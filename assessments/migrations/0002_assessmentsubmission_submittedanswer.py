from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("assessments", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentSubmission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("evaluating", "Evaluating"),
                            ("complete", "Complete"),
                            ("failed", "Failed"),
                        ],
                        default="evaluating",
                        max_length=16,
                    ),
                ),
                (
                    "overall_score",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("overall_summary", models.TextField(blank=True)),
                ("strengths", models.JSONField(default=list)),
                ("weaknesses", models.JSONField(default=list)),
                ("question_feedback", models.JSONField(default=list)),
                ("practice_resources", models.JSONField(default=list)),
                ("model_name", models.CharField(max_length=80)),
                ("response_id", models.CharField(blank=True, max_length=120)),
                ("error_message", models.CharField(blank=True, max_length=255)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "question_set",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submission",
                        to="assessments.questionset",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assessment_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SubmittedAnswer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("response", models.TextField()),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submitted_answers",
                        to="assessments.freeresponsequestion",
                    ),
                ),
                (
                    "submission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="assessments.assessmentsubmission",
                    ),
                ),
            ],
            options={
                "ordering": ("question__position",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("submission", "question"),
                        name="unique_answer_per_submission_question",
                    )
                ],
            },
        ),
    ]
