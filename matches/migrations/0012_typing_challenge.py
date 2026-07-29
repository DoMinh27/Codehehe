from django.db import migrations, models
import django.db.models.deletion


TYPING_CODE = "TYPING_CHALLENGE"


def seed_typing_skill(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    MatchSkill = apps.get_model("matches", "MatchSkill")
    Skill = apps.get_model("matches", "Skill")

    skill, _ = Skill.objects.update_or_create(
        code=TYPING_CODE,
        defaults={
            "name": "Thử thách gõ chữ",
            "description": (
                "Khóa Run, Submit và Skill của đối thủ cho đến khi "
                "gõ đúng câu hoặc hết 20 giây."
            ),
            "energy_cost": 1,
            "duration_seconds": 20,
            "is_active": True,
        },
    )
    for match in Match.objects.filter(status="PLAYING").iterator():
        MatchSkill.objects.get_or_create(
            match=match,
            skill=skill,
            defaults={
                "code_snapshot": skill.code,
                "name_snapshot": skill.name,
                "description_snapshot": skill.description,
                "energy_cost_snapshot": skill.energy_cost,
                "duration_seconds_snapshot": skill.duration_seconds,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0011_reduce_time_drain_energy_cost"),
    ]

    operations = [
        migrations.CreateModel(
            name="TypingChallenge",
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
                ("prompt", models.CharField(max_length=100)),
                ("started_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "effect",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="typing_challenge",
                        to="matches.skilleffect",
                    ),
                ),
            ],
            options={
                "ordering": ["expires_at", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("expires_at__gt", models.F("started_at"))
                        ),
                        name="typingchallenge_expires_after_start",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("completed_at__isnull", True))
                            | (
                                models.Q(
                                    ("completed_at__gte", models.F("started_at"))
                                )
                                & models.Q(
                                    ("completed_at__lte", models.F("expires_at"))
                                )
                            )
                        ),
                        name="typingchallenge_completion_in_window",
                    ),
                ],
            },
        ),
        migrations.RunPython(seed_typing_skill, migrations.RunPython.noop),
    ]
