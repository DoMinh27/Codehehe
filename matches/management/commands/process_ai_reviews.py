from time import monotonic

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from matches.services.ai_review import (
    AIReviewConfigurationError,
    AIReviewProcessor,
    ai_review_provider_from_environment,
)
from operations.models import WorkerHeartbeat
from operations.services.heartbeat import (
    heartbeat_error_code,
    record_worker_disabled,
    record_worker_failure,
    record_worker_success,
)


class Command(BaseCommand):
    help = "Process queued post-match AI submission reviews."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        started_at = monotonic()
        try:
            limit = options["limit"]
            if limit < 1:
                raise CommandError("--limit must be greater than zero.")
            if not settings.AI_REVIEW_ENABLED:
                record_worker_disabled(
                    WorkerHeartbeat.Worker.AI_REVIEW,
                    duration_ms=_elapsed_ms(started_at),
                )
                self.stdout.write("AI review processing is disabled.")
                return
            provider = ai_review_provider_from_environment()
            processed = AIReviewProcessor(provider).process_due(limit=limit)
        except AIReviewConfigurationError as error:
            record_worker_failure(
                WorkerHeartbeat.Worker.AI_REVIEW,
                error_code=heartbeat_error_code(error),
                duration_ms=_elapsed_ms(started_at),
            )
            raise CommandError(str(error)) from error
        except Exception as error:
            record_worker_failure(
                WorkerHeartbeat.Worker.AI_REVIEW,
                error_code=heartbeat_error_code(error),
                duration_ms=_elapsed_ms(started_at),
            )
            raise

        record_worker_success(
            WorkerHeartbeat.Worker.AI_REVIEW,
            duration_ms=_elapsed_ms(started_at),
            summary={"processed": processed},
            has_work=processed > 0,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Processed {processed} AI review job(s).")
        )


def _elapsed_ms(started_at):
    return max(0, round((monotonic() - started_at) * 1000))
