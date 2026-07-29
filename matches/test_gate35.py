from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from problems.models import Problem
from problems.services.judge import (
    FakeCodeRunner,
    Judge0UnavailableError,
    RunResult,
    RunVerdict,
)

from .models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
)
from .services.gameplay import (
    MatchPermissionError,
    MatchStateError,
    SurrenderMatchService,
)
from .services.run import (
    CodeRunConflictError,
    CodeRunPermissionError,
    CodeRunService,
    CodeRunUnavailableError,
    InvalidCodeRunError,
    MAX_DIAGNOSTIC_CHARS,
    MAX_INPUT_BYTES,
    MAX_SOURCE_BYTES,
    MAX_STDOUT_CHARS,
)
from .services.scoring import ScoringService

User = get_user_model()


class Gate35FixtureMixin:
    def create_fixture(self, *, room_code="GATE35"):
        self.host = User.objects.create_user(username=f"host-{room_code}")
        self.opponent = User.objects.create_user(username=f"opponent-{room_code}")
        self.outsider = User.objects.create_user(username=f"outsider-{room_code}")
        self.match = Match.objects.create(
            room_code=room_code,
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        self.host_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
        )
        self.opponent_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
        )
        self.problem = Problem.objects.create(
            slug=f"problem-{room_code.lower()}",
            title="Custom input",
            statement="Run it.",
            difficulty=Problem.Difficulty.EASY,
            points=1,
        )
        self.problem.test_cases.create(
            input_data="hidden-input",
            expected_output="hidden-output",
            is_sample=False,
        )
        self.match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            difficulty_snapshot=self.problem.difficulty,
        )
        for player in (self.host_player, self.opponent_player):
            PlayerProblemProgress.objects.create(
                match=self.match,
                player=player,
                match_problem=self.match_problem,
            )


class CodeRunServiceTests(Gate35FixtureMixin, TestCase):
    def setUp(self):
        self.create_fixture()

    def test_run_returns_output_without_database_side_effects(self):
        runner = FakeCodeRunner(
            RunResult(
                verdict=RunVerdict.COMPLETED,
                stdout="custom-output\n",
            )
        )
        before = (
            Submission.objects.count(),
            self.host_player.score,
            PlayerProblemProgress.objects.filter(is_solved=True).count(),
        )

        result = CodeRunService(runner).run(
            user=self.host,
            match_id=self.match.pk,
            match_problem_id=self.match_problem.pk,
            source_code="print(input())",
            input_data="custom-input",
        )

        self.host_player.refresh_from_db()
        self.assertEqual(result.stdout, "custom-output\n")
        self.assertEqual(runner.calls, [("print(input())", "custom-input")])
        self.assertEqual(
            before,
            (
                Submission.objects.count(),
                self.host_player.score,
                PlayerProblemProgress.objects.filter(is_solved=True).count(),
            ),
        )

    def test_payload_limits_and_types_are_validated_before_runner(self):
        runner = FakeCodeRunner()
        invalid_payloads = [
            ("", ""),
            ("x" * (MAX_SOURCE_BYTES + 1), ""),
            ("print(1)", "x" * (MAX_INPUT_BYTES + 1)),
            ("print(1)", None),
        ]

        for source_code, input_data in invalid_payloads:
            with self.subTest(source_code_length=len(source_code)):
                with self.assertRaises(InvalidCodeRunError):
                    CodeRunService(runner).run(
                        user=self.host,
                        match_id=self.match.pk,
                        match_problem_id=self.match_problem.pk,
                        source_code=source_code,
                        input_data=input_data,
                    )

        self.assertEqual(runner.calls, [])

    def test_outsider_is_rejected(self):
        runner = FakeCodeRunner()
        with self.assertRaises(CodeRunPermissionError):
            CodeRunService(runner).run(
                user=self.outsider,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
                input_data="",
            )
        self.assertEqual(runner.calls, [])

    def test_finished_or_expired_match_is_rejected(self):
        runner = FakeCodeRunner()
        self.match.started_at = timezone.now() - timedelta(seconds=901)
        self.match.save(update_fields=["started_at"])

        with self.assertRaises(CodeRunConflictError):
            CodeRunService(runner).run(
                user=self.host,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
                input_data="",
            )

        self.match.status = Match.Status.FINISHED
        self.match.save(update_fields=["status"])
        with self.assertRaises(CodeRunConflictError):
            CodeRunService(runner).run(
                user=self.host,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
                input_data="",
            )
        self.assertEqual(runner.calls, [])

    def test_output_and_diagnostic_are_safely_truncated(self):
        runner = FakeCodeRunner(
            RunResult(
                verdict=RunVerdict.RUNTIME_ERROR,
                stdout="o" * (MAX_STDOUT_CHARS + 10),
                diagnostic="\x00" + "e" * (MAX_DIAGNOSTIC_CHARS + 10),
            )
        )

        result = CodeRunService(runner).run(
            user=self.host,
            match_id=self.match.pk,
            match_problem_id=self.match_problem.pk,
            source_code="raise RuntimeError",
            input_data="",
        )

        self.assertEqual(len(result.stdout), MAX_STDOUT_CHARS)
        self.assertEqual(len(result.diagnostic), MAX_DIAGNOSTIC_CHARS)
        self.assertNotIn("\x00", result.diagnostic)

    def test_runner_failure_becomes_safe_unavailable_error(self):
        class FailingRunner:
            def run(self, **kwargs):
                raise Judge0UnavailableError("private infrastructure detail")

        with self.assertRaisesMessage(
            CodeRunUnavailableError,
            "Judge is temporarily unavailable",
        ):
            CodeRunService(FailingRunner()).run(
                user=self.host,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
                input_data="",
            )


