"""Tests for the VivaRepo account dashboard."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        generation_started_at = timezone.now()
        question_set = QuestionSet.objects.create(
            repository=repository,
            generated_by=active_user,
            status=QuestionSet.Status.COMPLETE,
            model_name="gpt-test",
            generation_started_at=generation_started_at,
            completed_at=generation_started_at + timedelta(seconds=42),
        )
        FreeResponseQuestion.objects.bulk_create(
            [
                FreeResponseQuestion(
                    question_set=question_set,
                    position=position,
                    prompt=f"Question {position}",
                    focus_area="Stacks" if position <= 3 else "Complexity",
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
        self.assertEqual(response.context["average_generation_seconds"], 42)
        self.assertEqual(response.context["average_generation_time"], "42 sec")
        self.assertEqual(response.context["generation_sample_count"], 1)
        self.assertEqual(
            response.context["topic_tallies"],
            [
                {"focus_area": "Stacks", "question_count": 3},
                {"focus_area": "Complexity", "question_count": 2},
            ],
        )
        self.assertContains(response, "Registered accounts")
        self.assertContains(response, "Repositories uploaded")
        self.assertContains(response, "Questions generated")
        self.assertContains(response, "Average generation time")
        self.assertContains(response, "42 sec")
        self.assertContains(response, "Question topics tested")
        self.assertContains(response, "Stacks")
        self.assertContains(response, "Complexity")
        self.assertContains(response, '<span class="topic-tally">3</span>', html=True)
        self.assertContains(response, '<span class="topic-tally">2</span>', html=True)
        self.assertContains(response, 'id="account-count-chart"')
        self.assertContains(response, "No personal account")
        self.assertContains(response, "information is displayed.")

    def test_dashboard_handles_empty_tables(self):
        response = self.client.get(reverse("projects:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account_count"], 0)
        self.assertEqual(response.context["repository_count"], 0)
        self.assertEqual(response.context["question_count"], 0)
        self.assertEqual(response.context["topic_tallies"], [])
        self.assertIsNone(response.context["average_generation_seconds"])
        self.assertEqual(response.context["average_generation_time"], "—")
        self.assertEqual(response.context["generation_sample_count"], 0)
        self.assertContains(response, "Question topics will appear")
        self.assertContains(response, "Timing begins when")
