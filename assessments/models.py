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
