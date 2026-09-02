from dataclasses import asdict, dataclass


MIRROR_CODE = "MIRROR_CODE"
BLUR_STATEMENT = "BLUR_STATEMENT"
TIME_DRAIN_60 = "TIME_DRAIN_60"
TYPING_CHALLENGE = "TYPING_CHALLENGE"
PURIFY = "PURIFY"
STEAL = "STEAL"
SHIELD = "SHIELD"

SELF = "SELF"
OPPONENT = "OPPONENT"
DEFENSIVE = "DEFENSIVE"
OFFENSIVE = "OFFENSIVE"
HARMFUL = "HARMFUL"
BENEFICIAL = "BENEFICIAL"
REJECT_ACTIVE = "REJECT_ACTIVE"
ALLOW_STACK = "ALLOW_STACK"

TIMED_HANDLER = "TIMED"
TIME_PENALTY_HANDLER = "TIME_PENALTY"
TYPING_HANDLER = "TYPING_CHALLENGE"
PURIFY_HANDLER = "PURIFY"
STEAL_HANDLER = "STEAL"
SHIELD_HANDLER = "SHIELD"

REQUIRED_SKILL_CODES = (
    MIRROR_CODE,
    BLUR_STATEMENT,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
    PURIFY,
    STEAL,
    SHIELD,
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
    handler: str
    target_mode: str = OPPONENT
    category: str = OFFENSIVE
    disposition: str = HARMFUL
    dispellable: bool = False
    shieldable: bool = True
    stacking: str = ALLOW_STACK
    can_use_while_action_locked: bool = False
    ui_group: str = OFFENSIVE

    def __post_init__(self):
        if self.handler not in {
            TIMED_HANDLER,
            TIME_PENALTY_HANDLER,
            TYPING_HANDLER,
            PURIFY_HANDLER,
            STEAL_HANDLER,
            SHIELD_HANDLER,
        }:
            raise ValueError("Skill handler is invalid.")
        if self.target_mode not in {SELF, OPPONENT}:
            raise ValueError("Skill target mode is invalid.")
        if self.category not in {DEFENSIVE, OFFENSIVE}:
            raise ValueError("Skill category is invalid.")
        if self.disposition not in {HARMFUL, BENEFICIAL}:
            raise ValueError("Skill disposition is invalid.")
        if self.stacking not in {REJECT_ACTIVE, ALLOW_STACK}:
            raise ValueError("Skill stacking policy is invalid.")
        if self.ui_group not in {DEFENSIVE, OFFENSIVE}:
            raise ValueError("Skill UI group is invalid.")

    def to_policy_snapshot(self):
        policy = asdict(self)
        policy.pop("code")
        return policy


SKILL_REGISTRY = {
    MIRROR_CODE: SkillDefinition(
        MIRROR_CODE,
        TIMED_HANDLER,
        dispellable=True,
        stacking=REJECT_ACTIVE,
    ),
    BLUR_STATEMENT: SkillDefinition(
        BLUR_STATEMENT,
        TIMED_HANDLER,
        dispellable=True,
        stacking=REJECT_ACTIVE,
    ),
    TIME_DRAIN_60: SkillDefinition(TIME_DRAIN_60, TIME_PENALTY_HANDLER),
    TYPING_CHALLENGE: SkillDefinition(
        TYPING_CHALLENGE,
        TYPING_HANDLER,
        dispellable=True,
        stacking=REJECT_ACTIVE,
    ),
    PURIFY: SkillDefinition(
        PURIFY,
        PURIFY_HANDLER,
        target_mode=SELF,
        category=DEFENSIVE,
        disposition=BENEFICIAL,
        shieldable=False,
        can_use_while_action_locked=True,
        ui_group=DEFENSIVE,
    ),
    STEAL: SkillDefinition(STEAL, STEAL_HANDLER),
    SHIELD: SkillDefinition(
        SHIELD,
        SHIELD_HANDLER,
        target_mode=SELF,
        category=DEFENSIVE,
        disposition=BENEFICIAL,
        shieldable=False,
        stacking=REJECT_ACTIVE,
        ui_group=DEFENSIVE,
    ),
}


def policy_for_match_skill(match_skill):
    definition = SKILL_REGISTRY.get(match_skill.code_snapshot)
    if definition is None:
        raise ValueError("Skill policy is not registered.")
    template = definition.to_policy_snapshot()
    snapshot = match_skill.policy_snapshot
    if not snapshot:
        raise ValueError("Frozen Skill policy is missing.")
    if set(snapshot) != set(template):
        raise ValueError("Frozen Skill policy is invalid.")
    if any(type(snapshot[key]) is not type(template[key]) for key in template):
        raise ValueError("Frozen Skill policy has invalid value types.")
    return SkillDefinition(code=match_skill.code_snapshot, **snapshot)
