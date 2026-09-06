import hashlib
import hmac
import ipaddress
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from matches.services.db import retry_transient_db_lock
from matches.services.rate_limit import is_rate_limited

from .models import AccountEmail, PendingRegistration
from .registration_services import purge_retained_pending_registrations


logger = logging.getLogger(__name__)
User = get_user_model()
EMAIL_VERIFICATION_SALT = "accounts.email-verification.v2"


@dataclass(frozen=True)
class VerificationLookup:
    status: str
    pending_registration: PendingRegistration | None = None
    account_email: AccountEmail | None = None


def _email_identity(email):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        AccountEmail.normalize(email).encode(),
        hashlib.sha256,
    ).hexdigest()


def _client_identity(request):
    remote_address = request.META.get("REMOTE_ADDR", "")
    try:
        remote_ip = ipaddress.ip_address(remote_address)
    except ValueError:
        return "unknown"
    if remote_ip.is_loopback:
        real_address = request.META.get("HTTP_X_REAL_IP", "")
        try:
            return str(ipaddress.ip_address(real_address))
        except ValueError:
            pass
    return str(remote_ip)


def email_request_is_limited(*, request, email, scope):
    window = settings.ACCOUNT_EMAIL_RATE_LIMIT_WINDOW_SECONDS
    address_limited = is_rate_limited(
        scope=f"account-email:{scope}:address",
        identity=_email_identity(email),
        limit=settings.ACCOUNT_EMAIL_RATE_LIMIT_PER_ADDRESS,
        window_seconds=window,
    )
    ip_limited = is_rate_limited(
        scope=f"account-email:{scope}:ip",
        identity=_client_identity(request),
        limit=settings.ACCOUNT_EMAIL_RATE_LIMIT_PER_IP,
        window_seconds=window,
    )
    return address_limited or ip_limited


def make_verification_token(pending_registration):
    return signing.dumps(
        {
            "pending_id": str(pending_registration.pk),
            "nonce": str(pending_registration.token_nonce),
        },
        salt=EMAIL_VERIFICATION_SALT,
        compress=True,
    )


def _decode_verification_token(token):
    try:
        payload = signing.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=settings.EMAIL_VERIFICATION_TIMEOUT_SECONDS,
        )
    except signing.SignatureExpired:
        return "expired", None
    except signing.BadSignature:
        return "invalid", None
    if not isinstance(payload, dict) or set(payload) != {"pending_id", "nonce"}:
        return "invalid", None
    try:
        pending_id = uuid.UUID(payload["pending_id"])
        nonce = uuid.UUID(payload["nonce"])
    except (AttributeError, TypeError, ValueError):
        return "invalid", None
    return "valid", (pending_id, nonce)


def inspect_verification_token(token, *, now=None):
    status, identity = _decode_verification_token(token)
    if status != "valid":
        return VerificationLookup(status=status)
    current_time = now or timezone.now()
    pending_id, nonce = identity
    pending = PendingRegistration.objects.filter(pk=pending_id).first()
    if pending is None or pending.token_nonce != nonce:
        return VerificationLookup(status="invalid")
    if pending.expires_at <= current_time:
        return VerificationLookup(status="expired", pending_registration=pending)
    return VerificationLookup(status="valid", pending_registration=pending)


def _confirm_verification_token(token, *, now=None):
    status, identity = _decode_verification_token(token)
    if status != "valid":
        return VerificationLookup(status=status)
    current_time = now or timezone.now()
    pending_id, nonce = identity
    try:
        with transaction.atomic():
            pending = PendingRegistration.objects.select_for_update().filter(
                pk=pending_id
            ).first()
            if pending is None or pending.token_nonce != nonce:
                return VerificationLookup(status="invalid")
            if pending.expires_at <= current_time:
                return VerificationLookup(
                    status="expired",
                    pending_registration=pending,
                )
            if User.objects.filter(username=pending.username).exists():
                return VerificationLookup(status="conflict")
            if AccountEmail.objects.filter(email=pending.email).exists():
                return VerificationLookup(status="conflict")

            user = User.objects.create(
                username=pending.username,
                email=pending.email,
                password=pending.password_hash,
                is_active=True,
            )
            account_email = AccountEmail.objects.create(
                user=user,
                email=pending.email,
                verified_at=current_time,
            )
            pending.delete()
    except IntegrityError:
        return VerificationLookup(status="conflict")
    return VerificationLookup(status="verified", account_email=account_email)


def confirm_verification_token(token, *, now=None):
    return retry_transient_db_lock(
        lambda: _confirm_verification_token(token, now=now),
        attempts=7,
    )


def send_verification_email(*, request, pending_registration):
    token = make_verification_token(pending_registration)
    verification_url = request.build_absolute_uri(
        reverse("email-verification-confirm", kwargs={"token": token})
    )
    context = {
        "username": pending_registration.username,
        "verification_url": verification_url,
        "expires_minutes": max(
            1,
            settings.EMAIL_VERIFICATION_TIMEOUT_SECONDS // 60,
        ),
    }
    try:
        subject = "".join(
            render_to_string(
                "registration/email_verification_subject.txt",
                context,
            ).splitlines()
        )
        body = render_to_string("registration/email_verification_email.txt", context)
        html_body = render_to_string(
            "registration/email_verification_email.html",
            context,
        )
        message = EmailMultiAlternatives(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [pending_registration.email],
        )
        message.attach_alternative(html_body, "text/html")
        message.send()
    except Exception as error:  # SMTP is an external boundary.
        logger.warning(
            "Account verification email delivery failed (%s)",
            type(error).__name__,
        )
        return False
    return True


def resend_verification_email(*, request, email, now=None):
    normalized_email = AccountEmail.normalize(email)
    if email_request_is_limited(
        request=request,
        email=normalized_email,
        scope="verification",
    ):
        return False
    current_time = now or timezone.now()
    purge_retained_pending_registrations(now=current_time)
    with transaction.atomic():
        pending = (
            PendingRegistration.objects.select_for_update()
            .filter(
                email=normalized_email,
                retained_until__gt=current_time,
            )
            .first()
        )
        if pending is None:
            return False
        if User.objects.filter(username=pending.username).exists():
            pending.delete()
            return False
        if AccountEmail.objects.filter(email=pending.email).exists():
            pending.delete()
            return False
        pending.token_nonce = uuid.uuid4()
        pending.expires_at = min(
            current_time
            + timedelta(seconds=settings.EMAIL_VERIFICATION_TIMEOUT_SECONDS),
            pending.retained_until,
        )
        if pending.expires_at <= current_time:
            return False
        pending.save(update_fields=["token_nonce", "expires_at"])
    return send_verification_email(
        request=request,
        pending_registration=pending,
    )
