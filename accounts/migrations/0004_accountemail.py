from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.text
from django.utils import timezone


def backfill_account_emails(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    user_model = apps.get_model(app_label, model_name)
    account_email_model = apps.get_model("accounts", "AccountEmail")
    seen = {}

    for user in user_model.objects.exclude(email="").order_by("id"):
        normalized = user.email.strip().lower()
        if not normalized:
            continue
        if normalized in seen:
            first_user_id = seen[normalized]
            raise RuntimeError(
                "Duplicate non-empty account email for user IDs "
                f"{first_user_id} and {user.pk}. Resolve duplicates before migrating."
            )
        seen[normalized] = user.pk
        account_email_model.objects.create(
            user_id=user.pk,
            email=normalized,
            verified_at=timezone.now(),
        )
        if user.email != normalized:
            user_model.objects.filter(pk=user.pk).update(email=normalized)


def remove_backfilled_account_emails(apps, schema_editor):
    account_email_model = apps.get_model("accounts", "AccountEmail")
    account_email_model.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_playeractivityday_activity_date_index"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountEmail",
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
                ("email", models.EmailField(max_length=254, unique=True)),
                (
                    "verified_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account_email",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["email", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("email"),
                        name="account_email_lower_unique",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            backfill_account_emails,
            remove_backfilled_account_emails,
        ),
    ]
