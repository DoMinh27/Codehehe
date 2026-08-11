from time import monotonic

from django.core.management.base import BaseCommand
from django.utils import timezone

from matches.models import Match
from matches.services.gameplay import FinishMatchService
from matches.services.scoring import ScoringService
from matches.services.submission import PendingSubmissionRecoveryService
from operations.models import WorkerHeartbeat
from operations.services.heartbeat import (
    heartbeat_error_code,
    record_worker_failure,
    record_worker_success,
)


class Command(BaseCommand):
    help = "Recover stale submissions and finalize eligible matches."

    def handle(self, *args, **options):
        started_at = monotonic()
        try:
            now = timezone.now()
            scoring_service = ScoringService()
            finish_service = FinishMatchService(scoring_service=scoring_service)
            recovered = PendingSubmissionRecoveryService(
                scoring_service=scoring_service,
            ).recover(now=now)

            finished = 0
            match_ids = list(
                Match.objects.filter(status=Match.Status.PLAYING).values_list(
                    "id", flat=True
                )
            )
            for match_id in match_ids:
                match = finish_service.try_finalize(match_id=match_id, now=now)
                if match is not None and match.status == Match.Status.FINISHED:
                    finished += 1
        except Exception as error:
            record_worker_failure(
                WorkerHeartbeat.Worker.MATCH_SWEEPER,
                error_code=heartbeat_error_code(error),
                duration_ms=_elapsed_ms(started_at),
            )
            raise

        record_worker_success(
            WorkerHeartbeat.Worker.MATCH_SWEEPER,
            duration_ms=_elapsed_ms(started_at),
            summary={"recovered": recovered, "finalized": finished},
            has_work=(recovered + finished) > 0,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Recovered {recovered} stale submission(s); "
                f"finished {finished} match(es)."
            )
        )


def _elapsed_ms(started_at):
    return max(0, round((monotonic() - started_at) * 1000))
