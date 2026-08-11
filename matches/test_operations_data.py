from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import PlayerActivityDay

from .models import Match, SubmissionAIReview


class OperationsDataIntegrityTests(TestCase):
    def test_cancelled_match_backfill_uses_last_known_update_time(self):
        host = get_user_model().objects.create_user(username="cancelled-host")
        match = Match.objects.create(
            room_code="BACK19",
            host=host,
            status=Match.Status.CANCELLED,
        )
        cancellation_time = timezone.now() - timedelta(days=2)
        Match.objects.filter(pk=match.pk).update(
            ended_at=None,
            updated_at=cancellation_time,
        )

        migration = import_module(
            "matches.migrations.0019_operations_dashboard_integrity_indexes"
        )
        migration.backfill_cancelled_match_ended_at(apps, None)

        match.refresh_from_db()
        self.assertEqual(match.ended_at, cancellation_time)

    def test_dashboard_query_indexes_are_declared_on_models(self):
        activity_indexes = {
            index.name: tuple(index.fields)
            for index in PlayerActivityDay._meta.indexes
        }
        review_indexes = {
            index.name: tuple(index.fields)
            for index in SubmissionAIReview._meta.indexes
        }

        self.assertEqual(
            activity_indexes["player_activity_date_idx"],
            ("activity_date",),
        )
        self.assertEqual(
            review_indexes["ai_review_status_updated_idx"],
            ("status", "updated_at"),
        )
        self.assertEqual(
            review_indexes["ai_review_completed_idx"],
            ("completed_at",),
        )
