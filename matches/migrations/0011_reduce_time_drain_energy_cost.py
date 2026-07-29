from django.db import migrations


def reduce_time_drain_energy_cost(apps, schema_editor):
    Skill = apps.get_model("matches", "Skill")
    Skill.objects.filter(code="TIME_DRAIN_60").update(energy_cost=1)


def restore_time_drain_energy_cost(apps, schema_editor):
    Skill = apps.get_model("matches", "Skill")
    Skill.objects.filter(code="TIME_DRAIN_60").update(energy_cost=2)


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0010_rebalance_timed_skills"),
    ]

    operations = [
        migrations.RunPython(
            reduce_time_drain_energy_cost,
            restore_time_drain_energy_cost,
        ),
    ]
