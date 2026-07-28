from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.utils import timezone

from problems.models import Problem
from problems.services.judge import (
    FakeJudgeService,
    Judge0ConfigurationError,
    Judge0UnavailableError,
    JudgeResult,
    Verdict,
)

from .models import Match, MatchPlayer, MatchProblem, PlayerProblemProgress, Submission
from .services.submission import (
    InvalidSubmissionError,
    SubmissionConflictError,
    SubmissionNotFoundError,
    SubmissionPermissionError,
    SubmissionService,
)


class MatchModelTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.opponent = User.objects.create_user(
            username="opponent",
            password="Password-938!",
        )
        self.match = Match.objects.create(room_code="ABC123", host=self.host)
        self.problem = Problem.objects.create(
            slug="match-problem",
            title="Original title",
            statement="Original statement",
            difficulty=Problem.Difficulty.EASY,
            points=1,
            starter_code="print('start')",
        )

    def test_match_defaults_and_ends_at(self):
        self.assertEqual(self.match.status, Match.Status.WAITING)
        self.assertEqual(self.match.duration_seconds, 900)
        self.assertIsNone(self.match.ends_at)

        started_at = timezone.now()
        self.match.started_at = started_at
        self.match.save()

        self.assertEqual(self.match.ends_at, started_at + timedelta(minutes=15))

    def test_match_cannot_have_winner_and_draw(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Match.objects.create(
                room_code="DRAW01",
                host=self.host,
                winner=self.host,
                is_draw=True,
            )

    def test_match_player_is_unique_per_user_and_match(self):
        MatchPlayer.objects.create(match=self.match, user=self.host, is_host=True)

        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchPlayer.objects.create(
                match=self.match,
                user=self.host,
            )

    def test_match_problem_keeps_content_snapshot_and_unique_order(self):
        host_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
        )
        match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=self.problem,
            order=1,
            points=self.problem.points,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            starter_code_snapshot=self.problem.starter_code,
            difficulty_snapshot=self.problem.difficulty,
            first_solver=host_player,
        )
        self.problem.title = "Changed title"
        self.problem.save()

        match_problem.refresh_from_db()
        self.assertEqual(match_problem.title_snapshot, "Original title")

        second_problem = Problem.objects.create(
            slug="second-match-problem",
            title="Second problem",
            statement="Second statement",
            difficulty=Problem.Difficulty.MEDIUM,
            points=2,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchProblem.objects.create(
                match=self.match,
                problem=second_problem,
                order=1,
                points=second_problem.points,
                title_snapshot=second_problem.title,
                statement_snapshot=second_problem.statement,
                difficulty_snapshot=second_problem.difficulty,
            )

    def test_submission_defaults_to_pending_python(self):
        player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
        )
        match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            starter_code_snapshot=self.problem.starter_code,
            difficulty_snapshot=self.problem.difficulty,
        )

        submission = Submission.objects.create(
            match=self.match,
            player=player,
            match_problem=match_problem,
            source_code="print(5)",
        )

        self.assertEqual(submission.language, Submission.Language.PYTHON)
        self.assertEqual(submission.verdict, Submission.Verdict.PENDING)
        self.assertFalse(submission.is_score_processed)

    def test_progress_is_unique_and_bonus_is_zero_or_one(self):
        player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
        )
        match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            difficulty_snapshot=self.problem.difficulty,
        )
        PlayerProblemProgress.objects.create(
            match=self.match,
            player=player,
            match_problem=match_problem,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerProblemProgress.objects.create(
                match=self.match,
                player=player,
                match_problem=match_problem,
            )

        opponent_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerProblemProgress.objects.create(
                match=self.match,
                player=opponent_player,
                match_problem=match_problem,
                first_solve_bonus_awarded=2,
            )


class SubmissionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="player", password="Password-938!")
        self.other_user = User.objects.create_user(username="other", password="Password-938!")
        self.match = Match.objects.create(
            room_code="PLAY01",
            host=self.user,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        self.player = MatchPlayer.objects.create(
            match=self.match, user=self.user, is_host=True
        )
        self.problem = Problem.objects.create(
            slug="submission-problem",
            title="Submission problem",
            statement="Print the result.",
            difficulty=Problem.Difficulty.EASY,
            points=1,
        )
        self.match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            difficulty_snapshot=self.problem.difficulty,
            sample_tests_snapshot=[
                {
                    "input_data": "visible-input",
                    "expected_output": "visible-output",
                }
            ],
            hidden_tests_snapshot=[
                {
                    "input_data": "hidden-input",
                    "expected_output": "hidden-output",
                }
            ],
        )
        self.problem.test_cases.create(
            input_data="visible-input", expected_output="visible-output", is_sample=True
        )
        self.problem.test_cases.create(
            input_data="hidden-input", expected_output="hidden-output", is_sample=False
        )

    def service(self, result):
        return SubmissionService(FakeJudgeService(result=result))

    def submit(self, service):
        return service.submit(
            user=self.user,
            match_id=self.match.pk,
            match_problem_id=self.match_problem.pk,
            source_code="print('ok')",
        )

    def test_maps_all_judge_verdicts_and_keeps_scoring_unchanged(self):
        cases = {
            Verdict.ACCEPTED: Submission.Verdict.ACCEPTED,
            Verdict.WRONG_ANSWER: Submission.Verdict.WRONG_ANSWER,
            Verdict.COMPILATION_ERROR: Submission.Verdict.COMPILATION_ERROR,
            Verdict.RUNTIME_ERROR: Submission.Verdict.RUNTIME_ERROR,
            Verdict.TIME_LIMIT_EXCEEDED: Submission.Verdict.TIME_LIMIT_EXCEEDED,
        }
        for judge_verdict, submission_verdict in cases.items():
            with self.subTest(judge_verdict=judge_verdict):
                submission = self.submit(self.service(JudgeResult(verdict=judge_verdict)))
                self.assertEqual(submission.verdict, submission_verdict)
                self.assertIsNotNone(submission.completed_at)
                self.assertFalse(submission.is_score_processed)
                self.player.refresh_from_db()
                self.assertEqual(self.player.score, 0)

    def test_only_hidden_test_cases_are_sent_to_judge(self):
        judge = FakeJudgeService()
        submission = self.submit(SubmissionService(judge))

        self.assertEqual(submission.verdict, Submission.Verdict.ACCEPTED)
        self.assertEqual(len(judge.calls), 1)
        _, test_cases = judge.calls[0]
        self.assertEqual(len(test_cases), 1)
        self.assertEqual(test_cases[0].input_data, "hidden-input")
        self.assertEqual(test_cases[0].expected_output, "hidden-output")

    def test_rejects_empty_source_without_creating_submission(self):
        with self.assertRaises(InvalidSubmissionError):
            SubmissionService(FakeJudgeService()).submit(
                user=self.user,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code=" \n ",
            )
        self.assertFalse(Submission.objects.exists())

    def test_rejects_user_outside_match(self):
        with self.assertRaises(SubmissionPermissionError):
            SubmissionService(FakeJudgeService()).submit(
                user=self.other_user,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print('ok')",
            )

    def test_rejects_problem_outside_match(self):
        other_problem = Problem.objects.create(
            slug="outside-match", title="Outside", statement="", difficulty="EASY", points=1
        )
        outside_match_problem = MatchProblem.objects.create(
            match=Match.objects.create(room_code="OTHER1", host=self.other_user),
            problem=other_problem,
            order=1,
            points=1,
            title_snapshot="Outside",
            statement_snapshot="",
            difficulty_snapshot="EASY",
        )
        with self.assertRaises(SubmissionNotFoundError):
            SubmissionService(FakeJudgeService()).submit(
                user=self.user,
                match_id=self.match.pk,
                match_problem_id=outside_match_problem.pk,
                source_code="print('ok')",
            )

    def test_rejects_inactive_and_expired_match_without_judging(self):
        judge = FakeJudgeService()
        self.match.status = Match.Status.WAITING
        self.match.save()
        with self.assertRaises(SubmissionConflictError):
            self.submit(SubmissionService(judge))
        self.assertEqual(judge.calls, [])
        self.assertFalse(Submission.objects.exists())

        self.match.status = Match.Status.PLAYING
        self.match.started_at = timezone.now() - timedelta(minutes=16)
        self.match.save()
        with self.assertRaises(SubmissionConflictError):
            self.submit(SubmissionService(judge))
        self.assertEqual(judge.calls, [])
        self.assertFalse(Submission.objects.exists())

    def test_judge_error_becomes_safe_internal_error(self):
        class UnavailableJudge:
            def judge(self, **kwargs):
                raise Judge0UnavailableError("hidden-input must not leak")

        submission = self.submit(SubmissionService(UnavailableJudge()))
        self.assertEqual(submission.verdict, Submission.Verdict.INTERNAL_ERROR)
        self.assertIsNotNone(submission.completed_at)
        self.assertNotIn("hidden-input", submission.judge_message)


