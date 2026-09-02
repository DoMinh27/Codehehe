from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from matches.models import MatchEvent, MatchPlayerSkill, Submission, TypingChallenge
from matches.services.events import get_timeline_page, record_event
from matches.services.gameplay import FinishMatchService, SurrenderMatchService
from matches.services.scoring import ScoringService
from matches.skills.definitions import (
    BLUR_STATEMENT,
    MIRROR_CODE,
    PURIFY,
    STEAL,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
)
from matches.skills.service import SkillService
from matches.skills.typing import TypingChallengeService
from matches.test_purify_steal import PurifyStealFixtureMixin


class TimelineTests(PurifyStealFixtureMixin, TestCase):
    def setUp(self):
        self.create_purify_steal_fixture(room_code="EVENT1")
        self.match.timeline_version = 1
        self.match.save(update_fields=["timeline_version"])
        record_event(
            match=self.match,
            kind=MatchEvent.Kind.MATCH_STARTED,
            event_key="started",
            payload={"duration_seconds": 300},
            now=self.match.started_at,
        )

    def submission(self, player=None, verdict=Submission.Verdict.ACCEPTED):
        return Submission.objects.create(
            match=self.match,
            player=player or self.host_player,
            match_problem=self.match_problem,
            verdict=verdict,
            source_code="private-source-secret",
            completed_at=timezone.now(),
        )

    def finish(self):
        self.match = SurrenderMatchService().surrender(
            user=self.host, match_id=self.match.pk
        )

    def test_scoring_events_are_idempotent_and_rewards_use_actual_energy(self):
        self.host_player.energy = 3
        self.host_player.save(update_fields=["energy"])
        submission = self.submission()
        scoring = ScoringService()
        scoring.process_submission(submission.pk)
        scoring.process_submission(submission.pk)
        scoring.process_submission(self.submission().pk)
        self.assertEqual(
            list(self.match.events.values_list("kind", flat=True)),
            [
                "MATCH_STARTED",
                "PROBLEM_SOLVED",
                "REWARD_GRANTED",
                "FIRST_SOLVE_CONFIRMED",
            ],
        )
        reward = self.match.events.get(kind="REWARD_GRANTED")
        self.assertEqual(reward.payload["energy"], 0)
        self.assertEqual(
            self.match.events.get(kind="FIRST_SOLVE_CONFIRMED").payload["score_after"],
            2,
        )

    def test_first_solve_waits_for_earlier_pending_without_reordering_events(self):
        earlier = self.submission(verdict=Submission.Verdict.PENDING)
        later = self.submission(player=self.opponent_player)
        Submission.objects.filter(pk=earlier.pk).update(
            received_at=timezone.now() - timedelta(seconds=5)
        )
        ScoringService().process_submission(later.pk)
        self.assertFalse(
            self.match.events.filter(kind="FIRST_SOLVE_CONFIRMED").exists()
        )
        earlier.verdict = Submission.Verdict.ACCEPTED
        earlier.save(update_fields=["verdict"])
        ScoringService().process_submission(earlier.pk)
        first = self.match.events.get(kind="FIRST_SOLVE_CONFIRMED")
        self.assertEqual(first.actor_id, self.host_player.pk)
        self.assertGreater(
            first.pk, self.match.events.filter(actor=self.opponent_player).last().pk
        )

    def test_event_failure_rolls_back_progress_score_and_reward(self):
        submission = self.submission()
        with patch(
            "matches.services.events.MatchEvent.objects.get_or_create",
            side_effect=RuntimeError("failed"),
        ):
            with self.assertRaises(RuntimeError):
                ScoringService().process_submission(submission.pk)
        self.host_progress.refresh_from_db()
        self.host_player.refresh_from_db()
        self.assertFalse(self.host_progress.is_solved)
        self.assertEqual((self.host_player.score, self.host_player.energy), (0, 0))
        self.assertFalse(
            MatchPlayerSkill.objects.filter(player=self.host_player).exists()
        )
        self.assertEqual(self.match.events.count(), 1)

    def test_event_key_is_unique_and_payload_rejects_sensitive_fields(self):
        with transaction.atomic():
            record_event(
                match=self.match,
                kind="MATCH_STARTED",
                event_key="started",
                payload={"duration_seconds": 1},
            )
        self.assertEqual(self.match.events.count(), 1)
        with self.assertRaises(ValueError):
            record_event(
                match=self.match,
                kind="MATCH_STARTED",
                event_key="bad",
                payload={"source_code": "secret"},
            )
        with self.assertRaises(ValueError):
            record_event(
                match=self.match,
                kind="MATCH_FINISHED",
                event_key="bad",
                payload={"scores": [{"source_code": "secret"}]},
            )

    def test_legacy_match_never_gets_partial_history(self):
        self.match.events.all().delete()
        self.match.timeline_version = 0
        self.match.save(update_fields=["timeline_version"])
        ScoringService().process_submission(self.submission().pk)
        self.finish()
        self.assertEqual(self.match.events.count(), 0)
        self.client.force_login(self.host)
        self.assertContains(
            self.client.get(reverse("match-result", args=[self.match.pk])),
            "Trận này chưa có dữ liệu diễn biến",
        )

    def test_surrender_and_late_verdict_do_not_change_finished_events(self):
        pending = self.submission(verdict=Submission.Verdict.PENDING)
        self.finish()
        before = list(self.match.events.values())
        SurrenderMatchService().surrender(user=self.host, match_id=self.match.pk)
        pending.verdict = Submission.Verdict.ACCEPTED
        pending.save(update_fields=["verdict"])
        ScoringService().process_submission(pending.pk)
        self.assertEqual(list(self.match.events.values()), before)
        last = self.match.events.last().payload
        self.assertEqual(last["winner_user_id"], self.opponent.pk)
        self.assertEqual(last["reason"], "SURRENDER")

    def test_all_solved_and_repeat_finalization_log_one_finish(self):
        for player in (self.host_player, self.opponent_player):
            ScoringService().process_submission(self.submission(player=player).pk)
        FinishMatchService().finalize(match_id=self.match.pk)
        FinishMatchService().finalize(match_id=self.match.pk)
        self.assertEqual(self.match.events.filter(kind="MATCH_FINISHED").count(), 1)
        self.assertEqual(self.match.events.last().payload["reason"], "ALL_SOLVED")

    def test_sweeper_timeout_logs_finish_after_actual_deadline(self):
        self.match.started_at = timezone.now() - timedelta(minutes=10)
        self.match.save(update_fields=["started_at"])
        call_command("sweep_matches", stdout=StringIO())
        self.match.refresh_from_db()
        event = self.match.events.get(kind="MATCH_FINISHED")
        self.assertEqual(event.payload["reason"], "TIMEOUT")
        self.assertGreater(event.recorded_at, self.match.ended_at)
        self.assertEqual(event.payload["ended_at"], self.match.ended_at.isoformat())

    def test_six_skills_and_typing_completion_have_safe_outcomes(self):
        now = timezone.now()
        self.grant(self.opponent_player, PURIFY)
        for code in (
            MIRROR_CODE,
            PURIFY,
            BLUR_STATEMENT,
            TYPING_CHALLENGE,
            TIME_DRAIN_60,
            STEAL,
        ):
            source, target = (
                (self.opponent_player, self.opponent_player)
                if code == PURIFY
                else (self.host_player, self.opponent_player)
            )
            if code != PURIFY:
                self.grant(source, code)
            if code == STEAL:
                self.grant(self.opponent_player, MIRROR_CODE)
            args = dict(
                user=source.user,
                match_id=self.match.pk,
                skill_code=code,
                target_player_id=target.pk,
                idempotency_key=code,
                now=now,
            )
            SkillService().use(**args)
            SkillService().use(**args)
            if code == TYPING_CHALLENGE:
                challenge = TypingChallenge.objects.get(
                    effect__skill_use__match=self.match
                )
                TypingChallengeService().complete(
                    user=self.opponent,
                    match_id=self.match.pk,
                    challenge_id=challenge.pk,
                    typed_text=challenge.prompt,
                    now=now + timedelta(seconds=1),
                )
        uses = self.match.events.filter(kind="SKILL_USED")
        self.assertEqual(uses.count(), 6)
        self.assertEqual(
            uses.get(payload__skill_code=PURIFY).payload["affected_skill_code"],
            MIRROR_CODE,
        )
        self.assertEqual(
            uses.get(payload__skill_code=STEAL).payload["affected_skill_code"],
            MIRROR_CODE,
        )
        self.assertEqual(
            uses.get(payload__skill_code=TIME_DRAIN_60).payload["time_penalty_seconds"],
            60,
        )
        self.assertEqual(self.match.events.filter(kind="TYPING_COMPLETED").count(), 1)
        self.assertNotIn(challenge.prompt, str(list(self.match.events.values())))

    def test_result_permissions_escape_and_sensitive_data_not_loaded(self):
        self.host.username = "<script>alert(1)</script>"
        self.host.save(update_fields=["username"])
        ScoringService().process_submission(self.submission().pk)
        self.finish()
        url = reverse("match-result", args=[self.match.pk])
        self.client.force_login(self.host)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "private-source-secret")
        self.assertNotContains(response, "hidden-secret")
        self.assertIn("no-store", response.headers["Cache-Control"])
        for query in queries:
            self.assertNotIn('"source_code"', query["sql"])
            self.assertNotIn('"hidden_tests_snapshot"', query["sql"])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.outsider.is_staff = True
        self.outsider.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_pagination_and_snapshot_survive_problem_and_user_changes(self):
        ScoringService().process_submission(self.submission().pk)
        self.match_problem.title_snapshot = "EDITED"
        self.match_problem.save(update_fields=["title_snapshot"])
        self.host.username = "changed-name"
        self.host.save(update_fields=["username"])
        for i in range(55):
            record_event(
                match=self.match,
                kind="MATCH_STARTED",
                event_key=f"test:{i}",
                payload={"duration_seconds": 300},
            )
        self.finish()
        page = get_timeline_page(match=self.match, page=1)
        self.assertEqual(len(page), 50)
        self.assertIn("V2 Problem", page.object_list[1]["text"])
        self.assertIn("host-EVENT1", page.object_list[1]["text"])
        next_page = get_timeline_page(match=self.match, page=2)
        self.assertLess(page.object_list[-1]["id"], next_page.object_list[0]["id"])
        self.assertFalse(admin.site._registry[MatchEvent].has_change_permission(None))
        self.assertFalse(admin.site._registry[MatchEvent].has_add_permission(None))
        self.assertFalse(admin.site._registry[MatchEvent].has_delete_permission(None))


class TimelineMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_old_matches_and_capacity_triggers(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        old_target = [("matches", "0020_purify_steal_skills")]
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        user = old_apps.get_model("auth", "User").objects.create(
            username="legacy-event-host"
        )
        match = old_apps.get_model("matches", "Match").objects.create(
            room_code="OLDLOG",
            host_id=user.pk,
            status="PLAYING",
            started_at=timezone.now(),
        )
        old_rules = match.rules_snapshot
        old_started = match.started_at
        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
        apps = executor.loader.project_state(leaves).apps
        migrated = apps.get_model("matches", "Match").objects.get(pk=match.pk)
        self.assertEqual(migrated.timeline_version, 0)
        self.assertEqual(migrated.status, "PLAYING")
        self.assertEqual(migrated.started_at, old_started)
        self.assertEqual(migrated.rules_snapshot, old_rules)
        self.assertEqual(apps.get_model("matches", "MatchEvent").objects.count(), 0)
        self.assertEqual(apps.get_model("matches", "RematchRequest").objects.count(), 0)
        players = apps.get_model("matches", "MatchPlayer")
        for index in range(3):
            member = apps.get_model("auth", "User").objects.create(
                username=f"old-capacity-{index}"
            )
            if index < 2:
                players.objects.create(match_id=match.pk, user_id=member.pk)
            else:
                with self.assertRaises(IntegrityError), transaction.atomic():
                    players.objects.create(match_id=match.pk, user_id=member.pk)
