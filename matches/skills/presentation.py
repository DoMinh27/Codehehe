"""Safe, viewer-specific presentation for Battle Skills."""

from dataclasses import dataclass

from .definitions import (
    BLUR_STATEMENT,
    MIRROR_CODE,
    PURIFY,
    SHIELD,
    STEAL,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
)


@dataclass(frozen=True)
class SkillPresentation:
    name: str
    description: str
    target_label: str
    special_rule: str | None = None


SKILL_PRESENTATIONS = {
    MIRROR_CODE: SkillPresentation(
        name="Đảo chiều code",
        description="Đảo chiều vùng soạn thảo của đối thủ",
        target_label="Đối thủ",
    ),
    BLUR_STATEMENT: SkillPresentation(
        name="Che mờ đề",
        description="Che mờ đề bài và ví dụ của đối thủ",
        target_label="Đối thủ",
    ),
    TIME_DRAIN_60: SkillPresentation(
        name="Trừ thời gian",
        description="Rút ngắn thời gian làm bài của đối thủ",
        target_label="Đối thủ",
    ),
    TYPING_CHALLENGE: SkillPresentation(
        name="Thử thách gõ chữ",
        description=(
            "Khóa thao tác cho đến khi đối thủ hoàn thành thử thách "
            "hoặc hết thời gian"
        ),
        target_label="Đối thủ",
    ),
    PURIFY: SkillPresentation(
        name="Thanh tẩy",
        description="Hóa giải hiệu ứng bất lợi mới nhất đang tác động",
        target_label="Bản thân",
        special_rule="Không hoàn lại thời gian đã mất",
    ),
    STEAL: SkillPresentation(
        name="Tước đoạt",
        description="Lấy ngẫu nhiên 1 lượt kỹ năng của đối thủ",
        target_label="Đối thủ",
        special_rule="Không thể lấy Tước đoạt",
    ),
    SHIELD: SkillPresentation(
        name="Khiên",
        description="Chặn kỹ năng tấn công tiếp theo",
        target_label="Bản thân",
    ),
}


def presentation_for(code):
    return SKILL_PRESENTATIONS.get(code)


def display_skill_name(code, fallback="Kỹ năng"):
    presentation = presentation_for(code)
    return presentation.name if presentation is not None else fallback


def effect_label(*, code, duration_seconds, time_drain_seconds):
    if code == TIME_DRAIN_60:
        return f"−{time_drain_seconds} giây"
    if code == TYPING_CHALLENGE:
        return f"Tối đa {duration_seconds} giây"
    if code == SHIELD:
        return f"1 đòn hoặc {duration_seconds} giây"
    if duration_seconds is not None:
        return f"{duration_seconds} giây"
    return "Tức thời"


def combat_feedback_for(*, skill_use, viewer_player, time_drain_seconds):
    """Return the one safe Battle message visible to ``viewer_player``."""
    is_source = skill_use.source_player_id == viewer_player.pk
    is_target = skill_use.target_player_id == viewer_player.pk
    if not is_source and not is_target:
        return None

    code = skill_use.match_skill.code_snapshot
    name = display_skill_name(code, skill_use.match_skill.name_snapshot)
    outcome = skill_use.outcome_snapshot
    outcome_kind = outcome.get("kind")
    affected_name = display_skill_name(
        outcome.get("skill_code"),
        outcome.get("skill_name", "kỹ năng"),
    )

    if outcome_kind == "BLOCKED_BY_SHIELD":
        if is_source:
            text, cue, tone = "Đòn đã bị chặn", "SHIELD_BLOCKED_ATTACK", "WARNING"
        else:
            text = f"Khiên đã chặn {name}"
            cue, tone = "SHIELD_BLOCK", "SUCCESS"
    elif code == SHIELD:
        if not is_source:
            return None
        text, cue, tone = "Khiên đã sẵn sàng", "SHIELD_READY", "SUCCESS"
    elif code == PURIFY:
        if not is_source:
            return None
        text = f"Đã hóa giải {affected_name}"
        cue, tone = "PURIFY", "SUCCESS"
    elif code == STEAL:
        if is_source:
            text, cue, tone = (
                f"Nhận được 1 lượt {affected_name}",
                "STEAL_GAIN",
                "SUCCESS",
            )
        else:
            text, cue, tone = (
                f"Bạn mất 1 lượt {affected_name}",
                "STEAL_LOSS",
                "WARNING",
            )
    elif code == TIME_DRAIN_60:
        if is_source:
            text, cue, tone = "Đã dùng Trừ thời gian", "SKILL_USED", "SUCCESS"
        else:
            text = f"Bạn bị trừ {time_drain_seconds} giây"
            cue, tone = "TIME_DRAIN_HIT", "WARNING"
    elif is_source:
        text, cue, tone = f"Đã dùng {name}", "SKILL_USED", "SUCCESS"
    else:
        cue_by_code = {
            MIRROR_CODE: "MIRROR_HIT",
            BLUR_STATEMENT: "BLUR_HIT",
            TYPING_CHALLENGE: "TYPING_HIT",
        }
        text = f"Bạn đang bị {name}"
        cue, tone = cue_by_code.get(code, "SKILL_HIT"), "WARNING"

    return {
        "id": skill_use.pk,
        "text": text,
        "cue": cue,
        "tone": tone,
        "created_at": skill_use.used_at.isoformat(),
    }
