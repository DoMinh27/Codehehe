import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.core.management import CommandError, call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from matches.services.ai_review import AIReviewConfigurationError
from operations.admin import WorkerHeartbeatAdmin
from operations.models import WorkerHeartbeat
from operations.services.heartbeat import (
    heartbeat_error_code,
    record_worker_disabled,
    record_worker_failure,
    record_worker_success,
)


class WorkerHeartbeatServiceTests(TestCase):
    def test_success_creates_heartbeat_with_safe_summary(self):
        recorded_at = timezone.now()

        written = record_worker_success(
            WorkerHeartbeat.Worker.AI_REVIEW,
            duration_ms=19,
            summary={"processed": 2},
            has_work=True,
            at=recorded_at,
        )

        self.assertTrue(written)
        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.OK)
        self.assertEqual(heartbeat.last_heartbeat_at, recorded_at)
        self.assertEqual(heartbeat.last_success_at, recorded_at)
        self.assertIsNone(heartbeat.last_failure_at)
        self.assertEqual(heartbeat.last_duration_ms, 19)
        self.assertEqual(heartbeat.summary, {"processed": 2})
        self.assertEqual(heartbeat.error_code, "")

    def test_idle_success_is_written_at_most_once_per_minute(self):
        first_at = timezone.now()
        record_worker_success(
            WorkerHeartbeat.Worker.MATCH_SWEEPER,
            duration_ms=4,
            summary={"recovered": 0, "finalized": 0},
            has_work=False,
            at=first_at,
        )

        skipped = record_worker_success(
            WorkerHeartbeat.Worker.MATCH_SWEEPER,
            duration_ms=5,
            summary={"recovered": 0, "finalized": 0},
            has_work=False,
            at=first_at + timedelta(seconds=59),
        )
        written = record_worker_success(
            WorkerHeartbeat.Worker.MATCH_SWEEPER,
            duration_ms=6,
            summary={"recovered": 0, "finalized": 0},
            has_work=False,
            at=first_at + timedelta(seconds=60),
        )

        self.assertFalse(skipped)
        self.assertTrue(written)
        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.MATCH_SWEEPER
        )
        self.assertEqual(
            heartbeat.last_heartbeat_at,
            first_at + timedelta(seconds=60),
        )
        self.assertEqual(heartbeat.last_duration_ms, 6)

    def test_work_and_status_changes_bypass_idle_throttle(self):
        first_at = timezone.now()
        record_worker_success(
            WorkerHeartbeat.Worker.AI_REVIEW,
            duration_ms=1,
            summary={"processed": 0},
            has_work=False,
            at=first_at,
        )

        work_written = record_worker_success(
            WorkerHeartbeat.Worker.AI_REVIEW,
            duration_ms=2,
            summary={"processed": 1},
            has_work=True,
            at=first_at + timedelta(seconds=1),
        )
        disabled_written = record_worker_disabled(
            WorkerHeartbeat.Worker.AI_REVIEW,
            duration_ms=3,
            at=first_at + timedelta(seconds=2),
        )

        self.assertTrue(work_written)
        self.assertTrue(disabled_written)
        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.DISABLED)
        self.assertEqual(
            heartbeat.last_heartbeat_at,
            first_at + timedelta(seconds=2),
        )

    def test_failure_is_immediate_and_preserves_last_success(self):
        first_at = timezone.now()
        failed_at = first_at + timedelta(seconds=1)
        record_worker_success(
            WorkerHeartbeat.Worker.AI_REVIEW,
            duration_ms=8,
            summary={"processed": 0},
            has_work=False,
            at=first_at,
        )

        written = record_worker_failure(
            WorkerHeartbeat.Worker.AI_REVIEW,
            error_code="provider timeout: secret details are removed",
            duration_ms=12,
            at=failed_at,
        )

        self.assertTrue(written)
        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.FAILED)
        self.assertEqual(heartbeat.last_success_at, first_at)
        self.assertEqual(heartbeat.last_failure_at, failed_at)
        self.assertEqual(
            heartbeat.error_code,
            "PROVIDER_TIMEOUT_SECRET_DETAILS_ARE_REMOVED",
        )

    def test_summary_rejects_non_count_or_unapproved_values(self):
        with self.assertRaises(ValueError):
            record_worker_success(
                WorkerHeartbeat.Worker.AI_REVIEW,
                duration_ms=1,
                summary={"source_code": 1},
                has_work=True,
            )
        with self.assertRaises(ValueError):
            record_worker_success(
                WorkerHeartbeat.Worker.AI_REVIEW,
                duration_ms=1,
                summary={"processed": True},
                has_work=True,
            )

    def test_exception_type_becomes_stable_error_code(self):
        self.assertEqual(
            heartbeat_error_code(AIReviewConfigurationError("secret")),
            "AI_REVIEW_CONFIGURATION_ERROR",
        )


