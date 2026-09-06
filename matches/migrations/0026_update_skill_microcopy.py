from django.db import migrations


DESCRIPTIONS = {
    "MIRROR_CODE": "Buộc editor của đối thủ hiển thị từ phải sang trái",
    "BLUR_STATEMENT": "Làm mờ đề bài và ví dụ của đối thủ",
    "TIME_DRAIN_60": "Trừ 60 giây làm bài của đối thủ",
    "TYPING_CHALLENGE": (
        "Khóa Run, Submit và Skill của đối thủ cho đến khi "
        "gõ đúng câu hoặc hết 20 giây"
    ),
    "PURIFY": (
        "Xóa hiệu ứng đang chịu mới nhất, kể cả Thử thách gõ chữ. "
        "Không hoàn lại thời gian đã mất"
    ),
    "STEAL": (
        "Đánh cắp ngẫu nhiên một skill còn lượt của đối thủ. "
        "Không thể đánh cắp Steal"
    ),
    "SHIELD": "Chặn skill tấn công hợp lệ tiếp theo trong tối đa 45 giây",
}


def update_skill_microcopy(apps, schema_editor):
    skill_model = apps.get_model("matches", "Skill")
    match_skill_model = apps.get_model("matches", "MatchSkill")
    for code, description in DESCRIPTIONS.items():
        skill_model.objects.filter(code=code).update(description=description)
        match_skill_model.objects.filter(code_snapshot=code).update(
            description_snapshot=description
        )


def restore_skill_microcopy(apps, schema_editor):
    skill_model = apps.get_model("matches", "Skill")
    match_skill_model = apps.get_model("matches", "MatchSkill")
    for code, description in DESCRIPTIONS.items():
        old_description = f"{description}."
        skill_model.objects.filter(code=code).update(description=old_description)
        match_skill_model.objects.filter(code_snapshot=code).update(
            description_snapshot=old_description
        )


class Migration(migrations.Migration):
    dependencies = [("matches", "0025_match_integrity_monitor")]

    operations = [
        migrations.RunPython(update_skill_microcopy, restore_skill_microcopy),
    ]
