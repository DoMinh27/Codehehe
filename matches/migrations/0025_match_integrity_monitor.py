from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("matches", "0024_seed_shield")]

    operations = [
        migrations.AddField(
            model_name="match",
            name="integrity_monitor_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="match",
            name="integrity_policy_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="MatchIntegrityState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_heartbeat_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("active_absence_started_at", models.DateTimeField(blank=True, null=True)),
                ("active_absence_kind", models.CharField(blank=True, choices=[("TAB", "Rời tab"), ("PAGE", "Rời trang")], max_length=8)),
                ("active_absence_id", models.CharField(blank=True, max_length=36)),
                ("strike_count", models.PositiveIntegerField(default=0)),
                ("away_duration_ms", models.PositiveBigIntegerField(default=0)),
                ("paste_count", models.PositiveIntegerField(default=0)),
                ("paste_character_count", models.PositiveBigIntegerField(default=0)),
                ("is_flagged", models.BooleanField(db_index=True, default=False)),
                ("flagged_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("flag_reason", models.CharField(blank=True, choices=[("STRIKES", "Vượt số lần vi phạm"), ("AWAY_TIME", "Vượt tổng thời gian vắng mặt"), ("CONNECTION_GAP", "Mất heartbeat")], max_length=24)),
                ("processed_event_ids", models.JSONField(blank=True, default=list, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("player", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="integrity_state", to="matches.matchplayer")),
            ],
            options={"ordering": ["player_id"]},
        ),
        migrations.CreateModel(
            name="MatchIntegrityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("TAB_AWAY", "Rời tab"), ("PAGE_AWAY", "Rời trang"), ("CONNECTION_GAP", "Mất heartbeat"), ("PASTE", "Paste vào trình soạn thảo"), ("FLAGGED", "Gắn cờ Fair Play")], db_index=True, max_length=24)),
                ("severity", models.CharField(choices=[("INFO", "Thông tin"), ("WARNING", "Cảnh báo")], db_index=True, default="INFO", max_length=12)),
                ("event_key", models.CharField(max_length=96)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.PositiveBigIntegerField(default=0)),
                ("value", models.PositiveBigIntegerField(default=0)),
                ("recorded_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integrity_events", to="matches.match")),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integrity_events", to="matches.matchplayer")),
            ],
            options={
                "ordering": ["id"],
                "indexes": [
                    models.Index(fields=["match", "player", "id"], name="integrity_match_player_idx"),
                    models.Index(fields=["kind", "recorded_at"], name="integrity_kind_time_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("match", "player", "event_key"), name="integrity_event_key_unique"),
                ],
            },
        ),
    ]
