
from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class RegisterTests(TestCase):
    password = "SafePassword-938!"

    def test_register_page_uses_expected_template(self):
        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")

    def test_valid_registration_creates_user_with_hashed_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_player",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="new_player")
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))

    def test_duplicate_username_does_not_create_another_user(self):
        User.objects.create_user(username="existing", password=self.password)

        response = self.client.post(
            reverse("register"),
            {
                "username": "existing",
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
                "password1": self.password,
                "password2": "DifferentPassword-938!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="new_player").exists())
        self.assertIn("password2", response.context["form"].errors)

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
