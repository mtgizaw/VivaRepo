# Generated for VivaRepo repository-based free-response questions.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionSet",
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
                            ("generating", "Generating"),
                            ("complete", "Complete"),
                            ("failed", "Failed"),
                        ],
                        default="generating",
                        max_length=16,
                    ),
                ),
                ("model_name", models.CharField(max_length=80)),
                ("response_id", models.CharField(blank=True, max_length=120)),
                ("error_message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "generated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generated_question_sets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "repository",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="question_set",
                        to="projects.repository",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FreeResponseQuestion",
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
                ("position", models.PositiveSmallIntegerField()),
                ("prompt", models.TextField()),
                ("focus_area", models.CharField(max_length=120)),
                ("reference_answer", models.TextField()),
                ("source_files", models.JSONField(default=list)),
                (
                    "question_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="assessments.questionset",
                    ),
                ),
            ],
            options={
                "ordering": ("position",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("question_set", "position"),
                        name="unique_question_position_per_set",
                    )
                ],
            },
        ),
    ]