class SurrenderMatchServiceTests(Gate35FixtureMixin, TestCase):
    def setUp(self):
        self.create_fixture(room_code="GIVEUP")
        self.service = SurrenderMatchService()

    def test_surrender_finishes_immediately_with_opponent_as_winner(self):
        match = self.service.surrender(user=self.host, match_id=self.match.pk)

        self.assertEqual(match.status, Match.Status.FINISHED)
        self.assertEqual(match.winner, self.opponent)
        self.assertEqual(match.finish_reason, Match.FinishReason.SURRENDER)
        self.assertEqual(match.surrendered_by, self.host)
        self.assertFalse(match.is_draw)
        self.assertIsNotNone(match.ended_at)

    def test_same_player_retry_is_idempotent(self):
        first = self.service.surrender(user=self.host, match_id=self.match.pk)
        second = self.service.surrender(user=self.host, match_id=self.match.pk)

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.ended_at, first.ended_at)

    def test_outsider_and_opponent_retry_are_rejected(self):
        with self.assertRaises(MatchPermissionError):
            self.service.surrender(user=self.outsider, match_id=self.match.pk)

        self.service.surrender(user=self.host, match_id=self.match.pk)
        with self.assertRaises(MatchStateError):
            self.service.surrender(user=self.opponent, match_id=self.match.pk)

    def test_pending_completion_after_surrender_does_not_change_score(self):
        pending = Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problem,
            source_code="print(1)",
        )
        self.service.surrender(user=self.host, match_id=self.match.pk)
        Submission.objects.filter(pk=pending.pk).update(
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )

        ScoringService().process_submission(pending.pk)

        pending.refresh_from_db()
        self.host_player.refresh_from_db()
        self.match_problem.refresh_from_db()
        self.assertTrue(pending.is_score_processed)
        self.assertEqual(self.host_player.score, 0)
        self.assertIsNone(self.match_problem.first_solver)
        self.match.refresh_from_db()
        self.assertEqual(self.match.winner, self.opponent)


