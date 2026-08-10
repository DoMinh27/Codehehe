from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerActivityDay",
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
                ("activity_date", models.DateField()),
                ("first_activity_at", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_days",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-activity_date", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="playeractivityday",
            constraint=models.UniqueConstraint(
                fields=("user", "activity_date"),
                name="player_activity_user_date_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="playeractivityday",
            index=models.Index(
                fields=["user", "-activity_date"],
                name="player_activity_user_day_idx",
            ),
        ),
    ]
