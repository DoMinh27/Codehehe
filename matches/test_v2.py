import json
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import (
    Match,
    MatchPlayer,
    MatchPlayerSkill,
    MatchProblem,
    MatchSkill,
    PlayerProblemProgress,
    Skill,
    SkillEffect,
    SkillUse,
    Submission,
)
from matches.services.gameplay import FinishMatchService
from matches.services.run import CodeRunConflictError, CodeRunService
from matches.services.scoring import ScoringService
from matches.services.submission import (
    SubmissionConflictError,
    SubmissionService,
)
from matches.skills.definitions import (
    BLUR_STATEMENT,
    MIRROR_CODE,
    TIME_DRAIN_60,
)
from matches.skills.rewards import RewardService
from matches.skills.service import (
    SkillService,
    SkillUseConflictError,
    SkillUsePermissionError,
)
from problems.models import Problem
from problems.services.judge import FakeCodeRunner, FakeJudgeService


User = get_user_model()


SKILL_DATA = {
    MIRROR_CODE: ("Đảo chiều code", 1, 35),
    BLUR_STATEMENT: ("Làm mờ đề", 1, 35),
    TIME_DRAIN_60: ("Trừ thời gian", 1, None),
}


class V2FixtureMixin:
    def create_v2_fixture(self, *, room_code="V20001", started_at=None):
        self.host = User.objects.create(username=f"host-{room_code}")
        self.opponent = User.objects.create(username=f"opponent-{room_code}")
        self.outsider = User.objects.create(username=f"outsider-{room_code}")
        self.match = Match.objects.create(
            room_code=room_code,
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=started_at or timezone.now(),
        )
        self.host_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
            slot=1,
            is_active=True,
        )
        self.opponent_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
            slot=2,
            is_active=True,
        )
        self.match_skills = {}
        for code, (name, cost, duration) in SKILL_DATA.items():
            skill, _ = Skill.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": f"{name} description",
                    "energy_cost": cost,
                    "duration_seconds": duration,
                    "is_active": True,
                },
            )
            self.match_skills[code] = MatchSkill.objects.create(
                match=self.match,
                skill=skill,
                code_snapshot=code,
                name_snapshot=name,
                description_snapshot=skill.description,
                energy_cost_snapshot=cost,
                duration_seconds_snapshot=duration,
            )

        problem = Problem.objects.create(
            slug=f"problem-{room_code.lower()}",
            title="V2 Problem",
            statement="Visible statement",
            difficulty=Problem.Difficulty.EASY,
            points=1,
        )
        self.match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=problem,
            order=1,
            points=1,
            title_snapshot=problem.title,
            statement_snapshot=problem.statement,
            difficulty_snapshot=problem.difficulty,
            sample_tests_snapshot=[
                {"input_data": "sample", "expected_output": "sample-output"}
            ],
            hidden_tests_snapshot=[
                {"input_data": "hidden-secret", "expected_output": "hidden-output"}
            ],
        )
        self.host_progress = PlayerProblemProgress.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problem,
        )
        self.opponent_progress = PlayerProblemProgress.objects.create(
            match=self.match,
            player=self.opponent_player,
            match_problem=self.match_problem,
        )

    def grant(self, player, code, *, quantity=1, energy=3):
        player.energy = energy
        player.save(update_fields=["energy"])
        return MatchPlayerSkill.objects.create(
            player=player,
            match_skill=self.match_skills[code],
            quantity=quantity,
        )


class EnergyRewardTests(V2FixtureMixin, TestCase):
    def setUp(self):
        self.create_v2_fixture(room_code="ENERGY")

    def accepted_submission(self):
        return Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problem,
            source_code="print(1)",
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )

    def test_first_solve_awards_energy_and_one_deterministic_skill_once(self):
        selected = self.match_skills[MIRROR_CODE]
        scoring = ScoringService(
            reward_service=RewardService(selector=lambda skills: selected)
        )
        submission = self.accepted_submission()

        scoring.process_submission(submission.pk)
        scoring.process_submission(submission.pk)

        self.host_player.refresh_from_db()
        self.host_progress.refresh_from_db()
        inventory = MatchPlayerSkill.objects.get(
            player=self.host_player,
            match_skill=selected,
        )
        self.assertEqual(self.host_player.energy, 1)
        self.assertEqual(inventory.quantity, 1)
        self.assertTrue(self.host_progress.reward_processed)
        self.assertEqual(self.host_progress.energy_awarded, 1)
        self.assertEqual(self.host_progress.skill_awarded, selected)

    def test_full_energy_still_drops_skill_without_exceeding_cap(self):
        snapshot = deepcopy(self.match.rules_snapshot)
        snapshot["energy"]["max"] = 2
        self.match.rules_snapshot = snapshot
        self.match.save(update_fields=["rules_snapshot"])
        self.host_player.energy = 2
        self.host_player.save(update_fields=["energy"])
        selected = self.match_skills[BLUR_STATEMENT]
        submission = self.accepted_submission()

        ScoringService(
            reward_service=RewardService(selector=lambda skills: selected)
        ).process_submission(submission.pk)

        self.host_player.refresh_from_db()
        self.host_progress.refresh_from_db()
        self.assertEqual(self.host_player.energy, 2)
        self.assertEqual(self.host_progress.energy_awarded, 0)
        self.assertEqual(
            MatchPlayerSkill.objects.get(
                player=self.host_player,
                match_skill=selected,
            ).quantity,
            1,
        )


