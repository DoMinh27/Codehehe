from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from matches.services.ai_review import (
    AIReviewConfigurationError,
    AIReviewProcessor,
    ai_review_provider_from_environment,
)


class Command(BaseCommand):
    help = "Process queued post-match AI submission reviews."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1:
            raise CommandError("--limit must be greater than zero.")
        if not settings.AI_REVIEW_ENABLED:
            self.stdout.write("AI review processing is disabled.")
            return
        try:
            provider = ai_review_provider_from_environment()
        except AIReviewConfigurationError as error:
            raise CommandError(str(error)) from error
        processed = AIReviewProcessor(provider).process_due(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(f"Processed {processed} AI review job(s).")
        )
