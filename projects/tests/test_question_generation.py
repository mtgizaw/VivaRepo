"""Tests for repository-grounded OpenAI question generation."""

from io import BytesIO
import json
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ai.repository_questions import GeneratedQuestionSet
from assessments.models import QuestionSet
from projects.models import Repository
from projects.tests.test_repository_upload import repository_zip


User = get_user_model()


def five_questions() -> list[dict]:
    return [
        {
            "prompt": f"Explain how repository behavior number {number} works and why.",
            "focus_area": f"Behavior {number}",
            "reference_answer": (
                f"The repository demonstrates behavior {number} through its source code."
            ),
            "source_files": ["project/app.py"],
        }
        for number in range(1, 6)
    ]


class RepositoryQuestionViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username="martha", password="password")
        self.repository = Repository.objects.create(
            name="BoundedStack",
            archive=repository_zip("boundedstack-main.zip"),
            original_filename="boundedstack-main.zip",
            size_bytes=4500,
            uploaded_by=self.user,
        )
        self.client.force_login(self.user)

    def test_recent_upload_starts_question_generation(self):
        response = self.client.get(reverse("projects:upload_repository"))

        self.assertContains(
            response,
            reverse("projects:generate_repository_questions", args=[self.repository.pk]),
        )
        self.assertContains(response, "Generate questions")

    @patch("projects.views.generate_questions_for_repository")
    def test_generation_persists_exactly_five_questions(self, generate):
        generate.return_value = GeneratedQuestionSet(
            questions=five_questions(),
            response_id="resp_test",
            model_name="gpt-test",
        )

        response = self.client.post(
            reverse(
                "projects:generate_repository_questions",
                args=[self.repository.pk],
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        question_set = QuestionSet.objects.get(repository=self.repository)
        self.assertEqual(question_set.status, QuestionSet.Status.COMPLETE)
        self.assertEqual(question_set.questions.count(), 5)
        self.assertContains(response, "Five free-response questions are ready.")
        self.assertContains(response, "Question 5")
        self.assertNotContains(response, "The repository demonstrates behavior")

    @patch("projects.views.generate_questions_for_repository")
    def test_completed_set_is_reused_without_another_api_call(self, generate):
        question_set = QuestionSet.objects.create(
            repository=self.repository,
            generated_by=self.user,
            model_name="gpt-test",
            status=QuestionSet.Status.COMPLETE,
        )
        for position, question in enumerate(five_questions(), start=1):
            question_set.questions.create(position=position, **question)

        response = self.client.post(
            reverse(
                "projects:generate_repository_questions",
                args=[self.repository.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("projects:repository_detail", args=[self.repository.pk]),
        )
        generate.assert_not_called()

    def test_other_users_cannot_view_or_generate_for_repository(self):
        other = User.objects.create_user(username="other", password="password")
        self.client.force_login(other)

        detail_response = self.client.get(
            reverse("projects:repository_detail", args=[self.repository.pk])
        )
        generate_response = self.client.post(
            reverse(
                "projects:generate_repository_questions",
                args=[self.repository.pk],
            )
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(generate_response.status_code, 404)


class OpenAIQuestionServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root)
        super().tearDownClass()

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_QUESTION_MODEL="gpt-test",
    )
    @patch("ai.repository_questions.urlopen")
    def test_responses_request_uses_strict_five_question_schema(self, urlopen_mock):
        from ai.repository_questions import generate_questions_for_repository

        user = User.objects.create_user(username="martha")
        repository = Repository.objects.create(
            name="BoundedStack",
            archive=repository_zip("boundedstack.zip"),
            original_filename="boundedstack.zip",
            size_bytes=4500,
            uploaded_by=user,
        )
        api_response = BytesIO(
            json.dumps(
                {
                    "id": "resp_test",
                    "model": "gpt-test",
                    "output_text": json.dumps({"questions": five_questions()}),
                }
            ).encode("utf-8")
        )
        api_response.__enter__ = lambda response: response
        api_response.__exit__ = lambda *args: None
        urlopen_mock.return_value = api_response

        result = generate_questions_for_repository(repository, user)

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data)
        schema = payload["text"]["format"]["schema"]
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(schema["properties"]["questions"]["minItems"], 5)
        self.assertEqual(schema["properties"]["questions"]["maxItems"], 5)
        self.assertIn("project/app.py", payload["input"])
        self.assertEqual(len(result.questions), 5)