class SkillServiceTests(V2FixtureMixin, TestCase):
    def setUp(self):
        self.create_v2_fixture(room_code="SKILLS")

    def test_timed_skill_is_atomic_idempotent_and_does_not_stack(self):
        inventory = self.grant(
            self.host_player,
            MIRROR_CODE,
            quantity=2,
            energy=3,
        )
        service = SkillService()
        now = timezone.now()

        first = service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.opponent_player.pk,
            idempotency_key="mirror-1",
            now=now,
        )
        replay = service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.opponent_player.pk,
            idempotency_key="mirror-1",
            now=now,
        )

        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.skill_use.pk, replay.skill_use.pk)
        effect = SkillEffect.objects.get(skill_use=first.skill_use)
        self.assertEqual(effect.expires_at, now + timedelta(seconds=35))
        self.host_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual(self.host_player.energy, 2)
        self.assertEqual(inventory.quantity, 1)
        self.assertEqual(inventory.used_count, 1)

        with self.assertRaises(SkillUseConflictError):
            service.use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=MIRROR_CODE,
                target_player_id=self.opponent_player.pk,
                idempotency_key="mirror-2",
                now=now + timedelta(seconds=1),
            )
        self.host_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual((self.host_player.energy, inventory.quantity), (2, 1))

    def test_different_timed_effects_can_coexist(self):
        self.grant(self.host_player, MIRROR_CODE, energy=3)
        self.grant(self.host_player, BLUR_STATEMENT, energy=3)
        now = timezone.now()

        for code in (MIRROR_CODE, BLUR_STATEMENT):
            SkillService().use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=code,
                target_player_id=self.opponent_player.pk,
                idempotency_key=f"use-{code}",
                now=now,
            )

        self.assertEqual(
            SkillEffect.objects.filter(
                skill_use__target_player=self.opponent_player,
                expires_at__gt=now,
            ).count(),
            2,
        )

    def test_time_drain_stacks_with_sufficient_resources(self):
        inventory = self.grant(
            self.host_player,
            TIME_DRAIN_60,
            quantity=2,
            energy=3,
        )
        service = SkillService()
        now = timezone.now()
        service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=TIME_DRAIN_60,
            target_player_id=self.opponent_player.pk,
            idempotency_key="drain-1",
            now=now,
        )
        service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=TIME_DRAIN_60,
            target_player_id=self.opponent_player.pk,
            idempotency_key="drain-2",
            now=now,
        )

        self.opponent_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual(self.opponent_player.time_penalty_seconds, 120)
        self.assertEqual(inventory.quantity, 0)
        self.host_player.refresh_from_db()
        self.assertEqual(self.host_player.energy, 1)
        self.assertEqual(SkillUse.objects.count(), 2)
        self.assertEqual(SkillEffect.objects.count(), 0)

    def test_time_drain_uses_match_rules_snapshot(self):
        snapshot = deepcopy(self.match.rules_snapshot)
        snapshot["skill_effects"]["TIME_DRAIN_60"][
            "time_penalty_seconds"
        ] = 15
        self.match.rules_snapshot = snapshot
        self.match.save(update_fields=["rules_snapshot"])
        self.grant(
            self.host_player,
            TIME_DRAIN_60,
            energy=3,
        )

        SkillService().use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=TIME_DRAIN_60,
            target_player_id=self.opponent_player.pk,
            idempotency_key="drain-snapshot",
            now=timezone.now(),
        )

        self.opponent_player.refresh_from_db()
        self.assertEqual(self.opponent_player.time_penalty_seconds, 15)

    def test_outsider_self_target_and_reused_key_payload_are_rejected(self):
        self.grant(self.host_player, MIRROR_CODE)
        service = SkillService()
        with self.assertRaises(SkillUsePermissionError):
            service.use(
                user=self.outsider,
                match_id=self.match.pk,
                skill_code=MIRROR_CODE,
                target_player_id=self.opponent_player.pk,
                idempotency_key="outsider",
            )
        with self.assertRaises(SkillUsePermissionError):
            service.use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=MIRROR_CODE,
                target_player_id=self.host_player.pk,
                idempotency_key="self",
            )

        service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.opponent_player.pk,
            idempotency_key="same-key",
        )
        with self.assertRaises(SkillUseConflictError):
            service.use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=BLUR_STATEMENT,
                target_player_id=self.opponent_player.pk,
                idempotency_key="same-key",
            )


