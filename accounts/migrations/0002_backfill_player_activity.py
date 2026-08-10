from django.db import migrations
from django.utils import timezone


def backfill_player_activity(apps, schema_editor):
    Submission = apps.get_model("matches", "Submission")
    PlayerActivityDay = apps.get_model("accounts", "PlayerActivityDay")

    pending_rows = []
    previous_key = None
    submissions = (
        Submission.objects.order_by("player__user_id", "received_at", "id")
        .values_list("player__user_id", "received_at")
        .iterator(chunk_size=1000)
    )
    for user_id, received_at in submissions:
        activity_date = timezone.localdate(received_at)
        key = (user_id, activity_date)
        if key == previous_key:
            continue
        pending_rows.append(
            PlayerActivityDay(
                user_id=user_id,
                activity_date=activity_date,
                first_activity_at=received_at,
            )
        )
        previous_key = key
        if len(pending_rows) >= 1000:
            PlayerActivityDay.objects.bulk_create(
                pending_rows,
                ignore_conflicts=True,
            )
            pending_rows.clear()

    if pending_rows:
        PlayerActivityDay.objects.bulk_create(
            pending_rows,
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_playeractivityday"),
        ("matches", "0017_ai_review_on_demand"),
    ]

    operations = [
        migrations.RunPython(
            backfill_player_activity,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
