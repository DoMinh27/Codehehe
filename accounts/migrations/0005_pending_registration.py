import uuid
from datetime import timedelta

from django.conf import settings
from django.db import migrations, models
import django.db.models.functions.text
from django.utils import timezone


VERIFICATION_LIFETIME = timedelta(minutes=5)
RETENTION_LIFETIME = timedelta(hours=2)


def move_unverified_users_to_pending(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    user_model = apps.get_model(app_label, model_name)
    account_email_model = apps.get_model("accounts", "AccountEmail")
    pending_model = apps.get_model("accounts", "PendingRegistration")
    current_time = timezone.now()

    rows = account_email_model.objects.filter(verified_at__isnull=True).order_by(
        "user_id"
    )
    for account_email in rows.iterator():
        user = user_model.objects.get(pk=account_email.user_id)
        if user.is_active:
            raise RuntimeError(
                "An active user has an unverified AccountEmail. "
                "Resolve inconsistent account data before migrating."
            )
        created_at = user.date_joined
        retained_until = created_at + RETENTION_LIFETIME
        if retained_until > current_time:
            pending_model.objects.create(
                username=user.username,
                email=account_email.email.strip().lower(),
                password_hash=user.password,
                token_nonce=uuid.uuid4(),
                created_at=created_at,
                expires_at=created_at + VERIFICATION_LIFETIME,
                retained_until=retained_until,
            )
        user.delete()


def restore_unverified_users(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    user_model = apps.get_model(app_label, model_name)
    account_email_model = apps.get_model("accounts", "AccountEmail")
    pending_model = apps.get_model("accounts", "PendingRegistration")

    for pending in pending_model.objects.order_by("created_at").iterator():
        if user_model.objects.filter(username=pending.username).exists():
            continue
        user = user_model.objects.create(
            username=pending.username,
            email=pending.email,
            password=pending.password_hash,
            is_active=False,
            date_joined=pending.created_at,
        )
        account_email_model.objects.create(
            user_id=user.pk,
            email=pending.email,
            verified_at=None,
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_accountemail")]

    operations = [
        migrations.CreateModel(
            name="PendingRegistration",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("username", models.CharField(max_length=150, unique=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password_hash", models.CharField(editable=False, max_length=128)),
                ("token_nonce", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("retained_until", models.DateTimeField(db_index=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("email"),
                        name="pending_registration_lower_email_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(expires_at__gt=models.F("created_at")),
                        name="pending_registration_expiry_after_created",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            retained_until__gte=models.F("expires_at")
                        ),
                        name="pending_registration_retention_after_expiry",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            move_unverified_users_to_pending,
            restore_unverified_users,
        ),
        migrations.AlterField(
            model_name="accountemail",
            name="verified_at",
            field=models.DateTimeField(db_index=True),
        ),
    ]
