import django.db.models.deletion
from django.db import migrations, models


SKILLS = (
    {
        "code": "MIRROR_CODE",
        "name": "Đảo chiều code",
        "description": "Buộc editor của đối thủ hiển thị từ phải sang trái.",
        "energy_cost": 1,
        "duration_seconds": 30,
    },
    {
        "code": "BLUR_STATEMENT",
        "name": "Làm mờ đề",
        "description": "Làm mờ đề bài và ví dụ của đối thủ.",
        "energy_cost": 1,
        "duration_seconds": 30,
    },
    {
        "code": "TIME_DRAIN_60",
        "name": "Trừ thời gian",
        "description": "Trừ 60 giây làm bài của đối thủ.",
        "energy_cost": 2,
        "duration_seconds": None,
    },
)


def seed_skills_and_reconcile_matches(apps, schema_editor):
    Skill = apps.get_model("matches", "Skill")
    Match = apps.get_model("matches", "Match")
    MatchSkill = apps.get_model("matches", "MatchSkill")
    Progress = apps.get_model("matches", "PlayerProblemProgress")

    skills = []
    for definition in SKILLS:
        skill, _ = Skill.objects.update_or_create(
            code=definition["code"],
            defaults={**definition, "is_active": True},
        )
        skills.append(skill)

    for match in Match.objects.filter(status="PLAYING"):
        for skill in skills:
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

    Progress.objects.filter(is_solved=True).update(reward_processed=True)


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0006_enforce_sqlite_match_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchPlayerSkill",
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
                ("quantity", models.PositiveIntegerField(default=0)),
                ("used_count", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["match_skill_id"]},
        ),
        migrations.CreateModel(
            name="MatchSkill",
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
                ("code_snapshot", models.CharField(max_length=40)),
                ("name_snapshot", models.CharField(max_length=100)),
                ("description_snapshot", models.TextField()),
                ("energy_cost_snapshot", models.PositiveSmallIntegerField()),
                (
                    "duration_seconds_snapshot",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="Skill",
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
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField()),
                ("energy_cost", models.PositiveSmallIntegerField()),
                (
                    "duration_seconds",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="SkillEffect",
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
                ("started_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["expires_at", "id"]},
        ),
        migrations.CreateModel(
            name="SkillUse",
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
                ("energy_spent", models.PositiveSmallIntegerField()),
                ("idempotency_key", models.CharField(max_length=64)),
                ("used_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-used_at", "-id"]},
        ),
        migrations.AddField(
            model_name="matchplayer",
            name="energy",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="matchplayer",
            name="time_penalty_seconds",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="playerproblemprogress",
            name="energy_awarded",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="playerproblemprogress",
            name="reward_processed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="matchplayer",
            constraint=models.CheckConstraint(
                condition=models.Q(energy__gte=0, energy__lte=3),
                name="matchplayer_energy_0_to_3",
            ),
        ),
        migrations.AddField(
            model_name="matchplayerskill",
            name="player",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="skill_inventory",
                to="matches.matchplayer",
            ),
        ),
        migrations.AddField(
            model_name="matchskill",
            name="match",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="match_skills",
                to="matches.match",
            ),
        ),
        migrations.AddField(
            model_name="matchplayerskill",
            name="match_skill",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="player_inventory",
                to="matches.matchskill",
            ),
        ),
        migrations.AddField(
            model_name="playerproblemprogress",
            name="skill_awarded",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="awarded_progress",
                to="matches.matchskill",
            ),
        ),
        migrations.AddConstraint(
            model_name="playerproblemprogress",
            constraint=models.CheckConstraint(
                condition=models.Q(energy_awarded__in=[0, 1]),
                name="progress_energy_award_0_or_1",
            ),
        ),
        migrations.AddField(
            model_name="matchskill",
            name="skill",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="match_snapshots",
                to="matches.skill",
            ),
        ),
        migrations.AddField(
            model_name="skilluse",
            name="match",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="skill_uses",
                to="matches.match",
            ),
        ),
        migrations.AddField(
            model_name="skilluse",
            name="match_skill",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="uses",
                to="matches.matchskill",
            ),
        ),
        migrations.AddField(
            model_name="skilluse",
            name="source_player",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="skill_uses",
                to="matches.matchplayer",
            ),
        ),
        migrations.AddField(
            model_name="skilluse",
            name="target_player",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="skill_hits",
                to="matches.matchplayer",
            ),
        ),
        migrations.AddField(
            model_name="skilleffect",
            name="skill_use",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="effect",
                to="matches.skilluse",
            ),
        ),
        migrations.AddConstraint(
            model_name="matchplayerskill",
            constraint=models.UniqueConstraint(
                fields=("player", "match_skill"),
                name="player_matchskill_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="matchskill",
            constraint=models.UniqueConstraint(
                fields=("match", "skill"),
                name="matchskill_match_skill_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="matchskill",
            constraint=models.UniqueConstraint(
                fields=("match", "code_snapshot"),
                name="matchskill_match_code_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="skilluse",
            index=models.Index(
                fields=["match", "used_at"],
                name="skilluse_match_used_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="skilluse",
            constraint=models.UniqueConstraint(
                fields=("source_player", "idempotency_key"),
                name="skilluse_player_idem_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="skilleffect",
            constraint=models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("started_at")),
                name="skilleffect_expires_after_start",
            ),
        ),
        migrations.RunPython(
            seed_skills_and_reconcile_matches,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
