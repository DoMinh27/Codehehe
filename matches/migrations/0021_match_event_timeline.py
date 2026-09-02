import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("matches", "0020_purify_steal_skills")]

    operations = [
        migrations.AddField(
            model_name="match",
            name="timeline_version",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="MatchEvent",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("MATCH_STARTED", "Bắt đầu trận"),
                            ("PROBLEM_SOLVED", "Giải được bài"),
                            ("FIRST_SOLVE_CONFIRMED", "Người giải đầu tiên"),
                            ("REWARD_GRANTED", "Nhận phần thưởng"),
                            ("SKILL_USED", "Sử dụng Skill"),
                            ("TYPING_COMPLETED", "Hoàn thành thử thách gõ chữ"),
                            ("PLAYER_SURRENDERED", "Đầu hàng"),
                            ("MATCH_FINISHED", "Kết thúc trận"),
                        ],
                        max_length=32,
                    ),
                ),
                ("actor_name_snapshot", models.CharField(blank=True, max_length=150)),
                ("target_name_snapshot", models.CharField(blank=True, max_length=150)),
                (
                    "recorded_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("event_key", models.CharField(max_length=128)),
                ("payload", models.JSONField(default=dict)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events_as_actor",
                        to="matches.matchplayer",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events_as_target",
                        to="matches.matchplayer",
                    ),
                ),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="matches.match",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
                "indexes": [
                    models.Index(fields=["match", "id"], name="matchevent_match_id_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("match", "event_key"),
                        name="matchevent_match_key_unique",
                    )
                ],
            },
        ),
    ]
