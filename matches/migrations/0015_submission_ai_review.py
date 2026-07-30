import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0014_matchproblem_reference_solution_snapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubmissionAIReview",
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
                ("prompt_version", models.CharField(max_length=40)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("provider", models.CharField(default="groq", max_length=40)),
                ("model", models.CharField(max_length=100)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                (
                    "next_attempt_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "processing_started_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("input_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("output_tokens", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "reasoning_tokens",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("error_code", models.CharField(blank=True, max_length=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "submission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_reviews",
                        to="matches.submission",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["status", "next_attempt_at"],
                        name="ai_review_due_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("submission", "prompt_version"),
                        name="ai_review_submission_prompt_unique",
                    ),
                ],
            },
        ),
    ]
