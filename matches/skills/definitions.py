from dataclasses import dataclass


MIRROR_CODE = "MIRROR_CODE"
BLUR_STATEMENT = "BLUR_STATEMENT"
TIME_DRAIN_60 = "TIME_DRAIN_60"
TYPING_CHALLENGE = "TYPING_CHALLENGE"
REQUIRED_SKILL_CODES = (
    MIRROR_CODE,
    BLUR_STATEMENT,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
)
TIME_DRAIN_SECONDS = 60
TYPING_PROMPTS = (
    "practice makes progress",
    "focus on the next test",
    "debug one step at a time",
    "clean code is easier to trust",
    "nguoi tAy BaC toi an gio an SuonWG",
    "english or spanish",
    "toi dOng tiNh",
    "toi rat dong tinh",
    "67676767676767",
    "danh mat em",
    "EmOiLAUdaiTinhaIdO",
)


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
    TYPING_CHALLENGE: SkillDefinition(TYPING_CHALLENGE, "TYPING_CHALLENGE"),
}
