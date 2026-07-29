import matches.rules
from django.db import migrations, models


CURRENT_RULESET_VERSION = "v3.1"
DEFAULT_SKILL_CODES = [
    "MIRROR_CODE",
    "BLUR_STATEMENT",
    "TIME_DRAIN_60",
    "TYPING_CHALLENGE",
]
TYPING_PROMPTS = [
    "practice makes progress",
    "focus on the next test",
    "debug one step at a time",
    "clean code is easier to trust",
    "nguoi tAy BaC toi an gio an SuonWG",
    "english or spanish",
    "toi dOng tiNh",
    "toi rat dong tinh",
    "67676767676767",
    "danh mat em",
    "EmOiLAUdaiTinhaIdO",
]


def build_snapshot(*, duration_seconds, problem_counts, skill_codes):
    return {
        "match_duration_seconds": duration_seconds,
        "problem_counts": problem_counts,
        "scoring": {
            "first_solve_bonus": 1,
        },
        "energy": {
            "max": 3,
            "per_first_solve": 1,
        },
        "required_skill_codes": skill_codes,
        "skill_effects": {
            "TIME_DRAIN_60": {
                "time_penalty_seconds": 60,
            },
        },
        "typing": {
            "prompts": TYPING_PROMPTS,
        },
    }


def backfill_rulesets(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    MatchProblem = apps.get_model("matches", "MatchProblem")
    MatchSkill = apps.get_model("matches", "MatchSkill")

    for match in Match.objects.all().iterator():
        frozen_difficulties = list(
            MatchProblem.objects.filter(match_id=match.pk).values_list(
                "difficulty_snapshot",
                flat=True,
            )
        )
        if frozen_difficulties:
            problem_counts = {
                "EASY": frozen_difficulties.count("EASY"),
                "MEDIUM": frozen_difficulties.count("MEDIUM"),
                "HARD": frozen_difficulties.count("HARD"),
            }
        else:
            problem_counts = {
                "EASY": 2,
                "MEDIUM": 1,
                "HARD": 1,
            }

        frozen_skill_codes = list(
            MatchSkill.objects.filter(match_id=match.pk)
            .order_by("id")
            .values_list("code_snapshot", flat=True)
        )
        match.ruleset_version = CURRENT_RULESET_VERSION
        match.rules_snapshot = build_snapshot(
            duration_seconds=match.duration_seconds,
            problem_counts=problem_counts,
            skill_codes=frozen_skill_codes or DEFAULT_SKILL_CODES,
        )
        match.save(
            update_fields=[
                "ruleset_version",
                "rules_snapshot",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0012_typing_challenge"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="ruleset_version",
            field=models.CharField(
                default=CURRENT_RULESET_VERSION,
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="match",
            name="rules_snapshot",
            field=models.JSONField(default=dict),
        ),
        migrations.RunPython(
            backfill_rulesets,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="match",
            name="rules_snapshot",
            field=models.JSONField(
                default=matches.rules.default_v3_rules_snapshot,
            ),
        ),
    ]
