from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase as DjangoTestCase
from django.urls import reverse
from django.utils.html import escape

from .admin import ProblemAdminForm
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
        self.assertEqual(problem.primary_topic, Problem.PrimaryTopic.OTHER)
        self.assertEqual(problem.source_type, Problem.SourceType.ORIGINAL)
        self.assertEqual(problem.source_name, "CodeHehe")
        self.assertEqual(problem.source_url, "")
        self.assertEqual(problem.source_license, "CodeHehe original")

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


class ProblemAdminFormTests(DjangoTestCase):
    def test_adapted_problem_requires_complete_source_metadata(self):
        form = ProblemAdminForm(
            data={
                "slug": "adapted-problem",
                "title": "Adapted Problem",
                "statement": "Statement",
                "difficulty": Problem.Difficulty.EASY,
                "points": 1,
                "starter_code": "",
                "reference_solution": "print(1)",
                "primary_topic": Problem.PrimaryTopic.BASICS,
                "source_type": Problem.SourceType.ADAPTED,
                "source_name": "",
                "source_url": "",
                "source_license": "",
                "order": 1,
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("source_name", form.errors)
        self.assertIn("source_url", form.errors)
        self.assertIn("source_license", form.errors)

    def test_original_problem_accepts_blank_source_url(self):
        form = ProblemAdminForm(
            data={
                "slug": "original-problem",
                "title": "Original Problem",
                "statement": "Statement",
                "difficulty": Problem.Difficulty.EASY,
                "points": 1,
                "starter_code": "",
                "reference_solution": "print(1)",
                "primary_topic": Problem.PrimaryTopic.BASICS,
                "source_type": Problem.SourceType.ORIGINAL,
                "source_name": "CodeHehe",
                "source_url": "",
                "source_license": "CodeHehe original",
                "order": 1,
                "is_active": True,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)


class ProblemPageTests(DjangoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="player",
            password="SafePassword-938!",
        )
        self.problem = Problem.objects.create(
            slug="visible-problem",
            title="Visible Problem",
            statement="Solve the visible problem.",
            difficulty=Problem.Difficulty.MEDIUM,
            points=2,
            starter_code="print('starter code')",
            order=2,
        )
        self.first_problem = Problem.objects.create(
            slug="first-problem",
            title="First Problem",
            statement="This problem appears first.",
            difficulty=Problem.Difficulty.EASY,
            points=1,
            order=1,
        )
        self.inactive_problem = Problem.objects.create(
            slug="inactive-problem",
            title="Inactive Problem",
            statement="This problem is inactive.",
            difficulty=Problem.Difficulty.HARD,
            points=3,
            order=0,
            is_active=False,
        )
        TestCase.objects.create(
            problem=self.problem,
            input_data="sample-input-visible",
            expected_output="sample-output-visible",
            is_sample=True,
            order=1,
        )
        TestCase.objects.create(
            problem=self.problem,
            input_data="hidden-input-secret",
            expected_output="hidden-output-secret",
            is_sample=False,
            order=2,
        )

    def test_problem_pages_require_login(self):
        urls = [
            reverse("problem-list"),
            reverse("problem-detail", args=[self.problem.slug]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_problem_list_shows_only_active_problems_in_order(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("problem-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "problems/problem_list.html")
        self.assertEqual(
            list(response.context["problems"]),
            [self.first_problem, self.problem],
        )
        self.assertNotContains(response, self.inactive_problem.title)

    def test_problem_list_shows_empty_state(self):
        Problem.objects.all().delete()
        self.client.force_login(self.user)

        response = self.client.get(reverse("problem-list"))

        self.assertContains(response, "Hiện chưa có bài tập nào")

    def test_problem_detail_uses_slug_and_shows_problem_content(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("problem-detail", args=[self.problem.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "problems/problem_detail.html")
        self.assertContains(response, self.problem.title)
        self.assertContains(response, self.problem.statement)
        self.assertContains(response, escape(self.problem.starter_code))
        self.assertContains(response, "Medium")
        self.assertContains(response, "2")

    def test_problem_detail_exposes_samples_but_not_hidden_tests(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("problem-detail", args=[self.problem.slug])
        )

        self.assertContains(response, "sample-input-visible")
        self.assertContains(response, "sample-output-visible")
        self.assertNotContains(response, "hidden-input-secret")
        self.assertNotContains(response, "hidden-output-secret")
        self.assertEqual(
            [test_case.is_sample for test_case in response.context["problem"].sample_tests],
            [True],
        )

    def test_problem_pages_do_not_expose_source_metadata(self):
        self.problem.source_type = Problem.SourceType.ADAPTED
        self.problem.source_name = "private-source-name"
        self.problem.source_url = "https://example.com/private-source-url"
        self.problem.source_license = "private-license-label"
        self.problem.save(
            update_fields=(
                "source_type",
                "source_name",
                "source_url",
                "source_license",
            )
        )
        self.client.force_login(self.user)

        for url in (
            reverse("problem-list"),
            reverse("problem-detail", args=[self.problem.slug]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, "private-source-name")
                self.assertNotContains(response, "private-source-url")
                self.assertNotContains(response, "private-license-label")

    def test_problem_detail_returns_404_for_inactive_or_unknown_slug(self):
        self.client.force_login(self.user)
        slugs = [self.inactive_problem.slug, "unknown-problem"]

        for slug in slugs:
            with self.subTest(slug=slug):
                response = self.client.get(
                    reverse("problem-detail", args=[slug])
                )
                self.assertEqual(response.status_code, 404)
