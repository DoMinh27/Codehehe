from django.db import migrations


NEW_SKILLS = {
    "MIRROR_CODE": (
        "Đảo chiều code",
        "Đảo chiều vùng soạn thảo của đối thủ",
    ),
    "BLUR_STATEMENT": (
        "Che mờ đề",
        "Che mờ đề bài và ví dụ của đối thủ",
    ),
    "TIME_DRAIN_60": (
        "Trừ thời gian",
        "Rút ngắn thời gian làm bài của đối thủ",
    ),
    "TYPING_CHALLENGE": (
        "Thử thách gõ chữ",
        "Khóa thao tác cho đến khi đối thủ hoàn thành thử thách "
        "hoặc hết thời gian",
    ),
    "PURIFY": (
        "Thanh tẩy",
        "Hóa giải hiệu ứng bất lợi mới nhất đang tác động",
    ),
    "STEAL": (
        "Tước đoạt",
        "Lấy ngẫu nhiên 1 lượt kỹ năng của đối thủ",
    ),
    "SHIELD": (
        "Khiên",
        "Chặn kỹ năng tấn công tiếp theo",
    ),
}

OLD_SKILLS = {
    "MIRROR_CODE": (
        "Đảo chiều code",
        "Buộc editor của đối thủ hiển thị từ phải sang trái",
    ),
    "BLUR_STATEMENT": (
        "Làm mờ đề",
        "Làm mờ đề bài và ví dụ của đối thủ",
    ),
    "TIME_DRAIN_60": (
        "Trừ thời gian",
        "Trừ 60 giây làm bài của đối thủ",
    ),
    "TYPING_CHALLENGE": (
        "Thử thách gõ chữ",
        "Khóa Run, Submit và Skill của đối thủ cho đến khi gõ đúng câu "
        "hoặc hết 20 giây",
    ),
    "PURIFY": (
        "Thanh tẩy",
        "Xóa hiệu ứng đang chịu mới nhất, kể cả Thử thách gõ chữ. "
        "Không hoàn lại thời gian đã mất",
    ),
    "STEAL": (
        "Steal",
        "Đánh cắp ngẫu nhiên một skill còn lượt của đối thủ. "
        "Không thể đánh cắp Steal",
    ),
    "SHIELD": (
        "Shield",
        "Chặn skill tấn công hợp lệ tiếp theo trong tối đa 45 giây",
    ),
}


def update_skills(apps, values):
    skill_model = apps.get_model("matches", "Skill")
    match_skill_model = apps.get_model("matches", "MatchSkill")
    for code, (name, description) in values.items():
        skill_model.objects.filter(code=code).update(
            name=name,
            description=description,
        )
        match_skill_model.objects.filter(code_snapshot=code).update(
            name_snapshot=name,
            description_snapshot=description,
        )


def apply_presentation(apps, schema_editor):
    update_skills(apps, NEW_SKILLS)


def restore_presentation(apps, schema_editor):
    update_skills(apps, OLD_SKILLS)


class Migration(migrations.Migration):
    dependencies = [("matches", "0026_update_skill_microcopy")]

    operations = [
        migrations.RunPython(apply_presentation, restore_presentation),
    ]
