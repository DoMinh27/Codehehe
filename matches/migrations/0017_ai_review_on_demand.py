from django.db import migrations, models
import django.db.models.deletion


RETRYABLE_CODES = {
    "RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_SERVER_ERROR",
    "UNEXPECTED_PROVIDER_ERROR",
    "INVALID_PROVIDER_RESPONSE",
    "STALE_PROCESSING",
}
STATUS_PRIORITY = {
    "COMPLETED": 0,
    "PROCESSING": 1,
    "PENDING": 2,
    "FAILED": 3,
}


def backfill_progress(apps, schema_editor):
    Review = apps.get_model("matches", "SubmissionAIReview")
    Progress = apps.get_model("matches", "PlayerProblemProgress")

    progress_ids = {
        (progress.player_id, progress.match_problem_id): progress.id
        for progress in Progress.objects.all().only(
            "id", "player_id", "match_problem_id"
        )
    }
    grouped = {}
    reviews = Review.objects.select_related("submission").all()
    for review in reviews:
        key = (review.submission.player_id, review.submission.match_problem_id)
        grouped.setdefault(key, []).append(review)

    for key, candidates in grouped.items():
        candidates.sort(
            key=lambda review: (
                STATUS_PRIORITY.get(review.status, 99),
                -review.id,
            )
        )
        canonical = candidates[0]
        canonical.progress_id = progress_ids.get(key)
        canonical.failure_retryable = (
            canonical.status == "FAILED"
            and (
                canonical.error_code in RETRYABLE_CODES
                or canonical.error_code.startswith("PROVIDER_HTTP_5")
            )
        )
        canonical.save(update_fields=["progress", "failure_retryable"])

        for duplicate in candidates[1:]:
            duplicate.progress_id = None
            duplicate.status = "FAILED"
            duplicate.error_code = "DUPLICATE_SUPERSEDED"
            duplicate.failure_retryable = False
            duplicate.next_attempt_at = None
            duplicate.processing_started_at = None
            duplicate.save(
                update_fields=[
                    "progress",
                    "status",
                    "error_code",
                    "failure_retryable",
                    "next_attempt_at",
                    "processing_started_at",
                ]
            )


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0016_match_ai_review_enabled"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="submissionaireview",
            name="ai_review_submission_prompt_unique",
        ),
        migrations.AddField(
            model_name="submissionaireview",
            name="failure_retryable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="submissionaireview",
            name="manual_retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="submissionaireview",
            name="progress",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ai_review",
                to="matches.playerproblemprogress",
            ),
        ),
        migrations.CreateModel(
            name="AIReviewProviderThrottle",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(max_length=40, unique=True)),
                (
                    "next_allowed_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(backfill_progress, migrations.RunPython.noop),
    ]
