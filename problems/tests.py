from django.db import IntegrityError, transaction
from django.test import TestCase as DjangoTestCase

from .models import Problem, TestCase


class ProblemModelTests(DjangoTestCase):
    def test_problem_defaults_and_string_representation(self):
        problem = Problem.objects.create(
            slug="two-sum",
            title="Two Sum",
            statement="Return the sum.",
            difficulty=Problem.Difficulty.EASY,
            points=1,
        )

        self.assertEqual(str(problem), "Two Sum")
        self.assertTrue(problem.is_active)
        self.assertEqual(problem.order, 0)

    def test_problem_points_must_be_at_least_one(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Problem.objects.create(
                slug="invalid-problem",
                title="Invalid problem",
                statement="Invalid points.",
                difficulty=Problem.Difficulty.EASY,
                points=0,
            )


class TestCaseModelTests(DjangoTestCase):
    def test_problem_exposes_ordered_test_cases(self):
        problem = Problem.objects.create(
            slug="echo",
            title="Echo",
            statement="Print the input.",
            difficulty=Problem.Difficulty.EASY,
            points=1,
        )
        hidden = TestCase.objects.create(
            problem=problem,
            input_data="second",
            expected_output="second",
            is_sample=False,
            order=2,
        )
        sample = TestCase.objects.create(
            problem=problem,
            input_data="first",
            expected_output="first",
            is_sample=True,
            order=1,
        )

        self.assertEqual(list(problem.test_cases.all()), [sample, hidden])
        self.assertIn("sample", str(sample))
