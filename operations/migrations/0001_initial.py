from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WorkerHeartbeat",
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
                (
                    "worker",
                    models.CharField(
                        choices=[
                            ("AI_REVIEW", "AI review"),
                            ("MATCH_SWEEPER", "Match sweeper"),
                        ],
                        max_length=32,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OK", "OK"),
                            ("FAILED", "Failed"),
                            ("DISABLED", "Disabled"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("last_heartbeat_at", models.DateTimeField(db_index=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_failure_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_duration_ms",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("error_code", models.CharField(blank=True, max_length=64)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["worker"],
                "permissions": [
                    (
                        "view_operations_dashboard",
                        "Can view the operations dashboard",
                    ),
                ],
            },
        ),
    ]
