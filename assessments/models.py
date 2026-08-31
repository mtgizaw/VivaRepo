"""Generated assessments grounded in uploaded repositories."""

from django.conf import settings
from django.db import models

from projects.models import Repository


class QuestionSet(models.Model):
    """One generated assessment for a repository."""

    class Status(models.TextChoices):
        GENERATING = "generating", "Generating"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    repository = models.OneToOneField(
        Repository,
        on_delete=models.CASCADE,
        related_name="question_set",
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generated_question_sets",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.GENERATING,
    )
    model_name = models.CharField(max_length=80)
    response_id = models.CharField(max_length=120, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Questions for {self.repository.name}"


class FreeResponseQuestion(models.Model):
    """A question and private reference material generated from repository code."""

    question_set = models.ForeignKey(
        QuestionSet,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    position = models.PositiveSmallIntegerField()
    prompt = models.TextField()
    focus_area = models.CharField(max_length=120)
    reference_answer = models.TextField()
    source_files = models.JSONField(default=list)

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("question_set", "position"),
                name="unique_question_position_per_set",
            )
        ]

    def __str__(self) -> str:
        return f"Question {self.position}: {self.focus_area}"


class AssessmentSubmission(models.Model):
    """A user's complete set of answers and its generated evaluation."""

    class Status(models.TextChoices):
        EVALUATING = "evaluating", "Evaluating"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    question_set = models.OneToOneField(
        QuestionSet,
        on_delete=models.CASCADE,
        related_name="submission",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_submissions",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.EVALUATING,
    )
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    overall_summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list)
    weaknesses = models.JSONField(default=list)
    question_feedback = models.JSONField(default=list)
    practice_resources = models.JSONField(default=list)
    model_name = models.CharField(max_length=80)
    response_id = models.CharField(max_length=120, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Submission for {self.question_set.repository.name}"


class SubmittedAnswer(models.Model):
    """A learner's answer to one generated free-response question."""

    submission = models.ForeignKey(
        AssessmentSubmission,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        FreeResponseQuestion,
        on_delete=models.CASCADE,
        related_name="submitted_answers",
    )
    response = models.TextField()

    class Meta:
        ordering = ("question__position",)
        constraints = [
            models.UniqueConstraint(
                fields=("submission", "question"),
                name="unique_answer_per_submission_question",
            )
        ]

    def __str__(self) -> str:
        return f"Answer to question {self.question.position}"
