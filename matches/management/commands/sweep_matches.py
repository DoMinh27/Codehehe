from django.core.management.base import BaseCommand
from django.utils import timezone

from matches.models import Match
from matches.services.gameplay import FinishMatchService
from matches.services.scoring import ScoringService
from matches.services.submission import PendingSubmissionRecoveryService


class Command(BaseCommand):
    help = "Recover stale submissions and finalize eligible matches."

    def handle(self, *args, **options):
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

        self.stdout.write(
            self.style.SUCCESS(
                f"Recovered {recovered} stale submission(s); "
                f"finished {finished} match(es)."
            )
        )
