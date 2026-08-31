from django.db import migrations, models
from django.db.models import F


def backfill_evaluation_started_at(apps, schema_editor):
    AssessmentSubmission = apps.get_model("assessments", "AssessmentSubmission")
    AssessmentSubmission.objects.filter(evaluation_started_at__isnull=True).update(
        evaluation_started_at=F("submitted_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0003_questionset_generation_started_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessmentsubmission",
            name="evaluation_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            backfill_evaluation_started_at,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
