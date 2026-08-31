from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="source_context",
            field=models.TextField(blank=True),
        )
    ]
