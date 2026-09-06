import uuid

from django.conf import settings
from django.core.validators import validate_email
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class PlayerActivityDay(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_days",
    )
    activity_date = models.DateField()
    first_activity_at = models.DateTimeField()

    class Meta:
        ordering = ["-activity_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "activity_date"],
                name="player_activity_user_date_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["activity_date"],
                name="player_activity_date_idx",
            ),
            models.Index(
                fields=["user", "-activity_date"],
                name="player_activity_user_day_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} active on {self.activity_date}"


class AccountEmail(models.Model):
    """Unique, normalized email identity used for verification and recovery."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_email",
    )
    email = models.EmailField(unique=True)
    verified_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["email", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="account_email_lower_unique",
            ),
        ]

    @staticmethod
    def normalize(value):
        return (value or "").strip().lower()

    def clean(self):
        super().clean()
        self.email = self.normalize(self.email)
        validate_email(self.email)

    def save(self, *args, **kwargs):
        self.email = self.normalize(self.email)
        return super().save(*args, **kwargs)

    @property
    def is_verified(self):
        return self.verified_at is not None

    def __str__(self):
        return f"{self.user.username} <{self.email}>"


class PendingRegistration(models.Model):
    """Short-lived registration data that has not established an account yet."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128, editable=False)
    token_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    retained_until = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="pending_registration_lower_email_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="pending_registration_expiry_after_created",
            ),
            models.CheckConstraint(
                condition=models.Q(retained_until__gte=models.F("expires_at")),
                name="pending_registration_retention_after_expiry",
            ),
        ]

    def clean(self):
        super().clean()
        self.email = AccountEmail.normalize(self.email)
        validate_email(self.email)

    def save(self, *args, **kwargs):
        self.email = AccountEmail.normalize(self.email)
        return super().save(*args, **kwargs)

    @property
    def is_active(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return self.username
