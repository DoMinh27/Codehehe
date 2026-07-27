from django.core.management.base import BaseCommand, CommandError

from problems.services.judge import (
    Judge0ConfigurationError,
    Judge0Service,
    Judge0UnavailableError,
    JudgeTestCase,
)


class Command(BaseCommand):
    help = "Send known correct, wrong, and runtime-error code to Judge0."

    def handle(self, *args, **options):
        try:
            judge = Judge0Service.from_environment()
        except Judge0ConfigurationError as error:
            raise CommandError(str(error)) from error

        cases = {
            "correct": "import sys\nprint(sum(map(int, sys.stdin.read().split())))",
            "wrong": "print(0)",
            "runtime_error": "raise RuntimeError('spike')",
        }
        test_case = JudgeTestCase(input_data="2 3", expected_output="5")

        for label, source_code in cases.items():
            try:
                result = judge.judge(source_code=source_code, test_cases=[test_case])
            except Judge0UnavailableError as error:
                raise CommandError(str(error)) from error
            self.stdout.write(
                f"{label}: {result.verdict} "
                f"({result.passed_test_cases}/{result.total_test_cases})"
            )
