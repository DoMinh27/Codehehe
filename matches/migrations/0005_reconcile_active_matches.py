from django.db import migrations
from django.utils import timezone


def reconcile_active_matches(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    MatchPlayer = apps.get_model("matches", "MatchPlayer")

    MatchPlayer.objects.update(is_active=False)
    occupied_user_ids = set()
    active_matches = list(
        Match.objects.filter(status="PLAYING").order_by(
            "-started_at", "-created_at", "-id"
        )
    )
    active_matches.extend(
        Match.objects.filter(status="WAITING").order_by("-created_at", "-id")
    )

    for match in active_matches:
        players = list(
            MatchPlayer.objects.filter(match_id=match.id)
            .exclude(slot__isnull=True)
            .order_by("slot", "id")
        )
        valid_player_count = (
            len(players) == 2
            if match.status == "PLAYING"
            else len(players) in {1, 2}
        )
        has_user_conflict = any(
            player.user_id in occupied_user_ids for player in players
        )
        has_extra_players = (
            MatchPlayer.objects.filter(match_id=match.id).count() != len(players)
        )
        if not valid_player_count or has_user_conflict or has_extra_players:
            match.status = "CANCELLED"
            if match.started_at is not None and match.ended_at is None:
                match.ended_at = timezone.now()
                match.save(update_fields=["status", "ended_at", "updated_at"])
            else:
                match.save(update_fields=["status", "updated_at"])
            continue

        MatchPlayer.objects.filter(id__in=[player.id for player in players]).update(
            is_active=True
        )
        occupied_user_ids.update(player.user_id for player in players)


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0004_match_integrity_and_test_snapshots"),
    ]

    operations = [
        migrations.RunPython(
            reconcile_active_matches,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
