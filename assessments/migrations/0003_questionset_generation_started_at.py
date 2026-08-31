from django.db import migrations, models
from django.db.models import F


def backfill_generation_started_at(apps, schema_editor):
    QuestionSet = apps.get_model("assessments", "QuestionSet")
    QuestionSet.objects.filter(generation_started_at__isnull=True).update(
        generation_started_at=F("created_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_assessmentsubmission_submittedanswer"),
    ]

    operations = [
        migrations.AddField(
            model_name="questionset",
            name="generation_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            backfill_generation_started_at,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
