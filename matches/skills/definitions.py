from dataclasses import dataclass


MIRROR_CODE = "MIRROR_CODE"
BLUR_STATEMENT = "BLUR_STATEMENT"
TIME_DRAIN_60 = "TIME_DRAIN_60"
TYPING_CHALLENGE = "TYPING_CHALLENGE"
PURIFY = "PURIFY"
STEAL = "STEAL"
DEFENSIVE = "DEFENSIVE"
OFFENSIVE = "OFFENSIVE"
REQUIRED_SKILL_CODES = (
    MIRROR_CODE,
    BLUR_STATEMENT,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
    PURIFY,
    STEAL,
)
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
    target_mode: str = "OPPONENT"
    can_use_while_action_locked: bool = False
    ui_group: str = OFFENSIVE


SKILL_REGISTRY = {
    MIRROR_CODE: SkillDefinition(MIRROR_CODE, "TIMED"),
    BLUR_STATEMENT: SkillDefinition(BLUR_STATEMENT, "TIMED"),
    TIME_DRAIN_60: SkillDefinition(
        TIME_DRAIN_60,
        "TIME_PENALTY",
    ),
    TYPING_CHALLENGE: SkillDefinition(TYPING_CHALLENGE, "TYPING_CHALLENGE"),
    PURIFY: SkillDefinition(
        PURIFY,
        "PURIFY",
        target_mode="SELF",
        can_use_while_action_locked=True,
        ui_group=DEFENSIVE,
    ),
    STEAL: SkillDefinition(STEAL, "STEAL"),
}
