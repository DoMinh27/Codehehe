import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0021_match_event_timeline"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RematchRequest",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Đang chờ"),
                            ("ACCEPTED", "Đã đồng ý"),
                            ("DECLINED", "Đã từ chối"),
                            ("CANCELLED", "Đã hủy"),
                        ],
                        default="PENDING",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField()),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "match",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rematch_request",
                        to="matches.match",
                    ),
                ),
                (
                    "new_match",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rematch_origin",
                        to="matches.match",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rematch_invitations_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rematch_invitations_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(requester=models.F("recipient")),
                        name="rematch_distinct_users",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(expires_at__gt=models.F("created_at")),
                        name="rematch_valid_expiry",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(status="ACCEPTED", new_match__isnull=False)
                        | (
                            ~models.Q(status="ACCEPTED")
                            & models.Q(new_match__isnull=True)
                        ),
                        name="rematch_accepted_has_match",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(status="PENDING", responded_at__isnull=True)
                        | (
                            ~models.Q(status="PENDING")
                            & models.Q(responded_at__isnull=False)
                        ),
                        name="rematch_response_state",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(match=models.F("new_match")),
                        name="rematch_different_match",
                    ),
                ],
            },
        ),
    ]
