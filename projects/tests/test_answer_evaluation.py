"""Tests for learner answers and OpenAI-generated assessment feedback."""

from io import BytesIO
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ai.answer_evaluation import EvaluationError, GeneratedEvaluation
from assessments.models import AssessmentSubmission, QuestionSet, SubmittedAnswer
from projects.models import Repository
from projects.tests.test_question_generation import five_questions


User = get_user_model()


def evaluation_result() -> dict:
    return {
        "overall_score": 82,
        "overall_summary": (
            "You understand the repository's main control flow and invariants, "
            "with a few opportunities to make the edge-case reasoning more precise."
        ),
        "strengths": [
            {
                "title": "Control-flow reasoning",
                "detail": "You connected public operations to their internal behavior.",
            },
            {
                "title": "Clear explanations",
                "detail": "Your answers stayed focused on the code under discussion.",
            },
        ],
        "weaknesses": [
            {
                "title": "Boundary conditions",
                "detail": "Some answers need more detail about empty and full states.",
            },
            {
                "title": "Complexity analysis",
                "detail": "Time and space costs should be stated explicitly.",
            },
        ],
        "question_feedback": [
            {
                "question_number": number,
                "score": 15 + number,
                "summary": f"Answer {number} identifies the important behavior.",
                "demonstrated_strength": "It uses concrete repository details.",
                "next_improvement": "Explain one additional edge case.",
            }
            for number in range(1, 6)
        ],
        "practice_resources": [
            {
                "title": "Python data model documentation",
                "resource_type": "Documentation",
                "url": "https://docs.python.org/3/reference/datamodel.html",
                "recommendation": "Review container protocols and exception behavior.",
                "practice_goal": "Implement and test a small bounded collection.",
            },
            {
                "title": "Boundary-value test exercise",
                "resource_type": "Coding exercise",
                "url": "https://docs.pytest.org/en/stable/how-to/parametrize.html",
                "recommendation": "Write tests around empty, one-item, and full states.",
                "practice_goal": "Cover every transition at the capacity boundary.",
            },
            {
                "title": "Complexity walkthrough",
                "resource_type": "Tutorial topic",
                "url": "https://wiki.python.org/moin/TimeComplexity",
                "recommendation": "Practice deriving operation costs from source code.",
                "practice_goal": "State time and space complexity for each operation.",
            },
        ],
    }


class AssessmentAnswerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="martha", password="password")
        self.repository = Repository.objects.create(
            name="BoundedStack",
            archive="repository_archives/boundedstack.zip",
            original_filename="boundedstack.zip",
            size_bytes=4500,
            uploaded_by=self.user,
        )
        self.question_set = QuestionSet.objects.create(
            repository=self.repository,
            generated_by=self.user,
            model_name="gpt-question-test",
            status=QuestionSet.Status.COMPLETE,
        )
        for position, question in enumerate(five_questions(), start=1):
            self.question_set.questions.create(position=position, **question)
        self.questions = list(self.question_set.questions.all())
        self.answers = {
            f"question_{question.pk}": (
                f"My detailed answer to question {question.position} explains the "
                "relevant behavior and reasoning."
            )
            for question in self.questions
        }
        self.client.force_login(self.user)

    def test_complete_question_set_displays_five_answer_boxes(self):
        response = self.client.get(
            reverse("projects:repository_detail", args=[self.repository.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b"<textarea"), 5)
        self.assertContains(response, "Submit all answers")
        self.assertContains(response, "data-evaluation-label")
        self.assertContains(response, "Evaluating answers… ${elapsedSeconds}s")

    @patch("projects.views.evaluate_assessment_answers")
    def test_all_answers_are_saved_and_detailed_evaluation_is_displayed(
        self,
        evaluate,
    ):
        evaluate.return_value = GeneratedEvaluation(
            result=evaluation_result(),
            response_id="resp_evaluation",
            model_name="gpt-evaluation-test",
        )

        response = self.client.post(
            reverse("projects:submit_assessment_answers", args=[self.repository.pk]),
            self.answers,
            follow=True,
        )

        submission = AssessmentSubmission.objects.get(question_set=self.question_set)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(submission.status, AssessmentSubmission.Status.COMPLETE)
        self.assertEqual(submission.overall_score, 82)
        self.assertIsNotNone(submission.evaluation_started_at)
        self.assertIsNotNone(submission.completed_at)
        self.assertGreaterEqual(
            submission.completed_at,
            submission.evaluation_started_at,
        )
        self.assertEqual(SubmittedAnswer.objects.filter(submission=submission).count(), 5)
        self.assertContains(response, "Your evaluation")
        self.assertContains(response, "Strengths")
        self.assertContains(response, "Areas to strengthen")
        self.assertContains(response, "Targeted practice")
        self.assertContains(
            response,
            'href="https://docs.python.org/3/reference/datamodel.html"',
        )
        self.assertContains(response, "opens in a new tab")
        self.assertContains(response, "My detailed answer to question 1")
        self.assertNotContains(response, "The repository demonstrates behavior")

    @patch("projects.views.evaluate_assessment_answers")
    def test_invalid_answers_are_shown_without_calling_openai(self, evaluate):
        incomplete_answers = self.answers.copy()
        incomplete_answers[f"question_{self.questions[-1].pk}"] = ""

        response = self.client.post(
            reverse("projects:submit_assessment_answers", args=[self.repository.pk]),
            incomplete_answers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Answer this question before submitting.")
        self.assertFalse(AssessmentSubmission.objects.exists())
        evaluate.assert_not_called()

    @patch("projects.views.evaluate_assessment_answers")
    def test_failed_evaluation_preserves_answers_for_retry(self, evaluate):
        evaluate.side_effect = EvaluationError(
            "OpenAI could not evaluate the answers right now. Please try again."
        )

        response = self.client.post(
            reverse("projects:submit_assessment_answers", args=[self.repository.pk]),
            self.answers,
            follow=True,
        )

        submission = AssessmentSubmission.objects.get(question_set=self.question_set)
        self.assertEqual(submission.status, AssessmentSubmission.Status.FAILED)
        self.assertEqual(submission.answers.count(), 5)
        self.assertContains(response, "Evaluation needs another try")
        self.assertContains(response, self.answers[f"question_{self.questions[0].pk}"])

    @patch("projects.views.evaluate_assessment_answers")
    def test_completed_submission_is_not_evaluated_twice(self, evaluate):
        AssessmentSubmission.objects.create(
            question_set=self.question_set,
            submitted_by=self.user,
            status=AssessmentSubmission.Status.COMPLETE,
            overall_score=90,
            model_name="gpt-evaluation-test",
        )

        response = self.client.post(
            reverse("projects:submit_assessment_answers", args=[self.repository.pk]),
            self.answers,
        )

        self.assertRedirects(
            response,
            reverse("projects:repository_detail", args=[self.repository.pk]),
        )
        evaluate.assert_not_called()

    def test_other_user_cannot_submit_answers(self):
        other = User.objects.create_user(username="other", password="password")
        self.client.force_login(other)

        response = self.client.post(
            reverse("projects:submit_assessment_answers", args=[self.repository.pk]),
            self.answers,
        )

        self.assertEqual(response.status_code, 404)


class OpenAIAnswerEvaluationServiceTests(TestCase):
    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_EVALUATION_MODEL="gpt-evaluation-test",
        OPENAI_EVALUATION_REASONING_EFFORT="low",
    )
    @patch("ai.answer_evaluation.urlopen")
    def test_responses_request_uses_strict_evaluation_schema(self, urlopen_mock):
        from ai.answer_evaluation import evaluate_assessment_answers

        user = User.objects.create_user(username="service-user")
        repository = Repository.objects.create(
            name="BoundedStack",
            archive="repository_archives/boundedstack.zip",
            original_filename="boundedstack.zip",
            size_bytes=4500,
            uploaded_by=user,
        )
        question_set = QuestionSet.objects.create(
            repository=repository,
            generated_by=user,
            model_name="gpt-question-test",
            status=QuestionSet.Status.COMPLETE,
        )
        for position, question in enumerate(five_questions(), start=1):
            question_set.questions.create(position=position, **question)
        questions = list(question_set.questions.all())
        answers = {
            question.pk: f"A substantive learner response for question {question.position}."
            for question in questions
        }
        api_response = BytesIO(
            json.dumps(
                {
                    "id": "resp_evaluation",
                    "model": "gpt-evaluation-test",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "status": "completed",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(evaluation_result()),
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                }
            ).encode("utf-8")
        )
        urlopen_mock.return_value = api_response

        generated = evaluate_assessment_answers(
            repository,
            question_set,
            answers,
            user,
        )

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data)
        schema = payload["text"]["format"]["schema"]
        self.assertFalse(payload["store"])
        self.assertEqual(payload["reasoning"]["effort"], "low")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(
            schema["properties"]["question_feedback"]["minItems"],
            5,
        )
        practice_schema = schema["properties"]["practice_resources"]["items"]
        self.assertIn("url", practice_schema["required"])
        self.assertEqual(practice_schema["properties"]["url"]["maxLength"], 2048)
        self.assertIn("A substantive learner response for question 1", payload["input"])
        self.assertEqual(generated.result["overall_score"], 82)

    def test_unsafe_practice_resource_url_is_rejected(self):
        from ai.answer_evaluation import _validate_evaluation

        result = evaluation_result()
        result["practice_resources"][0]["url"] = "javascript:alert(1)"

        with self.assertRaises(EvaluationError):
            _validate_evaluation(result)
