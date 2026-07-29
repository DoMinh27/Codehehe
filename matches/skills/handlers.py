"""Server-authoritative Skill effect handlers."""

from datetime import timedelta
from secrets import choice

from matches.models import MatchPlayer, SkillEffect, SkillUse, TypingChallenge
from matches.rules import MatchRules

from .definitions import SKILL_REGISTRY


class SkillHandlerConfigurationError(Exception):
    """Raised when a frozen Skill cannot be handled by this application."""


def apply_skill_effect(
    *,
    skill_use: SkillUse,
    target_player: MatchPlayer,
    rules: MatchRules,
    now,
    prompt_selector=choice,
) -> SkillEffect | None:
    definition = SKILL_REGISTRY.get(skill_use.match_skill.code_snapshot)
    if definition is None:
        raise SkillHandlerConfigurationError("Skill handler is not registered.")

    if definition.effect_kind == "TIME_PENALTY":
        target_player.time_penalty_seconds += rules.time_drain_seconds
        target_player.save(update_fields=["time_penalty_seconds"])
        return None

    duration = skill_use.match_skill.duration_seconds_snapshot
    if definition.effect_kind in {"TIMED", "TYPING_CHALLENGE"} and duration:
        effect = SkillEffect.objects.create(
            skill_use=skill_use,
            started_at=now,
            expires_at=now + timedelta(seconds=duration),
        )
        if definition.effect_kind == "TYPING_CHALLENGE":
            TypingChallenge.objects.create(
                effect=effect,
                prompt=prompt_selector(rules.typing_prompts),
                started_at=effect.started_at,
                expires_at=effect.expires_at,
            )
        return effect

    raise SkillHandlerConfigurationError("Skill effect configuration is invalid.")