class SubmissionViewTests(TestCase):
    def setUp(self):
        SubmissionServiceTests.setUp(self)

    def post(self, payload, *, client=None):
        return (client or self.client).post(
            f"/matches/{self.match.pk}/problems/{self.match_problem.pk}/submissions/",
            data=payload,
            content_type="application/json",
        )

    @patch("matches.views.Judge0Service.from_environment")
    def test_authenticated_json_submit_returns_safe_contract(self, judge_factory):
        judge_factory.return_value = FakeJudgeService(
            result=JudgeResult(
                verdict=Verdict.WRONG_ANSWER,
                stdout="hidden-input",
                stderr="hidden-output",
                message="raw judge detail",
            )
        )
        self.client.force_login(self.user)

        response = self.post('{"source_code": "print(1)"}')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["verdict"], Submission.Verdict.WRONG_ANSWER)
        self.assertEqual(
            set(response.json()), {"id", "verdict", "received_at", "completed_at", "message"}
        )
        self.assertNotIn("hidden-input", response.content.decode())
        self.assertNotIn("hidden-output", response.content.decode())
        self.assertNotIn("raw judge detail", response.content.decode())

    def test_view_validation_and_authorization_statuses(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post("not json").status_code, 400)
        self.assertEqual(self.post('{"source_code": ""}').status_code, 400)

        self.client.force_login(self.other_user)
        self.assertEqual(self.post('{"source_code": "print(1)"}').status_code, 403)

        self.client.force_login(self.user)
        self.match.status = Match.Status.WAITING
        self.match.save()
        self.assertEqual(self.post('{"source_code": "print(1)"}').status_code, 409)

    @patch("matches.views.Judge0Service.from_environment", return_value=FakeJudgeService())
    def test_view_requires_csrf_for_session_submit(self, judge_factory):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = self.post('{"source_code": "print(1)"}', client=csrf_client)
        self.assertEqual(response.status_code, 403)

    @patch(
        "matches.views.Judge0Service.from_environment",
        side_effect=Judge0ConfigurationError("missing JUDGE0_BASE_URL"),
    )
    def test_judge_configuration_error_is_persisted_as_internal_error(self, judge_factory):
        self.client.force_login(self.user)

        response = self.post('{"source_code": "print(1)"}')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["verdict"], Submission.Verdict.INTERNAL_ERROR)
        self.assertEqual(Submission.objects.count(), 1)
