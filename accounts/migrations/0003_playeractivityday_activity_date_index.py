from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_backfill_player_activity"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="playeractivityday",
            index=models.Index(
                fields=["activity_date"],
                name="player_activity_date_idx",
            ),
        ),
    ]
