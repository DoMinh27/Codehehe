from dataclasses import dataclass


MIRROR_CODE = "MIRROR_CODE"
BLUR_STATEMENT = "BLUR_STATEMENT"
TIME_DRAIN_60 = "TIME_DRAIN_60"
REQUIRED_SKILL_CODES = (MIRROR_CODE, BLUR_STATEMENT, TIME_DRAIN_60)
TIME_DRAIN_SECONDS = 60


@dataclass(frozen=True)
class SkillDefinition:
    code: str
    effect_kind: str
    time_penalty_seconds: int = 0


SKILL_REGISTRY = {
    MIRROR_CODE: SkillDefinition(MIRROR_CODE, "TIMED"),
    BLUR_STATEMENT: SkillDefinition(BLUR_STATEMENT, "TIMED"),
    TIME_DRAIN_60: SkillDefinition(
        TIME_DRAIN_60,
        "TIME_PENALTY",
        time_penalty_seconds=TIME_DRAIN_SECONDS,
    ),
}

