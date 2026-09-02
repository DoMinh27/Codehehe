from django.db import migrations, models


POLICIES = {
    "MIRROR_CODE": {
        "handler": "TIMED",
        "target_mode": "OPPONENT",
        "category": "OFFENSIVE",
        "disposition": "HARMFUL",
        "dispellable": True,
        "shieldable": True,
        "stacking": "REJECT_ACTIVE",
        "can_use_while_action_locked": False,
        "ui_group": "OFFENSIVE",
    },
    "BLUR_STATEMENT": {
        "handler": "TIMED",
        "target_mode": "OPPONENT",
        "category": "OFFENSIVE",
        "disposition": "HARMFUL",
        "dispellable": True,
        "shieldable": True,
        "stacking": "REJECT_ACTIVE",
        "can_use_while_action_locked": False,
        "ui_group": "OFFENSIVE",
    },
    "TIME_DRAIN_60": {
        "handler": "TIME_PENALTY",
        "target_mode": "OPPONENT",
        "category": "OFFENSIVE",
        "disposition": "HARMFUL",
        "dispellable": False,
        "shieldable": True,
        "stacking": "ALLOW_STACK",
        "can_use_while_action_locked": False,
        "ui_group": "OFFENSIVE",
    },
    "TYPING_CHALLENGE": {
        "handler": "TYPING_CHALLENGE",
        "target_mode": "OPPONENT",
        "category": "OFFENSIVE",
        "disposition": "HARMFUL",
        "dispellable": True,
        "shieldable": True,
        "stacking": "REJECT_ACTIVE",
        "can_use_while_action_locked": False,
        "ui_group": "OFFENSIVE",
    },
    "PURIFY": {
        "handler": "PURIFY",
        "target_mode": "SELF",
        "category": "DEFENSIVE",
        "disposition": "BENEFICIAL",
        "dispellable": False,
        "shieldable": False,
        "stacking": "ALLOW_STACK",
        "can_use_while_action_locked": True,
        "ui_group": "DEFENSIVE",
    },
    "STEAL": {
        "handler": "STEAL",
        "target_mode": "OPPONENT",
        "category": "OFFENSIVE",
        "disposition": "HARMFUL",
        "dispellable": False,
        "shieldable": True,
        "stacking": "ALLOW_STACK",
        "can_use_while_action_locked": False,
        "ui_group": "OFFENSIVE",
    },
}


def backfill_policies(apps, schema_editor):
    match_skill_model = apps.get_model("matches", "MatchSkill")
    for code, policy in POLICIES.items():
        match_skill_model.objects.filter(code_snapshot=code).update(
            policy_snapshot=policy
        )


class Migration(migrations.Migration):
    dependencies = [("matches", "0022_rematch_request")]

    operations = [
        migrations.AddField(
            model_name="matchskill",
            name="policy_snapshot",
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="skilleffect",
            name="consumed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="skilleffect",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(cancelled_at__isnull=True)
                    | models.Q(consumed_at__isnull=True)
                ),
                name="skilleffect_not_cancelled_and_consumed",
            ),
        ),
        migrations.RunPython(backfill_policies, migrations.RunPython.noop),
    ]
