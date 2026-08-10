import importlib
from datetime import datetime, timedelta, timezone as dt_timezone

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import PlayerActivityDay
from problems.models import Problem
from problems.services.judge import FakeJudgeService

from .models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
)
from .services.submission import InvalidSubmissionError, SubmissionService


User = get_user_model()


class HistoryFixtureMixin:
    def setUp(self):
        self.user = User.objects.create_user(username="history-owner")
        self.opponent = User.objects.create_user(username="history-opponent")
        self.outsider = User.objects.create_user(username="history-outsider")
        self.staff = User.objects.create_user(username="history-staff", is_staff=True)
        self.problem = Problem.objects.create(
            slug="history-problem",
            title="History problem",
            statement="Print one.",
            difficulty=Problem.Difficulty.EASY,
            points=1,
            reference_solution="print(1)",
        )

    def create_finished_match(
        self,
        room_code="HIST01",
        *,
        winner="user",
        user_score=1,
        opponent_score=0,
        ended_at=None,
    ):
        ended_at = ended_at or timezone.now()
        winner_user = {
            "user": self.user,
            "opponent": self.opponent,
            "draw": None,
        }[winner]
        match = Match.objects.create(
            room_code=room_code,
            host=self.user,
            status=Match.Status.FINISHED,
            started_at=ended_at - timedelta(minutes=5),
            ended_at=ended_at,
            winner=winner_user,
            is_draw=winner == "draw",
            finish_reason=Match.FinishReason.TIMEOUT,
        )
        user_player = MatchPlayer.objects.create(
            match=match,
            user=self.user,
            score=user_score,
            slot=1,
        )
        opponent_player = MatchPlayer.objects.create(
            match=match,
            user=self.opponent,
            score=opponent_score,
            slot=2,
        )
        match_problem = MatchProblem.objects.create(
            match=match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            reference_solution_snapshot=self.problem.reference_solution,
            difficulty_snapshot=self.problem.difficulty,
        )
        return match, user_player, opponent_player, match_problem


class MatchHistoryViewTests(HistoryFixtureMixin, TestCase):
    def test_history_requires_login_and_only_lists_own_matches(self):
        self.create_finished_match()
        url = reverse("match-history")

        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.outsider)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chưa có trận đã hoàn thành")
        self.assertNotContains(response, self.opponent.username)

    def test_history_uses_persisted_winner_and_dynamic_problem_count(self):
        match, user_player, _, match_problem = self.create_finished_match(
            user_score=0,
            opponent_score=0,
        )
        progress = PlayerProblemProgress.objects.create(
            match=match,
            player=user_player,
            match_problem=match_problem,
            is_solved=True,
        )
        self.assertTrue(progress.is_solved)
        self.client.force_login(self.user)

        response = self.client.get(reverse("match-history"))

        self.assertContains(response, "Thắng")
        self.assertContains(response, "0 – 0")
        self.assertContains(response, "1/1")
        self.assertContains(response, reverse("match-result", args=[match.id]))
        self.assertContains(response, reverse("my-submissions", args=[match.id]))

    def test_history_is_paginated_newest_first(self):
        base_time = timezone.now()
        for index in range(11):
            self.create_finished_match(
                room_code=f"PG{index:04d}",
                ended_at=base_time + timedelta(minutes=index),
            )
        self.client.force_login(self.user)

        first_page = self.client.get(reverse("match-history"))
        second_page = self.client.get(reverse("match-history"), {"page": 2})

        self.assertEqual(len(first_page.context["history_rows"]), 10)
        self.assertEqual(len(second_page.context["history_rows"]), 1)
        self.assertEqual(
            first_page.context["history_rows"][0]["match"].room_code,
            "PG0010",
        )
        self.assertEqual(
            second_page.context["history_rows"][0]["match"].room_code,
            "PG0000",
        )


