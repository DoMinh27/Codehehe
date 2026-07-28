from datetime import timedelta
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from problems.models import Problem
from problems.services.judge import (
    FakeCodeRunner,
    FakeJudgeService,
    JudgeResult,
    Verdict,
)

from .models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
)
from .services.gameplay import StartMatchService
from .services.scoring import ScoringService
from .services.submission import (
    PendingSubmissionRecoveryService,
    SubmissionService,
)

User = get_user_model()


class MatchIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="player")
        self.other = User.objects.create(username="other")
        self.match = Match.objects.create(room_code="LOCK01", host=self.user)

    def test_database_rejects_duplicate_room_slot(self):
        MatchPlayer.objects.create(
            match=self.match,
            user=self.user,
            slot=1,
            is_active=True,
            is_host=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchPlayer.objects.create(
                match=self.match,
                user=self.other,
                slot=1,
                is_active=True,
            )

    def test_database_rejects_a_third_player_even_without_a_slot(self):
        third = User.objects.create(username="third")
        MatchPlayer.objects.create(
            match=self.match,
            user=self.user,
            slot=1,
            is_active=True,
            is_host=True,
        )
        MatchPlayer.objects.create(
            match=self.match,
            user=self.other,
            slot=2,
            is_active=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchPlayer.objects.create(
                match=self.match,
                user=third,
                slot=None,
                is_active=False,
            )

    def test_database_rejects_two_active_memberships_for_one_user(self):
        MatchPlayer.objects.create(
            match=self.match,
            user=self.user,
            slot=1,
            is_active=True,
            is_host=True,
        )
        other_match = Match.objects.create(room_code="LOCK02", host=self.user)

        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchPlayer.objects.create(
                match=other_match,
                user=self.user,
                slot=1,
                is_active=True,
                is_host=True,
            )


class SnapshotAndIdempotencyTests(TestCase):
    def setUp(self):
        self.host = User.objects.create(username="host")
        self.opponent = User.objects.create(username="opponent")
        self.match = Match.objects.create(room_code="SNAP01", host=self.host)
        MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
            slot=1,
            is_active=True,
        )
        MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
            slot=2,
            is_active=True,
        )
        self.valid_problems = []
        for difficulty in (Problem.Difficulty.EASY, Problem.Difficulty.MEDIUM):
            invalid = Problem.objects.create(
                slug=f"invalid-{difficulty.lower()}",
                title="Invalid",
                statement="No hidden tests",
                difficulty=difficulty,
                points=1,
                order=0,
            )
            self.assertTrue(invalid.is_active)
            for index in range(2):
                problem = Problem.objects.create(
                    slug=f"{difficulty.lower()}-{index}",
                    title=f"{difficulty} {index}",
                    statement="Frozen statement",
                    difficulty=difficulty,
                    points=1,
                    order=index + 1,
                )
                problem.test_cases.create(
                    input_data=f"sample-{difficulty}-{index}",
                    expected_output="sample-output",
                    is_sample=True,
                )
                problem.test_cases.create(
                    input_data=f"hidden-{difficulty}-{index}",
                    expected_output="hidden-output",
                    is_sample=False,
                )
                self.valid_problems.append(problem)

    def test_start_skips_problem_without_hidden_tests_and_freezes_tests(self):
        StartMatchService().start(user=self.host, match_id=self.match.pk)

        match_problems = list(self.match.match_problems.order_by("order"))
        self.assertEqual(len(match_problems), 4)
        self.assertNotIn("Invalid", [problem.title_snapshot for problem in match_problems])
        frozen_hidden = match_problems[0].hidden_tests_snapshot.copy()
        self.valid_problems[0].test_cases.filter(is_sample=False).update(
            input_data="changed-after-start",
            expected_output="changed-output",
        )
        match_problems[0].refresh_from_db()
        self.assertEqual(match_problems[0].hidden_tests_snapshot, frozen_hidden)

    def test_idempotency_key_reuses_submission_and_snapshot(self):
        StartMatchService().start(user=self.host, match_id=self.match.pk)
        match_problem = self.match.match_problems.order_by("order").first()
        judge = FakeJudgeService(JudgeResult(verdict=Verdict.ACCEPTED))
        service = SubmissionService(judge)

        first = service.submit(
            user=self.host,
            match_id=self.match.pk,
            match_problem_id=match_problem.pk,
            source_code="print(1)",
            idempotency_key="same-request",
        )
        second = service.submit(
            user=self.host,
            match_id=self.match.pk,
            match_problem_id=match_problem.pk,
            source_code="print(999)",
            idempotency_key="same-request",
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(len(judge.calls), 1)
        self.assertEqual(
            judge.calls[0][1][0].input_data,
            match_problem.hidden_tests_snapshot[0]["input_data"],
        )


class PendingRecoveryAndSweepTests(TestCase):
    def setUp(self):
        self.host = User.objects.create(username="host")
        self.opponent = User.objects.create(username="opponent")
        self.match = Match.objects.create(
            room_code="SWEEP1",
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
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
        problem = Problem.objects.create(
            slug="sweep-problem",
            title="Sweep",
            statement="Statement",
            difficulty=Problem.Difficulty.EASY,
            points=2,
        )
        self.match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=problem,
            order=1,
            points=2,
            title_snapshot=problem.title,
            statement_snapshot=problem.statement,
            difficulty_snapshot=problem.difficulty,
            hidden_tests_snapshot=[
                {"input_data": "1", "expected_output": "1"}
            ],
        )
        for player in (self.host_player, self.opponent_player):
            PlayerProblemProgress.objects.create(
                match=self.match,
                player=player,
                match_problem=self.match_problem,
            )

    def test_stale_pending_is_recovered_and_unblocks_first_solve(self):
        old_time = timezone.now() - timedelta(minutes=5)
        pending = Submission.objects.create(
            match=self.match,
            player=self.opponent_player,
            match_problem=self.match_problem,
            source_code="print(0)",
        )
        Submission.objects.filter(pk=pending.pk).update(received_at=old_time)
        accepted = Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problem,
            source_code="print(1)",
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )
        ScoringService().process_submission(accepted.pk)
        self.match_problem.refresh_from_db()
        self.assertIsNone(self.match_problem.first_solver_id)

        recovered = PendingSubmissionRecoveryService(
            scoring_service=ScoringService(),
            timeout_seconds=60,
        ).recover(now=timezone.now())

        self.assertEqual(recovered, 1)
        pending.refresh_from_db()
        self.match_problem.refresh_from_db()
        self.host_player.refresh_from_db()
        self.assertEqual(pending.verdict, Submission.Verdict.INTERNAL_ERROR)
        self.assertEqual(self.match_problem.first_solver_id, self.host_player.pk)
        self.assertEqual(self.host_player.score, 3)

        late_result = SubmissionService(FakeJudgeService())._complete_submission(
            pending,
            JudgeResult(verdict=Verdict.ACCEPTED),
        )
        self.assertEqual(late_result.verdict, Submission.Verdict.INTERNAL_ERROR)

    def test_sweeper_finishes_timeout_at_server_deadline_and_releases_players(self):
        started_at = timezone.now() - timedelta(seconds=901)
        Match.objects.filter(pk=self.match.pk).update(started_at=started_at)
        self.match.refresh_from_db()
        expected_ended_at = self.match.ends_at

        output = io.StringIO()
        call_command("sweep_matches", stdout=output)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.FINISHED)
        self.assertEqual(self.match.ended_at, expected_ended_at)
        self.assertFalse(self.match.players.filter(is_active=True).exists())
        self.assertIn("finished 1 match", output.getvalue())


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create(username="runner")
        self.match = Match.objects.create(
            room_code="RATE01",
            host=self.user,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        self.player = MatchPlayer.objects.create(
            match=self.match,
            user=self.user,
            is_host=True,
            slot=1,
            is_active=True,
        )
        problem = Problem.objects.create(
            slug="rate-problem",
            title="Rate",
            statement="Statement",
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
        )
        self.client.force_login(self.user)

    @override_settings(MATCH_RUN_RATE_LIMIT=1, MATCH_RATE_LIMIT_WINDOW_SECONDS=60)
    @patch("matches.views.Judge0Service.from_environment")
    def test_run_endpoint_returns_429_after_limit(self, runner_factory):
        runner_factory.return_value = FakeCodeRunner()
        url = reverse(
            "code-run",
            args=[self.match.pk, self.match_problem.pk],
        )
        payload = {
            "source_code": "print(input())",
            "input_data": "hello",
        }

        first = self.client.post(url, payload, content_type="application/json")
        second = self.client.post(url, payload, content_type="application/json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
