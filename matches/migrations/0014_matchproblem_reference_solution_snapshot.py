from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0013_match_ruleset_snapshot"),
        ("problems", "0005_problem_reference_solution"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchproblem",
            name="reference_solution_snapshot",
            field=models.TextField(blank=True),
        ),
    ]
