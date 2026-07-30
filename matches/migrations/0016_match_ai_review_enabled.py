from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0015_submission_ai_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="ai_review_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