class PersonalDeadlineTests(V2FixtureMixin, TestCase):
    def setUp(self):
        self.create_v2_fixture(
            room_code="CLOCK1",
            started_at=timezone.now() - timedelta(seconds=900),
        )

    def test_expired_player_cannot_run_submit_or_use_skill(self):
        self.grant(self.host_player, MIRROR_CODE)

        with self.assertRaises(CodeRunConflictError):
            CodeRunService(FakeCodeRunner()).run(
                user=self.host,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
                input_data="",
            )
        with self.assertRaises(SubmissionConflictError):
            SubmissionService(FakeJudgeService()).submit(
                user=self.host,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
            )
        with self.assertRaises(SkillUseConflictError):
            SkillService().use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=MIRROR_CODE,
                target_player_id=self.opponent_player.pk,
                idempotency_key="expired",
            )

    def test_pending_submission_received_before_penalty_still_scores(self):
        pending = Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problem,
            source_code="print(1)",
        )
        Submission.objects.filter(pk=pending.pk).update(
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )

        ScoringService().process_submission(pending.pk)

        self.host_player.refresh_from_db()
        self.assertEqual(self.host_player.score, 2)

    def test_match_finishes_when_one_solved_and_the_other_timed_out(self):
        self.host_progress.is_solved = True
        self.host_progress.solved_at = timezone.now() - timedelta(minutes=1)
        self.host_progress.base_points_awarded = 1
        self.host_progress.reward_processed = True
        self.host_progress.save()
        self.host_player.score = 1
        self.host_player.save(update_fields=["score"])

        finished = FinishMatchService().finalize(match_id=self.match.pk)

        self.assertEqual(finished.status, Match.Status.FINISHED)
        self.assertEqual(finished.finish_reason, Match.FinishReason.TIMEOUT)
        self.assertEqual(finished.winner, self.host)


class SkillViewAndStateTests(V2FixtureMixin, TestCase):
    def setUp(self):
        self.create_v2_fixture(room_code="SKILLV")
        self.inventory = self.grant(self.host_player, MIRROR_CODE)

    def test_endpoint_contract_csrf_and_state_privacy(self):
        url = reverse(
            "skill-use",
            args=[self.match.pk, MIRROR_CODE],
        )
        payload = {
            "target_player_id": self.opponent_player.pk,
            "idempotency_key": "view-use-1",
        }
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.host)
        self.assertEqual(
            csrf_client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            ).status_code,
            403,
        )

        self.client.force_login(self.host)
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["code"], MIRROR_CODE)
        self.assertEqual(response.json()["my_energy"], 2)
        replay = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(replay.status_code, 200)

        state = self.client.get(reverse("match-state", args=[self.match.pk]))
        state_payload = state.json()
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state_payload["my_energy"], 2)
        self.assertEqual(len(state_payload["my_skills"]), 3)
        self.assertEqual(state_payload["active_effects"], [])
        self.assertNotIn("opponent_energy", state_payload)
        body = state.content.decode()
        self.assertNotIn("hidden-secret", body)
        self.assertNotIn("source_code", body)

        self.client.force_login(self.opponent)
        opponent_state = self.client.get(
            reverse("match-state", args=[self.match.pk])
        ).json()
        self.assertEqual(
            opponent_state["active_effects"][0]["code"],
            MIRROR_CODE,
        )

    def test_battle_loads_codemirror_bundle_and_keeps_textarea_fallback(self):
        self.client.force_login(self.host)

        response = self.client.get(reverse("battle", args=[self.match.pk]))

        self.assertContains(response, "matches/dist/main.bundle.js")
        self.assertContains(response, "matches/dist/battle.bundle.css")
        self.assertContains(response, 'class="source-code-input"')
        self.assertContains(response, '"skillUseUrlTemplate"')
