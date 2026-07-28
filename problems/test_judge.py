from unittest.mock import patch

from django.test import SimpleTestCase

from .services.judge import (
    FakeCodeRunner,
    FakeJudgeService,
    Judge0ConfigurationError,
    Judge0Service,
    JudgeResult,
    JudgeTestCase,
    RunResult,
    RunVerdict,
    Verdict,
)


class FakeJudgeServiceTests(SimpleTestCase):
    def setUp(self):
        self.test_cases = [
            JudgeTestCase(input_data="2 3", expected_output="5"),
            JudgeTestCase(input_data="0 0", expected_output="0"),
        ]

    def test_default_result_is_accepted_for_all_given_test_cases(self):
        judge = FakeJudgeService()

        result = judge.judge(
            source_code="print(sum(map(int, input().split())))",
            test_cases=self.test_cases,
        )

        self.assertTrue(result.is_accepted)
        self.assertEqual(result.verdict, Verdict.ACCEPTED)
        self.assertEqual(result.passed_test_cases, 2)
        self.assertEqual(result.total_test_cases, 2)
        self.assertEqual(len(judge.calls), 1)

    def test_configured_wrong_answer_is_returned_without_executing_code(self):
        judge = FakeJudgeService(
            result=JudgeResult(
                verdict=Verdict.WRONG_ANSWER,
                passed_test_cases=1,
                stdout="4",
                message="Output differs from expected output.",
            )
        )

        result = judge.judge(source_code="print(4)", test_cases=self.test_cases)

        self.assertFalse(result.is_accepted)
        self.assertEqual(result.verdict, Verdict.WRONG_ANSWER)
        self.assertEqual(result.passed_test_cases, 1)
        self.assertEqual(result.total_test_cases, 2)
        self.assertEqual(result.stdout, "4")

    def test_empty_source_code_is_rejected_before_calling_the_judge(self):
        judge = FakeJudgeService()

        with self.assertRaisesMessage(ValueError, "source_code must not be empty"):
            judge.judge(source_code="   ", test_cases=self.test_cases)

        self.assertEqual(judge.calls, [])


class FakeCodeRunnerTests(SimpleTestCase):
    def test_records_custom_input_without_executing_source(self):
        runner = FakeCodeRunner(
            result=RunResult(
                verdict=RunVerdict.COMPLETED,
                stdout="5\n",
            )
        )

        result = runner.run(source_code="print(input())", input_data="5")

        self.assertEqual(result.stdout, "5\n")
        self.assertEqual(runner.calls, [("print(input())", "5")])


class Judge0ServiceTests(SimpleTestCase):
    def setUp(self):
        self.test_cases = [
            JudgeTestCase(input_data="2 3", expected_output="5"),
            JudgeTestCase(input_data="0 0", expected_output="0"),
        ]

    def test_missing_base_url_is_a_configuration_error(self):
        with patch.dict("os.environ", {"JUDGE0_BASE_URL": ""}, clear=True):
            with self.assertRaises(Judge0ConfigurationError):
                Judge0Service.from_environment()

    def test_accepts_every_test_case_and_sends_expected_output_to_judge(self):
        judge = Judge0Service(base_url="https://judge.example")
        responses = iter([{"status": {"id": 3}}, {"status": {"id": 3}}])

        with patch.object(judge, "_submit", side_effect=responses) as submit:
            result = judge.judge(source_code="print(5)", test_cases=self.test_cases)

        self.assertEqual(result.verdict, Verdict.ACCEPTED)
        self.assertEqual(result.passed_test_cases, 2)
        self.assertEqual(submit.call_count, 2)

    def test_stops_on_wrong_answer_and_preserves_judge_output(self):
        judge = Judge0Service(base_url="https://judge.example")
        response = {
            "status": {"id": 4},
            "stdout": "4\n",
            "stderr": "",
            "message": "",
        }

        with patch.object(judge, "_submit", return_value=response):
            result = judge.judge(source_code="print(4)", test_cases=self.test_cases)

        self.assertEqual(result.verdict, Verdict.WRONG_ANSWER)
        self.assertEqual(result.passed_test_cases, 0)
        self.assertEqual(result.stdout, "4\n")

    def test_run_omits_expected_output_and_returns_stdout(self):
        runner = Judge0Service(base_url="https://judge.example")
        response = {
            "status": {"id": 3},
            "stdout": "hello\n",
        }

        with patch.object(
            runner,
            "_request_submission",
            return_value=response,
        ) as request_submission:
            result = runner.run(
                source_code="print(input())",
                input_data="hello",
            )

        self.assertEqual(result.verdict, RunVerdict.COMPLETED)
        self.assertEqual(result.stdout, "hello\n")
        request_submission.assert_called_once_with(
            source_code="print(input())",
            input_data="hello",
        )

    def test_run_returns_bounded_service_ready_diagnostic_fields(self):
        runner = Judge0Service(base_url="https://judge.example")
        response = {
            "status": {"id": 6},
            "stdout": "",
            "compile_output": "SyntaxError",
            "token": "must-not-be-returned",
        }

        with patch.object(runner, "_request_submission", return_value=response):
            result = runner.run(source_code="bad code", input_data="")

        self.assertEqual(result.verdict, RunVerdict.COMPILATION_ERROR)
        self.assertEqual(result.diagnostic, "SyntaxError")
