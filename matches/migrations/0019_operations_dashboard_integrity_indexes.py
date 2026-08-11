from django.db import migrations, models


def backfill_cancelled_match_ended_at(apps, schema_editor):
    match_model = apps.get_model("matches", "Match")
    match_model.objects.filter(
        status="CANCELLED",
        ended_at__isnull=True,
    ).update(ended_at=models.F("updated_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0018_player_history_support"),
    ]

    operations = [
        migrations.RunPython(
            backfill_cancelled_match_ended_at,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="submissionaireview",
            index=models.Index(
                fields=["status", "updated_at"],
                name="ai_review_status_updated_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="submissionaireview",
            index=models.Index(
                fields=["completed_at"],
                name="ai_review_completed_idx",
            ),
        ),
    ]