class Gate35ViewTests(Gate35FixtureMixin, TestCase):
    def setUp(self):
        self.create_fixture(room_code="VIEW35")

    @patch("matches.views.submissions.Judge0Service.from_environment")
    def test_run_json_contract_does_not_persist_or_leak_hidden_data(
        self,
        runner_factory,
    ):
        runner_factory.return_value = FakeCodeRunner(
            RunResult(
                verdict=RunVerdict.COMPLETED,
                stdout="visible-output\n",
            )
        )
        self.client.force_login(self.host)

        response = self.client.post(
            reverse("code-run", args=[self.match.pk, self.match_problem.pk]),
            data='{"source_code": "print(input())", "input_data": "hello"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verdict"], RunVerdict.COMPLETED)
        self.assertEqual(response.json()["stdout"], "visible-output\n")
        self.assertNotContains(response, "hidden-input")
        self.assertNotContains(response, "hidden-output")
        self.assertFalse(Submission.objects.exists())

    @patch("matches.views.submissions.Judge0Service.from_environment")
    def test_run_unavailable_returns_503_without_private_detail(
        self,
        runner_factory,
    ):
        runner_factory.return_value = FakeCodeRunner()
        runner_factory.return_value.run = lambda **kwargs: (_ for _ in ()).throw(
            Judge0UnavailableError("private Judge0 URL")
        )
        self.client.force_login(self.host)

        response = self.client.post(
            reverse("code-run", args=[self.match.pk, self.match_problem.pk]),
            data='{"source_code": "print(1)", "input_data": ""}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "private Judge0 URL", status_code=503)

    @patch("matches.views.submissions.Judge0Service.from_environment")
    def test_run_endpoint_validation_and_authorization_statuses(
        self,
        runner_factory,
    ):
        runner_factory.return_value = FakeCodeRunner()
        url = reverse("code-run", args=[self.match.pk, self.match_problem.pk])
        self.client.force_login(self.host)
        self.assertEqual(
            self.client.post(
                url,
                data="not-json",
                content_type="application/json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                url,
                data='{"source_code": "", "input_data": ""}',
                content_type="application/json",
            ).status_code,
            400,
        )

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.post(
                url,
                data='{"source_code": "print(1)", "input_data": ""}',
                content_type="application/json",
            ).status_code,
            403,
        )

        self.client.force_login(self.host)
        self.assertEqual(
            self.client.post(
                reverse("code-run", args=[self.match.pk, 999999]),
                data='{"source_code": "print(1)", "input_data": ""}',
                content_type="application/json",
            ).status_code,
            404,
        )
        self.match.status = Match.Status.FINISHED
        self.match.save(update_fields=["status"])
        self.assertEqual(
            self.client.post(
                url,
                data='{"source_code": "print(1)", "input_data": ""}',
                content_type="application/json",
            ).status_code,
            409,
        )
        self.assertEqual(runner_factory.return_value.calls, [])

    def test_surrender_endpoint_and_result_show_reason(self):
        self.client.force_login(self.host)

        response = self.client.post(
            reverse("match-surrender", args=[self.match.pk])
        )

        self.assertEqual(response.status_code, 200)
        result = self.client.get(response.json()["result_url"])
        self.assertContains(result, "Đầu hàng")
        self.assertContains(result, f"{self.host.username} đã đầu hàng")

    def test_surrender_endpoint_statuses(self):
        url = reverse("match-surrender", args=[self.match.pk])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("match-surrender", args=[999999])).status_code,
            404,
        )

        self.match.status = Match.Status.FINISHED
        self.match.save(update_fields=["status"])
        self.client.force_login(self.host)
        self.assertEqual(self.client.post(url).status_code, 409)

    def test_gate35_endpoints_require_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.host)

        run_response = csrf_client.post(
            reverse("code-run", args=[self.match.pk, self.match_problem.pk]),
            data='{"source_code": "print(1)", "input_data": ""}',
            content_type="application/json",
        )
        surrender_response = csrf_client.post(
            reverse("match-surrender", args=[self.match.pk])
        )

        self.assertEqual(run_response.status_code, 403)
        self.assertEqual(surrender_response.status_code, 403)

    def test_battle_contains_run_and_surrender_controls(self):
        self.client.force_login(self.host)

        response = self.client.get(reverse("battle", args=[self.match.pk]))

        self.assertContains(response, "Chạy thử")
        self.assertContains(response, "Dữ liệu nhập (stdin)")
        self.assertContains(response, "Đầu hàng")
        self.assertContains(
            response,
            reverse("code-run", args=[self.match.pk, self.match_problem.pk]),
        )
