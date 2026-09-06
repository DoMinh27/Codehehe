
from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PendingRegistration


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class RegisterTests(TestCase):
    password = "SafePassword-938!"

    def test_register_page_uses_expected_template(self):
        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")

    def test_valid_registration_creates_only_pending_registration(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_player",
                "email": "Player@Example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(response, reverse("email-verification-sent"))
        self.assertFalse(User.objects.filter(username="new_player").exists())
        pending = PendingRegistration.objects.get(username="new_player")
        self.assertNotEqual(pending.password_hash, self.password)
        self.assertEqual(pending.email, "player@example.com")

    def test_duplicate_username_does_not_create_another_user(self):
        User.objects.create_user(username="existing", password=self.password)

        response = self.client.post(
            reverse("register"),
            {
                "username": "existing",
                "email": "another@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="existing").count(), 1)
        self.assertIn("username", response.context["form"].errors)

    def test_invalid_password_confirmation_does_not_create_user(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_player",
                "email": "new@example.com",
                "password1": self.password,
                "password2": "DifferentPassword-938!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="new_player").exists())
        self.assertIn("password2", response.context["form"].errors)

    def test_invalid_registration_values_are_explained_in_vietnamese(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_player",
                "email": "not-an-email",
                "password1": "123",
                "password2": "123",
            },
        )

        self.assertContains(response, "Nhập địa chỉ email hợp lệ")
        self.assertContains(response, "Mật khẩu phải có ít nhất 8 ký tự")
        self.assertNotContains(response, "This password")
        self.assertNotContains(response, "Enter a valid email")

    def test_authenticated_user_is_redirected_from_register(self):
        user = User.objects.create_user(username="player", password=self.password)
        self.client.force_login(user)

        response = self.client.get(reverse("register"))

        self.assertRedirects(response, reverse("lobby"))


class LoginTests(TestCase):
    password = "SafePassword-938!"

    def setUp(self):
        self.user = User.objects.create_user(
            username="player",
            password=self.password,
        )

    def test_login_page_uses_expected_template(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_valid_login_creates_session_and_redirects_to_lobby(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("lobby"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_invalid_login_does_not_create_authenticated_session(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, "Tên đăng nhập hoặc mật khẩu không đúng")
        self.assertContains(response, "data-auth-form-alert")
        self.assertContains(response, "<title>Lỗi: Đăng nhập | CodeHehe</title>", html=True)

    def test_missing_login_field_shows_inline_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": ""},
        )

        self.assertNotContains(response, "data-auth-form-alert")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_password_error"')
        self.assertContains(response, "Vui lòng nhập mật khẩu")

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("login"))

        self.assertRedirects(response, reverse("lobby"))


class LobbyTests(TestCase):
    password = "SafePassword-938!"

    def test_anonymous_user_is_redirected_to_login_with_next(self):
        response = self.client.get(reverse("lobby"))

        expected_url = f"{reverse('login')}?next={reverse('lobby')}"
        self.assertRedirects(response, expected_url)

    def test_authenticated_user_can_view_lobby(self):
        user = User.objects.create_user(username="player", password=self.password)
        self.client.force_login(user)

        response = self.client.get(reverse("lobby"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/lobby.html")
        self.assertContains(response, user.username)


class LogoutTests(TestCase):
    password = "SafePassword-938!"

    def setUp(self):
        self.user = User.objects.create_user(
            username="player",
            password=self.password,
        )
        self.client.force_login(self.user)

    def test_logout_post_clears_session_and_redirects_to_login(self):
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_get_is_not_allowed_and_keeps_session(self):
        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)
