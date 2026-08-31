"""Tests for the VivaRepo account dashboard."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from assessments.models import FreeResponseQuestion, QuestionSet
from projects.models import Repository


User = get_user_model()


class AccountDashboardTests(TestCase):
    def test_dashboard_shows_live_platform_totals(self):
        active_user = User.objects.create_user(
            username="active",
            password="StrongPass-2026!",
        )
        User.objects.create_user(
            username="inactive",
            password="StrongPass-2026!",
            is_active=False,
        )
        repository = Repository.objects.create(
            name="BoundedStack",
            archive="repository_archives/boundedstack.zip",
            original_filename="boundedstack.zip",
            size_bytes=4500,
            uploaded_by=active_user,
        )
        question_set = QuestionSet.objects.create(
            repository=repository,
            generated_by=active_user,
            status=QuestionSet.Status.COMPLETE,
            model_name="gpt-test",
        )
        FreeResponseQuestion.objects.bulk_create(
            [
                FreeResponseQuestion(
                    question_set=question_set,
                    position=position,
                    prompt=f"Question {position}",
                    focus_area="Stacks",
                    reference_answer="Reference answer",
                    source_files=["BoundedStack.java"],
                )
                for position in range(1, 6)
            ]
        )

        response = self.client.get(reverse("projects:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account_count"], 2)
        self.assertEqual(response.context["repository_count"], 1)
        self.assertEqual(response.context["question_count"], 5)
        self.assertContains(response, "Registered accounts")
        self.assertContains(response, "Repositories uploaded")
        self.assertContains(response, "Questions generated")
        self.assertContains(response, 'id="account-count-chart"')
        self.assertContains(response, "No personal account")
        self.assertContains(response, "information is displayed.")

    def test_dashboard_handles_empty_tables(self):
        response = self.client.get(reverse("projects:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account_count"], 0)
        self.assertEqual(response.context["repository_count"], 0)
        self.assertEqual(response.context["question_count"], 0)
