from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ProblemSlugMigrationTests(TransactionTestCase):
    migrate_from = [("problems", "0001_initial")]
    migrate_to = [("problems", "0004_enforce_problem_slug_unique")]

    def test_existing_problems_receive_unique_slugs(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        old_problem = old_apps.get_model("problems", "Problem")

        first = old_problem.objects.create(
            title="Bài giống nhau",
            statement="First",
            difficulty="EASY",
            points=1,
        )
        second = old_problem.objects.create(
            title="Bài giống nhau",
            statement="Second",
            difficulty="EASY",
            points=1,
        )
        fallback = old_problem.objects.create(
            title="!!!",
            statement="Fallback",
            difficulty="EASY",
            points=1,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        problem = new_apps.get_model("problems", "Problem")

        self.assertEqual(problem.objects.get(pk=first.pk).slug, "bai-giong-nhau")
        self.assertEqual(problem.objects.get(pk=second.pk).slug, "bai-giong-nhau-2")
        self.assertEqual(
            problem.objects.get(pk=fallback.pk).slug,
            f"problem-{fallback.pk}",
        )
        self.assertEqual(
            problem.objects.values_list("slug", flat=True).distinct().count(),
            3,
        )


class ProblemSourceMetadataMigrationTests(TransactionTestCase):
    migrate_from = [("problems", "0005_problem_reference_solution")]
    migrate_to = [("problems", "0006_problem_source_metadata")]

    def test_existing_problem_receives_safe_source_defaults(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        old_problem = old_apps.get_model("problems", "Problem")
        original = old_problem.objects.create(
            slug="existing-problem",
            title="Existing Problem",
            statement="Statement",
            difficulty="EASY",
            points=1,
            reference_solution="print(1)",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        problem = new_apps.get_model("problems", "Problem").objects.get(
            pk=original.pk
        )

        self.assertEqual(problem.primary_topic, "OTHER")
        self.assertEqual(problem.source_type, "ORIGINAL")
        self.assertEqual(problem.source_name, "CodeHehe")
        self.assertEqual(problem.source_url, "")
        self.assertEqual(problem.source_license, "CodeHehe original")
