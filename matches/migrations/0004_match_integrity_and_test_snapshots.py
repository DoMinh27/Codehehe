from django.db import migrations, models


def backfill_integrity_fields(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    MatchPlayer = apps.get_model("matches", "MatchPlayer")
    MatchProblem = apps.get_model("matches", "MatchProblem")
    TestCase = apps.get_model("problems", "TestCase")

    active_user_ids = set()
    active_statuses = {"WAITING", "PLAYING"}
    matches = Match.objects.order_by("-started_at", "-created_at", "-id")
    for match in matches.iterator():
        players = list(
            MatchPlayer.objects.filter(match_id=match.id).order_by(
                "-is_host", "joined_at", "id"
            )
        )
        for index, player in enumerate(players, start=1):
            player.slot = index if index <= 2 else None
            player.is_active = (
                index <= 2
                and match.status in active_statuses
                and player.user_id not in active_user_ids
            )
            if player.is_active:
                active_user_ids.add(player.user_id)
            player.save(update_fields=["slot", "is_active"])

    for match_problem in MatchProblem.objects.iterator():
        test_cases = TestCase.objects.filter(
            problem_id=match_problem.problem_id
        ).order_by("order", "id")
        samples = []
        hidden = []
        for test_case in test_cases.iterator():
            snapshot = {
                "input_data": test_case.input_data,
                "expected_output": test_case.expected_output,
            }
            if test_case.is_sample:
                samples.append(snapshot)
            else:
                hidden.append(snapshot)
        match_problem.sample_tests_snapshot = samples
        match_problem.hidden_tests_snapshot = hidden
        match_problem.save(
            update_fields=["sample_tests_snapshot", "hidden_tests_snapshot"]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0003_match_finish_reason_surrendered_by"),
        ("problems", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchplayer",
            name="is_active",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="matchplayer",
            name="slot",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="matchproblem",
            name="hidden_tests_snapshot",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="matchproblem",
            name="sample_tests_snapshot",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="submission",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.RunPython(
            backfill_integrity_fields,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="matchplayer",
            constraint=models.UniqueConstraint(
                condition=models.Q(slot__isnull=False),
                fields=("match", "slot"),
                name="matchplayer_match_slot_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="matchplayer",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=("user",),
                name="matchplayer_one_active_per_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="matchplayer",
            constraint=models.CheckConstraint(
                condition=models.Q(slot__in=[1, 2]) | models.Q(slot__isnull=True),
                name="matchplayer_slot_1_or_2",
            ),
        ),
        migrations.AddConstraint(
            model_name="submission",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=("player", "match_problem", "idempotency_key"),
                name="submission_player_problem_idem_unique",
            ),
        ),
    ]
