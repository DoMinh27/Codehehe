import copy
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from problems.management.commands.seed_problems import DEFAULT_DATA_FILE
from problems.models import Problem, TestCase as ProblemTestCase


class SeedProblemsCommandTests(TestCase):
    def test_default_seed_creates_thirty_problems_and_tests(self):
        output = StringIO()

        call_command("seed_problems", stdout=output)

        self.assertEqual(Problem.objects.count(), 30)
        self.assertEqual(ProblemTestCase.objects.count(), 270)
        self.assertFalse(
            Problem.objects.filter(reference_solution="").exists()
        )
        self.assertEqual(
            Problem.objects.filter(difficulty=Problem.Difficulty.EASY).count(),
            10,
        )
        self.assertEqual(
            Problem.objects.filter(difficulty=Problem.Difficulty.MEDIUM).count(),
            12,
        )
        self.assertEqual(
            Problem.objects.filter(difficulty=Problem.Difficulty.HARD).count(),
            8,
        )
        self.assertEqual(
            Problem.objects.filter(source_type=Problem.SourceType.ADAPTED).count(),
            14,
        )
        self.assertIn("30 created", output.getvalue())

    def test_rerun_updates_by_slug_without_duplicates(self):
        call_command("seed_problems", stdout=StringIO())
        payload = self._default_payload()
        payload["problems"][0]["title"] = "Tên mới của bài tính tổng"

        with self._temporary_seed(payload) as seed_file:
            output = StringIO()
            call_command("seed_problems", file=seed_file, stdout=output)

        self.assertEqual(Problem.objects.count(), 30)
        self.assertEqual(ProblemTestCase.objects.count(), 270)
        self.assertEqual(
            Problem.objects.get(slug="sum-two-numbers").title,
            "Tên mới của bài tính tổng",
        )
        self.assertIn("0 created, 30 updated", output.getvalue())

    def test_duplicate_slug_rejects_entire_file(self):
        payload = self._default_payload()
        duplicate = copy.deepcopy(payload["problems"][0])
        duplicate["title"] = "Một tiêu đề khác"
        payload["problems"].append(duplicate)

        with self._temporary_seed(payload) as seed_file:
            with self.assertRaisesMessage(CommandError, "duplicate slug"):
                call_command("seed_problems", file=seed_file, stdout=StringIO())

        self.assertFalse(Problem.objects.exists())

    def test_problem_requires_sample_and_hidden_tests(self):
        payload = self._default_payload()
        for test_case in payload["problems"][0]["test_cases"]:
            test_case["is_sample"] = False

        with self._temporary_seed(payload) as seed_file:
            with self.assertRaisesMessage(
                CommandError,
                "at least one sample and one hidden test",
            ):
                call_command("seed_problems", file=seed_file, stdout=StringIO())

        self.assertFalse(Problem.objects.exists())

    def test_active_problem_requires_reference_solution(self):
        payload = self._default_payload()
        payload["problems"][0]["reference_solution"] = ""

        with self._temporary_seed(payload) as seed_file:
            with self.assertRaisesMessage(
                CommandError,
                "reference_solution must be a non-empty string",
            ):
                call_command("seed_problems", file=seed_file, stdout=StringIO())

        self.assertFalse(Problem.objects.exists())

    def test_adapted_problem_requires_source_url(self):
        payload = self._default_payload()
        adapted = next(
            problem
            for problem in payload["problems"]
            if problem["source_type"] == "ADAPTED"
        )
        adapted["source_url"] = ""

        with self._temporary_seed(payload) as seed_file:
            with self.assertRaisesMessage(
                CommandError,
                "source_url must be provided for adapted problems",
            ):
                call_command("seed_problems", file=seed_file, stdout=StringIO())

        self.assertFalse(Problem.objects.exists())

    def test_seed_rejects_invalid_topic_and_source_url(self):
        cases = (
            ("primary_topic", "UNKNOWN", "primary_topic must be one of"),
            ("source_url", "not-a-url", "source_url must be a valid URL"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                payload = self._default_payload()
                adapted = next(
                    problem
                    for problem in payload["problems"]
                    if problem["source_type"] == "ADAPTED"
                )
                adapted[field] = value

                with self._temporary_seed(payload) as seed_file:
                    with self.assertRaisesMessage(CommandError, message):
                        call_command(
                            "seed_problems",
                            file=seed_file,
                            stdout=StringIO(),
                        )

                self.assertFalse(Problem.objects.exists())

    def test_version_two_seed_uses_safe_metadata_defaults(self):
        payload = self._default_payload()
        payload["version"] = 2
        metadata_fields = {
            "primary_topic",
            "source_type",
            "source_name",
            "source_url",
            "source_license",
        }
        for problem in payload["problems"]:
            for field in metadata_fields:
                problem.pop(field)

        with self._temporary_seed(payload) as seed_file:
            call_command("seed_problems", file=seed_file, stdout=StringIO())

        self.assertEqual(Problem.objects.count(), 30)
        self.assertFalse(
            Problem.objects.exclude(
                primary_topic=Problem.PrimaryTopic.OTHER,
                source_type=Problem.SourceType.ORIGINAL,
                source_name="CodeHehe",
                source_url="",
                source_license="CodeHehe original",
            ).exists()
        )

    def _default_payload(self):
        return json.loads(DEFAULT_DATA_FILE.read_text(encoding="utf-8"))

    def _temporary_seed(self, payload):
        class SeedFileContext:
            def __init__(self, data):
                self.data = data
                self.temporary_directory = TemporaryDirectory()

            def __enter__(self):
                directory = Path(self.temporary_directory.name)
                seed_file = directory / "problems.json"
                seed_file.write_text(
                    json.dumps(self.data, ensure_ascii=False),
                    encoding="utf-8",
                )
                return seed_file

            def __exit__(self, exc_type, exc_value, traceback):
                self.temporary_directory.cleanup()

        return SeedFileContext(payload)
