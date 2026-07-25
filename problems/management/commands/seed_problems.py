import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError
from django.db import transaction

from problems.models import Problem, TestCase


DEFAULT_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "problems.json"
PROBLEM_FIELDS = {
    "slug",
    "title",
    "statement",
    "difficulty",
    "points",
    "starter_code",
    "order",
    "is_active",
    "test_cases",
}
TEST_CASE_FIELDS = {
    "input_data",
    "expected_output",
    "is_sample",
    "order",
}


class Command(BaseCommand):
    help = "Create or update the shared CodeHehe problem seed data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_DATA_FILE,
            help="Path to a problem seed JSON file.",
        )

    def handle(self, *args, **options):
        data_file = options["file"].resolve()
        payload = self._load_payload(data_file)
        problems = self._validate_payload(payload)

        created_count = 0
        updated_count = 0
        test_case_count = 0

        with transaction.atomic():
            for problem_data in problems:
                test_cases = problem_data.pop("test_cases")
                problem, created = Problem.objects.update_or_create(
                    slug=problem_data.pop("slug"),
                    defaults=problem_data,
                )
                problem.test_cases.all().delete()
                TestCase.objects.bulk_create(
                    [
                        TestCase(problem=problem, **test_case)
                        for test_case in test_cases
                    ]
                )

                created_count += int(created)
                updated_count += int(not created)
                test_case_count += len(test_cases)

        self.stdout.write(
            self.style.SUCCESS(
                "Seed completed: "
                f"{created_count} created, "
                f"{updated_count} updated, "
                f"{test_case_count} test cases."
            )
        )

    def _load_payload(self, data_file):
        try:
            return json.loads(data_file.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CommandError(f"Seed file not found: {data_file}") from error
        except json.JSONDecodeError as error:
            raise CommandError(
                f"Invalid JSON at line {error.lineno}, column {error.colno}."
            ) from error

    def _validate_payload(self, payload):
        if not isinstance(payload, dict):
            raise CommandError("The JSON root must be an object.")
        if payload.get("version") != 1:
            raise CommandError("Only seed format version 1 is supported.")

        problems = payload.get("problems")
        if not isinstance(problems, list) or not problems:
            raise CommandError("'problems' must be a non-empty list.")

        validated_problems = []
        seen_slugs = set()
        seen_titles = set()

        for index, raw_problem in enumerate(problems, start=1):
            label = f"Problem #{index}"
            self._require_exact_fields(raw_problem, PROBLEM_FIELDS, label)
            problem = dict(raw_problem)
            test_cases = problem["test_cases"]

            self._validate_problem(problem, label)
            if problem["slug"] in seen_slugs:
                raise CommandError(f"{label}: duplicate slug '{problem['slug']}'.")
            if problem["title"] in seen_titles:
                raise CommandError(f"{label}: duplicate title '{problem['title']}'.")

            validated_tests = self._validate_test_cases(test_cases, label)
            problem["test_cases"] = validated_tests
            validated_problems.append(problem)
            seen_slugs.add(problem["slug"])
            seen_titles.add(problem["title"])

        return validated_problems

    def _validate_problem(self, problem, label):
        self._require_text(problem["slug"], f"{label}.slug", max_length=220)
        try:
            validate_slug(problem["slug"])
        except ValidationError as error:
            raise CommandError(f"{label}.slug must be a valid ASCII slug.") from error

        self._require_text(problem["title"], f"{label}.title", max_length=200)
        self._require_text(problem["statement"], f"{label}.statement")
        if problem["difficulty"] not in Problem.Difficulty.values:
            choices = ", ".join(Problem.Difficulty.values)
            raise CommandError(f"{label}.difficulty must be one of: {choices}.")
        self._require_integer(problem["points"], f"{label}.points", minimum=1)
        if not isinstance(problem["starter_code"], str):
            raise CommandError(f"{label}.starter_code must be a string.")
        self._require_integer(problem["order"], f"{label}.order", minimum=0)
        if not isinstance(problem["is_active"], bool):
            raise CommandError(f"{label}.is_active must be a boolean.")

    def _validate_test_cases(self, test_cases, problem_label):
        if not isinstance(test_cases, list) or not test_cases:
            raise CommandError(f"{problem_label}.test_cases must be a non-empty list.")

        validated_tests = []
        seen_orders = set()
        has_sample = False
        has_hidden = False

        for index, raw_test in enumerate(test_cases, start=1):
            label = f"{problem_label}.test_cases[{index}]"
            self._require_exact_fields(raw_test, TEST_CASE_FIELDS, label)
            test_case = dict(raw_test)

            if not isinstance(test_case["input_data"], str):
                raise CommandError(f"{label}.input_data must be a string.")
            if not isinstance(test_case["expected_output"], str):
                raise CommandError(f"{label}.expected_output must be a string.")
            if not isinstance(test_case["is_sample"], bool):
                raise CommandError(f"{label}.is_sample must be a boolean.")
            self._require_integer(test_case["order"], f"{label}.order", minimum=0)
            if test_case["order"] in seen_orders:
                raise CommandError(
                    f"{problem_label}: duplicate test case order "
                    f"{test_case['order']}."
                )

            seen_orders.add(test_case["order"])
            has_sample = has_sample or test_case["is_sample"]
            has_hidden = has_hidden or not test_case["is_sample"]
            validated_tests.append(test_case)

        if not has_sample or not has_hidden:
            raise CommandError(
                f"{problem_label} must contain at least one sample and one hidden test."
            )
        return validated_tests

    def _require_exact_fields(self, value, expected_fields, label):
        if not isinstance(value, dict):
            raise CommandError(f"{label} must be an object.")

        actual_fields = set(value)
        missing = expected_fields - actual_fields
        extra = actual_fields - expected_fields
        if missing:
            raise CommandError(f"{label}: missing fields: {', '.join(sorted(missing))}.")
        if extra:
            raise CommandError(f"{label}: unknown fields: {', '.join(sorted(extra))}.")

    def _require_text(self, value, label, max_length=None):
        if not isinstance(value, str) or not value.strip():
            raise CommandError(f"{label} must be a non-empty string.")
        if max_length is not None and len(value) > max_length:
            raise CommandError(f"{label} must not exceed {max_length} characters.")

    def _require_integer(self, value, label, minimum):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise CommandError(f"{label} must be an integer greater than or equal to {minimum}.")