class MySubmissionsViewTests(HistoryFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        (
            self.match,
            self.user_player,
            self.opponent_player,
            self.match_problem,
        ) = self.create_finished_match()
        self.first_submission = Submission.objects.create(
            match=self.match,
            player=self.user_player,
            match_problem=self.match_problem,
            source_code="print('first')",
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )
        self.latest_submission = Submission.objects.create(
            match=self.match,
            player=self.user_player,
            match_problem=self.match_problem,
            source_code="</code><script>alert('xss')</script>",
            verdict=Submission.Verdict.WRONG_ANSWER,
            completed_at=timezone.now(),
        )
        Submission.objects.create(
            match=self.match,
            player=self.opponent_player,
            match_problem=self.match_problem,
            source_code="PRIVATE_OPPONENT_CODE",
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )
        PlayerProblemProgress.objects.create(
            match=self.match,
            player=self.user_player,
            match_problem=self.match_problem,
            is_solved=True,
            accepted_submission=self.first_submission,
            solved_at=timezone.now(),
        )

    def test_owner_sees_all_own_attempts_and_scoring_accepted_marker(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("my-submissions", args=[self.match.id]))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertContains(response, "print(&#x27;first&#x27;)", html=False)
        self.assertContains(response, "AC tính điểm")
        self.assertNotContains(response, "PRIVATE_OPPONENT_CODE")
        self.assertNotIn("</code><script>alert('xss')</script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertLess(
            body.index(f"Lần nộp #{self.latest_submission.id}"),
            body.index(f"Lần nộp #{self.first_submission.id}"),
        )

    def test_outsider_and_nonparticipant_staff_cannot_read_source(self):
        url = reverse("my-submissions", args=[self.match.id])
        for user in (self.outsider, self.staff):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_unfinished_match_source_is_not_available(self):
        self.match.status = Match.Status.PLAYING
        self.match.ended_at = None
        self.match.winner = None
        self.match.save(update_fields=["status", "ended_at", "winner"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("my-submissions", args=[self.match.id]))

        self.assertEqual(response.status_code, 404)

    def test_invalid_problem_selector_returns_not_found(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("my-submissions", args=[self.match.id]),
            {"problem": 999999},
        )

        self.assertEqual(response.status_code, 404)


@override_settings(TIME_ZONE="Asia/Ho_Chi_Minh")
class ActivityRecordingTests(HistoryFixtureMixin, TestCase):
    def active_submission_fixture(self):
        now = timezone.now()
        match = Match.objects.create(
            room_code="ACT001",
            host=self.user,
            status=Match.Status.PLAYING,
            started_at=now,
        )
        player = MatchPlayer.objects.create(
            match=match,
            user=self.user,
            slot=1,
        )
        match_problem = MatchProblem.objects.create(
            match=match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            difficulty_snapshot=self.problem.difficulty,
            hidden_tests_snapshot=[
                {"input_data": "", "expected_output": "1"},
            ],
        )
        return match, player, match_problem

    def test_submission_service_records_only_one_activity_day(self):
        match, player, match_problem = self.active_submission_fixture()
        service = SubmissionService(FakeJudgeService())
        for key in ("activity-one", "activity-two"):
            service.submit(
                user=self.user,
                match_id=match.id,
                match_problem_id=match_problem.id,
                source_code="print(1)",
                idempotency_key=key,
            )

        self.assertEqual(Submission.objects.filter(player=player).count(), 2)
        self.assertEqual(PlayerActivityDay.objects.filter(user=self.user).count(), 1)

    def test_rejected_submission_does_not_record_activity(self):
        match, _, match_problem = self.active_submission_fixture()

        with self.assertRaises(InvalidSubmissionError):
            SubmissionService(FakeJudgeService()).submit(
                user=self.user,
                match_id=match.id,
                match_problem_id=match_problem.id,
                source_code="  ",
            )

        self.assertFalse(PlayerActivityDay.objects.filter(user=self.user).exists())

    def test_backfill_uses_configured_local_dates(self):
        match, player, _, match_problem = self.create_finished_match()
        timestamps = (
            datetime(2026, 8, 9, 16, 30, tzinfo=dt_timezone.utc),
            datetime(2026, 8, 9, 17, 30, tzinfo=dt_timezone.utc),
        )
        for timestamp in timestamps:
            submission = Submission.objects.create(
                match=match,
                player=player,
                match_problem=match_problem,
                source_code="print(1)",
                verdict=Submission.Verdict.ACCEPTED,
            )
            Submission.objects.filter(pk=submission.pk).update(received_at=timestamp)

        migration = importlib.import_module(
            "accounts.migrations.0002_backfill_player_activity"
        )
        migration.backfill_player_activity(apps, None)

        self.assertEqual(
            list(
                PlayerActivityDay.objects.filter(user=self.user)
                .order_by("activity_date")
                .values_list("activity_date", flat=True)
            ),
            [datetime(2026, 8, 9).date(), datetime(2026, 8, 10).date()],
        )

    def test_match_player_prevents_history_loss_on_user_delete(self):
        match, _, opponent_player, _ = self.create_finished_match(winner="draw")
        self.assertEqual(opponent_player.match, match)

        with self.assertRaises(ProtectedError):
            self.opponent.delete()
