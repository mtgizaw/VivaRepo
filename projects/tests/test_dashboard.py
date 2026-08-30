"""Tests for the VivaRepo account dashboard."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AccountDashboardTests(TestCase):
    def test_dashboard_shows_the_count_from_the_configured_user_model(self):
        User.objects.create_user(username="active", password="StrongPass-2026!")
        User.objects.create_user(
            username="inactive",
            password="StrongPass-2026!",
            is_active=False,
        )

        response = self.client.get(reverse("projects:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account_count"], 2)
        self.assertContains(response, "Registered accounts")
        self.assertContains(response, 'id="account-count-chart"')
        self.assertContains(response, "No personal account")
        self.assertContains(response, "information is displayed.")

    def test_dashboard_handles_an_empty_user_table(self):
        response = self.client.get(reverse("projects:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account_count"], 0)
