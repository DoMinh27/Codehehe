from django.db import migrations, models


def seed_shield(apps, schema_editor):
    skill_model = apps.get_model("matches", "Skill")
    skill_model.objects.update_or_create(
        code="SHIELD",
        defaults={
            "name": "Shield",
            "description": (
                "Chặn skill tấn công hợp lệ tiếp theo trong tối đa 45 giây."
            ),
            "energy_cost": 1,
            "duration_seconds": 45,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("matches", "0023_skill_policy_and_effect_consumption")]

    operations = [
        migrations.AlterField(
            model_name="match",
            name="ruleset_version",
            field=models.CharField(default="v3.2", max_length=20),
        ),
        migrations.RunPython(seed_shield, migrations.RunPython.noop),
    ]
