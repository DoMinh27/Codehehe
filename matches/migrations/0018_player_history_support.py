from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("matches", "0017_ai_review_on_demand"),
    ]

    operations = [
        migrations.AlterField(
            model_name="matchplayer",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="match_players",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="submission",
            index=models.Index(
                fields=["player", "match_problem", "-received_at", "-id"],
                name="sub_player_prob_time_idx",
            ),
        ),
    ]
