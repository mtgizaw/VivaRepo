"""Authentication and foundation smoke tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class FoundationSmokeTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("projects:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VivaRepo")

    def test_health_endpoint(self):
        response = self.client.get(reverse("projects:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class AuthenticationTests(TestCase):
    password = "StrongPass-2026!"

    def test_social_login_buttons_link_to_provider_routes(self):
        for page_name in ("projects:signup", "projects:login"):
            with self.subTest(page=page_name):
                response = self.client.get(reverse(page_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "/accounts/google/login/")
                self.assertContains(response, "/accounts/github/login/")
                self.assertNotContains(response, "disabled")

    def test_signup_stores_hashed_password_and_logs_user_in(self):
        response = self.client.post(
            reverse("projects:signup"),
            {
                "username": "martha",
                "email": "Martha@example.com",
                "password1": self.password,
                "password2": self.password,
                "terms": "on",
            },
        )

        self.assertRedirects(response, reverse("projects:home"))
        user = User.objects.get(username="martha")
        self.assertEqual(user.email, "martha@example.com")
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user(
            username="existing",
            email="martha@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("projects:signup"),
            {
                "username": "another",
                "email": "MARTHA@example.com",
                "password1": self.password,
                "password2": self.password,
                "terms": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertEqual(User.objects.count(), 1)

    def test_user_can_log_in_with_email(self):
        user = User.objects.create_user(
            username="martha",
            email="martha@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("projects:login"),
            {"email": "MARTHA@example.com", "password": self.password},
        )

        self.assertRedirects(response, reverse("projects:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_invalid_credentials_do_not_create_a_session(self):
        User.objects.create_user(
            username="martha",
            email="martha@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("projects:login"),
            {"email": "martha@example.com", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email or password is incorrect.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_ends_session(self):
        user = User.objects.create_user(
            username="martha",
            email="martha@example.com",
            password=self.password,
        )
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("projects:logout")).status_code, 405)
        response = self.client.post(reverse("projects:logout"))

        self.assertRedirects(response, reverse("projects:home"))
        self.assertNotIn("_auth_user_id", self.client.session)