class WorkerHeartbeatCommandTests(TestCase):
    @override_settings(AI_REVIEW_ENABLED=False)
    def test_disabled_ai_processor_records_disabled_heartbeat(self):
        output = io.StringIO()

        call_command("process_ai_reviews", stdout=output)

        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.DISABLED)
        self.assertIsNone(heartbeat.last_success_at)
        self.assertEqual(heartbeat.summary, {})
        self.assertIn("disabled", output.getvalue())

    @override_settings(AI_REVIEW_ENABLED=True)
    @patch(
        "matches.management.commands.process_ai_reviews."
        "ai_review_provider_from_environment"
    )
    @patch("matches.management.commands.process_ai_reviews.AIReviewProcessor")
    def test_ai_processor_success_records_processed_count(
        self,
        processor_class,
        provider_factory,
    ):
        provider = object()
        provider_factory.return_value = provider
        processor_class.return_value.process_due.return_value = 2

        call_command("process_ai_reviews", limit=10, stdout=io.StringIO())

        processor_class.assert_called_once_with(provider)
        processor_class.return_value.process_due.assert_called_once_with(limit=10)
        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.OK)
        self.assertEqual(heartbeat.summary, {"processed": 2})

    @override_settings(AI_REVIEW_ENABLED=True)
    @patch(
        "matches.management.commands.process_ai_reviews."
        "ai_review_provider_from_environment",
        side_effect=AIReviewConfigurationError("API key is missing"),
    )
    def test_ai_configuration_failure_is_recorded_and_reraised(self, _factory):
        with self.assertRaises(CommandError):
            call_command("process_ai_reviews", stdout=io.StringIO())

        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.FAILED)
        self.assertEqual(
            heartbeat.error_code,
            "AI_REVIEW_CONFIGURATION_ERROR",
        )
        self.assertNotIn("API key", heartbeat.error_code)

    @override_settings(AI_REVIEW_ENABLED=True)
    @patch(
        "matches.management.commands.process_ai_reviews."
        "ai_review_provider_from_environment",
        return_value=object(),
    )
    @patch("matches.management.commands.process_ai_reviews.AIReviewProcessor")
    def test_ai_processor_runtime_failure_is_recorded_and_reraised(
        self,
        processor_class,
        _provider_factory,
    ):
        processor_class.return_value.process_due.side_effect = RuntimeError(
            "provider response includes sensitive text"
        )

        with self.assertRaisesRegex(RuntimeError, "sensitive text"):
            call_command("process_ai_reviews", stdout=io.StringIO())

        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.AI_REVIEW
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.FAILED)
        self.assertEqual(heartbeat.error_code, "RUNTIME_ERROR")

    def test_sweeper_success_records_counts(self):
        output = io.StringIO()

        call_command("sweep_matches", stdout=output)

        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.MATCH_SWEEPER
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.OK)
        self.assertEqual(heartbeat.summary, {"recovered": 0, "finalized": 0})
        self.assertIn("Recovered 0", output.getvalue())

    @patch(
        "matches.management.commands.sweep_matches."
        "PendingSubmissionRecoveryService"
    )
    def test_sweeper_failure_is_recorded_and_reraised(self, recovery_class):
        recovery_class.return_value.recover.side_effect = RuntimeError(
            "database details must not be stored"
        )

        with self.assertRaisesRegex(RuntimeError, "database details"):
            call_command("sweep_matches", stdout=io.StringIO())

        heartbeat = WorkerHeartbeat.objects.get(
            worker=WorkerHeartbeat.Worker.MATCH_SWEEPER
        )
        self.assertEqual(heartbeat.status, WorkerHeartbeat.Status.FAILED)
        self.assertEqual(heartbeat.error_code, "RUNTIME_ERROR")
        self.assertEqual(heartbeat.summary, {})


class WorkerHeartbeatAdminTests(TestCase):
    def test_admin_is_strictly_read_only(self):
        model_admin = WorkerHeartbeatAdmin(WorkerHeartbeat, admin.site)
        request = RequestFactory().get("/admin/operations/workerheartbeat/")

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
