from django.conf import settings
from django.db import models


class PlayerActivityDay(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_days",
    )
    activity_date = models.DateField()
    first_activity_at = models.DateTimeField()

    class Meta:
        ordering = ["-activity_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "activity_date"],
                name="player_activity_user_date_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-activity_date"],
                name="player_activity_user_day_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} active on {self.activity_date}"
