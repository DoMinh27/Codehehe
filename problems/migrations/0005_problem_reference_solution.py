from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0004_enforce_problem_slug_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="problem",
            name="reference_solution",
            field=models.TextField(blank=True),
        ),
    ]
