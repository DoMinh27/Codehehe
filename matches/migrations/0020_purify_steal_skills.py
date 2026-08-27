from django.db import migrations, models


SKILLS = (
    {
        "code": "PURIFY",
        "name": "Thanh tẩy",
        "description": (
            "Xóa hiệu ứng đang chịu mới nhất, kể cả Thử thách gõ chữ. "
            "Không hoàn lại thời gian đã mất."
        ),
        "energy_cost": 1,
        "duration_seconds": None,
    },
    {
        "code": "STEAL",
        "name": "Steal",
        "description": (
            "Đánh cắp ngẫu nhiên một skill còn lượt của đối thủ. "
            "Không thể đánh cắp Steal."
        ),
        "energy_cost": 2,
        "duration_seconds": None,
    },
)


def seed_purify_and_steal(apps, schema_editor):
    skill_model = apps.get_model("matches", "Skill")
    for definition in SKILLS:
        skill_model.objects.update_or_create(
            code=definition["code"],
            defaults={**definition, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0019_operations_dashboard_integrity_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="skilluse",
            name="outcome_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(
            seed_purify_and_steal,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
