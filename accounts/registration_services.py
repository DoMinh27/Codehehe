import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from matches.services.db import retry_transient_db_lock

from .models import AccountEmail, PendingRegistration


User = get_user_model()


@dataclass(frozen=True)
class PendingRegistrationConflict(Exception):
    field: str
    code: str


def purge_retained_pending_registrations(*, now=None):
    current_time = now or timezone.now()
    return PendingRegistration.objects.filter(
        retained_until__lte=current_time
    ).delete()[0]


def _account_conflict(*, username, email):
    if User.objects.filter(username=username).exists():
        return PendingRegistrationConflict("username", "ACCOUNT_EXISTS")
    if AccountEmail.objects.filter(email=email).exists():
        return PendingRegistrationConflict("email", "ACCOUNT_EXISTS")
    return None


@transaction.atomic
def _create_pending_registration(*, username, email, password_hash, now=None):
    current_time = now or timezone.now()
    normalized_email = AccountEmail.normalize(email)
    purge_retained_pending_registrations(now=current_time)

    conflict = _account_conflict(username=username, email=normalized_email)
    if conflict:
        raise conflict

    conflicting_rows = list(
        PendingRegistration.objects.select_for_update().filter(
            Q(username=username) | Q(email=normalized_email)
        )
    )
    active_rows = [row for row in conflicting_rows if row.expires_at > current_time]
    if active_rows:
        field = (
            "username"
            if any(row.username == username for row in active_rows)
            else "email"
        )
        raise PendingRegistrationConflict(field, "PENDING_ACTIVE")

    if conflicting_rows:
        PendingRegistration.objects.filter(
            pk__in=[row.pk for row in conflicting_rows]
        ).delete()

    verification_lifetime = timedelta(
        seconds=settings.EMAIL_VERIFICATION_TIMEOUT_SECONDS
    )
    retention_lifetime = timedelta(
        seconds=settings.PENDING_REGISTRATION_RETENTION_SECONDS
    )
    try:
        with transaction.atomic():
            return PendingRegistration.objects.create(
                username=username,
                email=normalized_email,
                password_hash=password_hash,
                token_nonce=uuid.uuid4(),
                created_at=current_time,
                expires_at=current_time + verification_lifetime,
                retained_until=current_time + retention_lifetime,
            )
    except IntegrityError as error:
        conflict = _account_conflict(username=username, email=normalized_email)
        if conflict:
            raise conflict from error
        raise PendingRegistrationConflict("email", "PENDING_ACTIVE") from error


def create_pending_registration(*, username, email, password_hash, now=None):
    return retry_transient_db_lock(
        lambda: _create_pending_registration(
            username=username,
            email=email,
            password_hash=password_hash,
            now=now,
        ),
        attempts=7,
    )
