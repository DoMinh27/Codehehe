import importlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from urllib.parse import urlparse
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.db.migrations.executor import MigrationExecutor
from django.test import (
    Client,
    RequestFactory,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.urls import reverse
from django.utils import timezone

from .email_services import (
    confirm_verification_token,
    inspect_verification_token,
    make_verification_token,
    resend_verification_email,
)
from .models import AccountEmail, PendingRegistration
from .registration_services import (
    PendingRegistrationConflict,
    create_pending_registration,
)


User = get_user_model()


def path_from_message(message):
    match = re.search(r"https?://[^\s<]+", message.body)
    if not match:
        raise AssertionError("Email does not contain an absolute URL")
    return urlparse(match.group(0)).path


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="CodeHehe <no-reply@example.com>",
    EMAIL_VERIFICATION_TIMEOUT_SECONDS=300,
    PENDING_REGISTRATION_RETENTION_SECONDS=7200,
    PASSWORD_RESET_TIMEOUT=3600,
    ACCOUNT_EMAIL_RATE_LIMIT_WINDOW_SECONDS=3600,
    ACCOUNT_EMAIL_RATE_LIMIT_PER_IP=10,
    ACCOUNT_EMAIL_RATE_LIMIT_PER_ADDRESS=3,
)
class EmailVerificationTests(TestCase):
    password = "SafePassword-938!"

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def register(self, *, username="new-player", email="Player@Example.com"):
        return self.client.post(
            reverse("register"),
            {
                "username": username,
                "email": email,
                "password1": self.password,
                "password2": self.password,
            },
        )

    def test_registration_creates_pending_record_and_sends_verification(self):
        response = self.register()

        self.assertRedirects(response, reverse("email-verification-sent"))
        self.assertFalse(User.objects.filter(username="new-player").exists())
        self.assertFalse(AccountEmail.objects.exists())
        pending = PendingRegistration.objects.get(username="new-player")
        self.assertEqual(pending.email, "player@example.com")
        self.assertNotEqual(pending.password_hash, self.password)
        self.assertTrue(check_password(self.password, pending.password_hash))
        self.assertEqual(len(mail.outbox), 1)

    def test_active_pending_registration_is_not_replaced_or_extended(self):
        self.register()
        pending = PendingRegistration.objects.get(username="new-player")
        original_expiry = pending.expires_at
        original_hash = pending.password_hash

        duplicate = self.register(email="PLAYER@example.COM")

        self.assertEqual(duplicate.status_code, 200)
        self.assertIn("__all__", duplicate.context["form"].errors)
        pending.refresh_from_db()
        self.assertEqual(pending.expires_at, original_expiry)
        self.assertEqual(pending.password_hash, original_hash)

    def test_verification_get_does_not_mutate_and_post_activates_once(self):
        self.register()
        path = path_from_message(mail.outbox[0])

        preview = self.client.get(path)
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(User.objects.filter(username="new-player").exists())
        self.assertIn("no-store", preview["Cache-Control"])

        confirmed = self.client.post(path)
        user = User.objects.get(username="new-player")
        account_email = AccountEmail.objects.get(user=user)
        self.assertEqual(confirmed.status_code, 200)
        self.assertContains(confirmed, "Tài khoản của bạn đã sẵn sàng")
        self.assertTrue(user.is_active)
        self.assertIsNotNone(account_email.verified_at)
        self.assertFalse(PendingRegistration.objects.exists())

        replay = self.client.get(path)
        self.assertContains(replay, "không hợp lệ hoặc đã được sử dụng")
        self.assertContains(replay, 'role="alert"')

    def test_unverified_account_cannot_login(self):
        self.register()

        response = self.client.post(
            reverse("login"),
            {"username": "new-player", "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verification_confirmation_requires_csrf(self):
        self.register()
        path = path_from_message(mail.outbox[0])
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(path)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="new-player").exists())
        self.assertTrue(PendingRegistration.objects.filter(username="new-player").exists())

    def test_tampered_and_expired_verification_tokens_are_rejected(self):
        self.register()
        pending = PendingRegistration.objects.get(username="new-player")
        token = make_verification_token(pending)

        self.assertEqual(
            inspect_verification_token(f"{token}changed").status,
            "invalid",
        )
        result = inspect_verification_token(token, now=pending.expires_at)
        self.assertEqual(result.status, "expired")

    def test_expired_identifiers_can_be_claimed_by_a_new_registration(self):
        original_time = timezone.now()
        first = create_pending_registration(
            username="shared-name",
            email="old@example.com",
            password_hash="hash-one",
            now=original_time,
        )

        replacement = create_pending_registration(
            username="shared-name",
            email="new@example.com",
            password_hash="hash-two",
            now=first.expires_at,
        )

        self.assertFalse(PendingRegistration.objects.filter(pk=first.pk).exists())
        self.assertEqual(replacement.username, "shared-name")

    def test_resend_rotates_token_within_retention_if_identifiers_are_free(self):
        self.register()
        pending = PendingRegistration.objects.get(username="new-player")
        original_token = make_verification_token(pending)
        request = RequestFactory().post("/", REMOTE_ADDR="127.0.0.1")
        resend_time = pending.expires_at + timedelta(minutes=1)
        mail.outbox.clear()

        sent = resend_verification_email(
            request=request,
            email=pending.email,
            now=resend_time,
        )

        self.assertTrue(sent)
        pending.refresh_from_db()
        self.assertEqual(inspect_verification_token(original_token).status, "invalid")
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_does_not_send_after_two_hour_retention(self):
        self.register()
        pending = PendingRegistration.objects.get(username="new-player")
        request = RequestFactory().post("/", REMOTE_ADDR="127.0.0.1")

        sent = resend_verification_email(
            request=request,
            email=pending.email,
            now=pending.retained_until,
        )

        self.assertFalse(sent)
        self.assertFalse(PendingRegistration.objects.filter(pk=pending.pk).exists())

    def test_resend_does_not_send_when_username_was_claimed_after_expiry(self):
        self.register()
        pending = PendingRegistration.objects.get(username="new-player")
        User.objects.create_user(username=pending.username, password=self.password)
        request = RequestFactory().post("/", REMOTE_ADDR="127.0.0.1")
        mail.outbox.clear()

        sent = resend_verification_email(
            request=request,
            email=pending.email,
            now=pending.expires_at,
        )

        self.assertFalse(sent)
        self.assertFalse(PendingRegistration.objects.filter(pk=pending.pk).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_email_uniqueness_is_case_insensitive_in_database(self):
        now = timezone.now()
        create_pending_registration(
            username="first-pending",
            email="shared@example.com",
            password_hash="hash-one",
            now=now,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PendingRegistration.objects.bulk_create(
                [
                    PendingRegistration(
                        username="second-pending",
                        email="SHARED@example.com",
                        password_hash="hash-two",
                        created_at=now,
                        expires_at=now + timedelta(minutes=5),
                        retained_until=now + timedelta(hours=2),
                    )
                ]
            )

    def test_cleanup_command_removes_only_past_retention(self):
        current_time = timezone.now()
        fresh = create_pending_registration(
            username="fresh",
            email="fresh@example.com",
            password_hash="fresh-hash",
            now=current_time,
        )
        stale = create_pending_registration(
            username="stale",
            email="stale@example.com",
            password_hash="stale-hash",
            now=current_time - timedelta(hours=3),
        )

        call_command("cleanup_pending_registrations")

        self.assertFalse(PendingRegistration.objects.filter(pk=stale.pk).exists())
        self.assertTrue(PendingRegistration.objects.filter(pk=fresh.pk).exists())

    def test_resend_response_is_identical_for_unknown_and_unverified_email(self):
        self.register()
        mail.outbox.clear()

        known = self.client.post(
            reverse("email-verification-resend"),
            {"email": "player@example.com"},
        )
        unknown = self.client.post(
            reverse("email-verification-resend"),
            {"email": "unknown@example.com"},
        )

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.url, unknown.url)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(ACCOUNT_EMAIL_RATE_LIMIT_PER_ADDRESS=2)
    def test_resend_rate_limit_silently_suppresses_extra_email(self):
        self.register()
        mail.outbox.clear()
        url = reverse("email-verification-resend")

        first = self.client.post(url, {"email": "player@example.com"})
        second = self.client.post(url, {"email": "player@example.com"})

        self.assertEqual(first.status_code, second.status_code)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(ACCOUNT_EMAIL_RATE_LIMIT_PER_IP=1)
    def test_registration_rate_limit_suppresses_delivery_but_keeps_generic_flow(self):
        first = self.register(username="first", email="first@example.com")
        second = self.register(username="second", email="second@example.com")

        self.assertEqual(first.status_code, second.status_code)
        self.assertEqual(first.url, second.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(PendingRegistration.objects.filter(username="second").exists())

    def test_verification_smtp_failure_keeps_pending_record_and_hides_email(self):
        with patch(
            "accounts.email_services.EmailMultiAlternatives.send",
            side_effect=OSError("smtp unavailable"),
        ), self.assertLogs("accounts.email_services", level="WARNING") as logs:
            response = self.register()

        self.assertRedirects(response, reverse("email-verification-sent"))
        self.assertTrue(PendingRegistration.objects.filter(username="new-player").exists())
        self.assertNotIn("player@example.com", " ".join(logs.output))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="CodeHehe <no-reply@example.com>",
    ACCOUNT_EMAIL_RATE_LIMIT_WINDOW_SECONDS=3600,
    ACCOUNT_EMAIL_RATE_LIMIT_PER_IP=10,
    ACCOUNT_EMAIL_RATE_LIMIT_PER_ADDRESS=3,
)
class PasswordResetFlowTests(TestCase):
    old_password = "OldPassword-938!"
    new_password = "NewPassword-472!"

    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.user = User.objects.create_user(
            username="verified-player",
            email="verified@example.com",
            password=self.old_password,
        )
        self.account_email = AccountEmail.objects.create(
            user=self.user,
            email=self.user.email,
            verified_at=timezone.now(),
        )

    def test_verified_user_can_reset_password_with_one_time_link(self):
        existing_session = Client()
        self.assertTrue(
            existing_session.login(
                username=self.user.username,
                password=self.old_password,
            )
        )
        response = self.client.post(
            reverse("password_reset"),
            {"email": "VERIFIED@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        initial_path = path_from_message(mail.outbox[0])
        confirmation = self.client.get(initial_path)
        self.assertEqual(confirmation.status_code, 302)
        set_password_path = confirmation.url
        form_page = self.client.get(set_password_path)
        self.assertContains(form_page, "Đặt mật khẩu mới")
        self.assertIn("no-store", form_page["Cache-Control"])
        changed = self.client.post(
            set_password_path,
            {"new_password1": self.new_password, "new_password2": self.new_password},
        )
        self.assertRedirects(changed, reverse("password_reset_complete"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.old_password))
        stale_session = existing_session.get(reverse("player-profile"))
        self.assertRedirects(
            stale_session,
            f"{reverse('login')}?next={reverse('player-profile')}",
        )
        replay = self.client.get(initial_path, follow=True)
        self.assertContains(replay, "Liên kết không hợp lệ")

    def test_password_mismatch_shows_visible_error_summary(self):
        self.client.post(
            reverse("password_reset"),
            {"email": self.account_email.email},
        )
        initial_path = path_from_message(mail.outbox[0])
        set_password_path = self.client.get(initial_path).url

        response = self.client.post(
            set_password_path,
            {
                "new_password1": self.new_password,
                "new_password2": "DifferentPassword-472!",
            },
        )

        self.assertNotContains(response, "data-auth-form-alert")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_new_password2_error"')

    def test_weak_password_errors_are_vietnamese(self):
        self.client.post(
            reverse("password_reset"),
            {"email": self.account_email.email},
        )
        initial_path = path_from_message(mail.outbox[0])
        set_password_path = self.client.get(initial_path).url

        response = self.client.post(
            set_password_path,
            {"new_password1": "123", "new_password2": "123"},
        )

        self.assertContains(response, "Mật khẩu phải có ít nhất 8 ký tự")
        self.assertContains(response, "Mật khẩu này quá phổ biến")
        self.assertContains(response, "Mật khẩu không được chỉ gồm chữ số")
        self.assertNotContains(response, "This password")

    def test_unknown_and_unverified_email_get_same_response_without_email(self):
        create_pending_registration(
            username="unverified",
            email="unverified@example.com",
            password_hash="unused-hash",
        )
        url = reverse("password_reset")

        unknown = self.client.post(url, {"email": "unknown@example.com"})
        unverified = self.client.post(url, {"email": "unverified@example.com"})

        self.assertEqual(unknown.status_code, unverified.status_code)
        self.assertEqual(unknown.url, unverified.url)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ACCOUNT_EMAIL_RATE_LIMIT_PER_ADDRESS=1)
    def test_password_reset_rate_limit_suppresses_extra_email(self):
        url = reverse("password_reset")
        self.client.post(url, {"email": self.account_email.email})
        self.client.post(url, {"email": self.account_email.email})
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_failure_is_safe_and_does_not_expose_email_in_logs(self):
        with patch(
            "accounts.forms.EmailMultiAlternatives.send",
            side_effect=OSError("smtp unavailable"),
        ), self.assertLogs("accounts.forms", level="WARNING") as logs:
            response = self.client.post(
                reverse("password_reset"),
                {"email": self.account_email.email},
            )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertNotIn(self.account_email.email, " ".join(logs.output))

    def test_verified_email_uniqueness_is_case_insensitive_in_database(self):
        another_user = User.objects.create_user(
            username="another-player",
            password=self.old_password,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountEmail.objects.bulk_create(
                [
                    AccountEmail(
                        user=another_user,
                        email="VERIFIED@example.com",
                        verified_at=timezone.now(),
                    )
                ]
            )


class AccountEmailMigrationTests(TestCase):
    def setUp(self):
        self.migration = importlib.import_module("accounts.migrations.0004_accountemail")

    def test_backfill_normalizes_and_verifies_existing_email(self):
        user = User.objects.create_user(username="legacy", email="Legacy@Example.com")

        self.migration.backfill_account_emails(importlib.import_module("django.apps").apps, None)

        account_email = AccountEmail.objects.get(user=user)
        user.refresh_from_db()
        self.assertEqual(account_email.email, "legacy@example.com")
        self.assertIsNotNone(account_email.verified_at)
        self.assertEqual(user.email, "legacy@example.com")

    def test_backfill_stops_on_case_insensitive_duplicate(self):
        User.objects.create_user(username="first", email="same@example.com")
        User.objects.create_user(username="second", email="SAME@example.com")

        with self.assertRaises(RuntimeError):
            self.migration.backfill_account_emails(
                importlib.import_module("django.apps").apps,
                None,
            )


class PendingRegistrationMigrationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([("accounts", "0004_accountemail")])
        old_apps = self.executor.loader.project_state(
            [("accounts", "0004_accountemail")]
        ).apps
        old_user = old_apps.get_model("auth", "User")
        old_account_email = old_apps.get_model("accounts", "AccountEmail")
        joined_at = timezone.now() - timedelta(minutes=1)
        user = old_user.objects.create(
            username="pending-legacy",
            email="pending@example.com",
            password="hashed-password",
            is_active=False,
            date_joined=joined_at,
        )
        old_account_email.objects.create(
            user_id=user.pk,
            email="pending@example.com",
            verified_at=None,
        )

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_unverified_inactive_user_becomes_pending_registration(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([("accounts", "0005_pending_registration")])
        new_apps = self.executor.loader.project_state(
            [("accounts", "0005_pending_registration")]
        ).apps
        new_user = new_apps.get_model("auth", "User")
        pending_model = new_apps.get_model("accounts", "PendingRegistration")

        self.assertFalse(
            new_user.objects.filter(username="pending-legacy").exists()
        )
        pending = pending_model.objects.get(username="pending-legacy")
        self.assertEqual(pending.email, "pending@example.com")
        self.assertEqual(pending.password_hash, "hashed-password")

    def test_stale_unverified_user_is_removed_without_pending_record(self):
        old_apps = self.executor.loader.project_state(
            [("accounts", "0004_accountemail")]
        ).apps
        old_user = old_apps.get_model("auth", "User")
        old_user.objects.filter(username="pending-legacy").update(
            date_joined=timezone.now() - timedelta(hours=3)
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([("accounts", "0005_pending_registration")])
        new_apps = self.executor.loader.project_state(
            [("accounts", "0005_pending_registration")]
        ).apps

        self.assertFalse(
            new_apps.get_model("auth", "User")
            .objects.filter(username="pending-legacy")
            .exists()
        )
        self.assertFalse(
            new_apps.get_model("accounts", "PendingRegistration")
            .objects.filter(username="pending-legacy")
            .exists()
        )

    def test_active_unverified_user_stops_migration(self):
        old_apps = self.executor.loader.project_state(
            [("accounts", "0004_accountemail")]
        ).apps
        old_user = old_apps.get_model("auth", "User")
        old_user.objects.filter(username="pending-legacy").update(is_active=True)

        failed_executor = MigrationExecutor(connection)
        with self.assertRaises(RuntimeError):
            failed_executor.migrate([("accounts", "0005_pending_registration")])

        old_user.objects.filter(username="pending-legacy").update(is_active=False)


@override_settings(
    EMAIL_VERIFICATION_TIMEOUT_SECONDS=300,
    PENDING_REGISTRATION_RETENTION_SECONDS=7200,
)
class RegistrationConcurrencyTests(TransactionTestCase):
    def test_concurrent_confirmation_creates_one_account(self):
        pending = create_pending_registration(
            username="race-player",
            email="race@example.com",
            password_hash="hashed-password",
        )
        token = make_verification_token(pending)
        barrier = Barrier(2)

        def confirm():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return confirm_verification_token(token).status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: confirm(), range(2)))

        self.assertEqual(statuses.count("verified"), 1)
        self.assertEqual(
            statuses.count("invalid") + statuses.count("conflict"),
            1,
        )
        self.assertEqual(User.objects.filter(username="race-player").count(), 1)
        self.assertEqual(AccountEmail.objects.filter(email="race@example.com").count(), 1)

    def test_concurrent_registration_reserves_identifiers_once(self):
        barrier = Barrier(2)

        def register():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    create_pending_registration(
                        username="race-pending",
                        email="race-pending@example.com",
                        password_hash="hashed-password",
                    )
                except PendingRegistrationConflict:
                    return "conflict"
                return "created"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: register(), range(2)))

        self.assertEqual(statuses.count("created"), 1)
        self.assertEqual(statuses.count("conflict"), 1)
        self.assertEqual(
            PendingRegistration.objects.filter(username="race-pending").count(),
            1,
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountEmailAdminTests(TestCase):
    def test_admin_addition_marks_email_verified_and_activates_user(self):
        admin_user = User.objects.create_superuser(username="root", password="secret")
        user = User.objects.create_user(
            username="legacy-player",
            password="secret",
            is_active=False,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("admin:accounts_accountemail_add"),
            {"user": user.pk, "email": "Legacy@Example.com", "_save": "Save"},
        )

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        account_email = AccountEmail.objects.get(user=user)
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "legacy@example.com")
        self.assertIsNotNone(account_email.verified_at)

    def test_user_admin_keeps_legacy_email_field_read_only(self):
        model_admin = admin.site._registry[User]
        self.assertIn("email", model_admin.get_readonly_fields(None))

    def test_pending_registration_admin_does_not_expose_password_hash(self):
        model_admin = admin.site._registry[PendingRegistration]

        self.assertNotIn("password_hash", model_admin.fields)
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
