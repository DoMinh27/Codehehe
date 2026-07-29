from django.db import migrations


TIMED_SKILL_CODES = ("MIRROR_CODE", "BLUR_STATEMENT")


def set_timed_skill_duration(apps, schema_editor):
    Skill = apps.get_model("matches", "Skill")
    Skill.objects.filter(code__in=TIMED_SKILL_CODES).update(duration_seconds=35)


def restore_timed_skill_duration(apps, schema_editor):
    Skill = apps.get_model("matches", "Skill")
    Skill.objects.filter(code__in=TIMED_SKILL_CODES).update(duration_seconds=30)


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0009_alter_match_duration_seconds"),
    ]

    operations = [
        migrations.RunPython(
            set_timed_skill_duration,
            restore_timed_skill_duration,
        ),
    ]
