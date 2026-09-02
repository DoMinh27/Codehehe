from dataclasses import dataclass, field
from datetime import timedelta
from secrets import choice
from django.db.models import Count, Q

from matches.models import (
    Match,
    MatchPlayer,
    MatchPlayerSkill,
    MatchSkill,
    PlayerProblemProgress,
    SkillEffect,
    TypingChallenge,
)
from matches.rules import MatchRules

from .definitions import (
    HARMFUL,
    OPPONENT,
    PURIFY_HANDLER,
    REJECT_ACTIVE,
    SELF,
    SHIELD,
    SHIELD_HANDLER,
    STEAL,
    STEAL_HANDLER,
    TIME_PENALTY_HANDLER,
    TIMED_HANDLER,
    TYPING_HANDLER,
    SkillDefinition,
    policy_for_match_skill,
)
from .effects import active_effects_for_player
from .typing import has_active_typing_challenge


class SkillEngineConfigurationError(Exception):
    pass


class SkillTargetError(Exception):
    pass


class SkillConditionError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass
class SkillPreparation:
    purified_effect: SkillEffect | None = None
    stealable_inventory: list[MatchPlayerSkill] = field(default_factory=list)
    selected_inventory: MatchPlayerSkill | None = None


@dataclass(frozen=True)
class SkillAvailabilityFacts:
    active_match_skill_ids: frozenset[int] = frozenset()
    has_dispellable_effect: bool = False
    has_stealable_skill: bool = False
    target_finished: bool = False


@dataclass(frozen=True)
class SkillContext:
    match: Match
    source: MatchPlayer
    target: MatchPlayer
    match_skill: MatchSkill
    policy: SkillDefinition
    rules: MatchRules
    now: object


def validate_target(*, source, target, policy):
    if source.match_id != target.match_id:
        raise SkillTargetError("Target must be a player in this match.")
    if policy.target_mode == SELF and target.pk != source.pk:
        raise SkillTargetError("Target must be yourself.")
    if policy.target_mode == OPPONENT and target.pk == source.pk:
        raise SkillTargetError("Target must be your opponent in this match.")
    if policy.target_mode not in {SELF, OPPONENT}:
        raise SkillEngineConfigurationError("Skill target mode is unsupported.")


def validate_common(*, context, quantity, action_locked=None):
    if context.match.status != Match.Status.PLAYING or context.match.ends_at is None:
        raise SkillConditionError("MATCH_NOT_PLAYING", "Match is not playing.")
    source_deadline = context.source.personal_ends_at
    if source_deadline is None or context.now > source_deadline:
        raise SkillConditionError("PLAYER_TIMED_OUT", "Your personal time has ended.")
    locked = (
        has_active_typing_challenge(player_id=context.source.pk, now=context.now)
        if action_locked is None
        else action_locked
    )
    if locked and not context.policy.can_use_while_action_locked:
        raise SkillConditionError(
            "ACTION_LOCKED",
            "Complete the Typing challenge before using a Skill.",
        )
    if quantity < 1:
        raise SkillConditionError("NO_QUANTITY", "You do not have this Skill.")
    if context.source.energy < context.match_skill.energy_cost_snapshot:
        raise SkillConditionError("INSUFFICIENT_ENERGY", "Not enough Energy.")


def validate_and_prepare(
    *,
    context,
    quantity,
    action_locked=None,
    lock=False,
    steal_selector=choice,
    facts=None,
):
    """Run the same target and availability policy for state and execution."""
    validate_target(
        source=context.source,
        target=context.target,
        policy=context.policy,
    )
    validate_common(
        context=context,
        quantity=quantity,
        action_locked=action_locked,
    )
    return prepare_skill(
        context=context,
        lock=lock,
        steal_selector=steal_selector,
        facts=facts,
    )


def prepare_skill(*, context, lock=False, steal_selector=choice, facts=None):
    queryset = active_effects_for_player(
        player=context.target,
        now=context.now,
        lock=lock,
    )
    effect_already_active = (
        context.match_skill.pk in facts.active_match_skill_ids
        if facts is not None
        else queryset.filter(skill_use__match_skill=context.match_skill).exists()
    )
    if context.policy.stacking == REJECT_ACTIVE and effect_already_active:
        raise SkillConditionError(
            "EFFECT_ALREADY_ACTIVE",
            "This effect is already active.",
        )

    if context.policy.handler == TYPING_HANDLER:
        target_deadline = context.target.personal_ends_at
        target_finished = (
            facts.target_finished
            if facts is not None
            else target_deadline is None or context.now >= target_deadline
        )
        if target_finished:
            raise SkillConditionError(
                "TARGET_FINISHED",
                "The opponent has already finished.",
            )
        if facts is None:
            progress = PlayerProblemProgress.objects.filter(
                match=context.match,
                player=context.target,
            ).aggregate(
                total=Count("id"),
                solved=Count("id", filter=Q(is_solved=True)),
            )
            if progress["total"] > 0 and progress["solved"] == progress["total"]:
                raise SkillConditionError(
                    "TARGET_FINISHED",
                    "The opponent has already finished.",
                )

    preparation = SkillPreparation()
    if context.policy.handler == PURIFY_HANDLER:
        if facts is not None:
            if not facts.has_dispellable_effect:
                raise SkillConditionError(
                    "NO_DISPELLABLE_EFFECT",
                    "You have no active effect to purify.",
                )
            return preparation
        candidates = (
            active_effects_for_player(
                player=context.source,
                now=context.now,
                lock=lock,
            )
            .select_related("skill_use__match_skill")
            .order_by("-started_at", "-id")
        )
        preparation.purified_effect = next(
            (
                effect
                for effect in candidates
                if _is_purifiable(effect.skill_use.match_skill)
            ),
            None,
        )
        if preparation.purified_effect is None:
            raise SkillConditionError(
                "NO_DISPELLABLE_EFFECT",
                "You have no active effect to purify.",
            )
    elif context.policy.handler == STEAL_HANDLER:
        if facts is not None:
            if not facts.has_stealable_skill:
                raise SkillConditionError(
                    "NO_STEALABLE_SKILL",
                    "The opponent has no Skill available to steal.",
                )
            return preparation
        inventory = MatchPlayerSkill.objects
        if lock:
            inventory = inventory.select_for_update()
        preparation.stealable_inventory = list(
            inventory.filter(
                player=context.target,
                match_skill__match=context.match,
                quantity__gt=0,
            )
            .exclude(match_skill__code_snapshot=STEAL)
            .select_related("match_skill")
            .order_by("match_skill_id", "id")
        )
        if not preparation.stealable_inventory:
            raise SkillConditionError(
                "NO_STEALABLE_SKILL",
                "The opponent has no Skill available to steal.",
            )
        if lock:
            preparation.selected_inventory = steal_selector(
                preparation.stealable_inventory
            )
            if preparation.selected_inventory not in preparation.stealable_inventory:
                raise SkillConditionError(
                    "INVALID_STEAL_SELECTION",
                    "Skill steal selection is invalid.",
                )
    return preparation


def find_active_shield(*, context, lock=False):
    if not context.policy.shieldable or context.source.pk == context.target.pk:
        return None
    return (
        active_effects_for_player(
            player=context.target,
            now=context.now,
            lock=lock,
        )
        .select_related("skill_use__match_skill")
        .filter(skill_use__match_skill__code_snapshot=SHIELD)
        .order_by("started_at", "id")
        .first()
    )


def apply_skill(
    *,
    context,
    skill_use,
    preparation,
    prompt_selector=choice,
):
    handler = SKILL_HANDLERS.get(context.policy.handler)
    if handler is None:
        raise SkillEngineConfigurationError("Skill handler is not registered.")
    return handler(
        context=context,
        skill_use=skill_use,
        preparation=preparation,
        prompt_selector=prompt_selector,
    )


def _apply_purify(*, context, skill_use, preparation, prompt_selector):
    effect = preparation.purified_effect
    if effect is None:
        raise SkillEngineConfigurationError("Purify target was not prepared.")
    effect.cancelled_at = context.now
    effect.save(update_fields=["cancelled_at"])
    return None


def _apply_steal(*, context, skill_use, preparation, prompt_selector):
    selected = preparation.selected_inventory
    if selected is None:
        raise SkillEngineConfigurationError("Steal selection was not prepared.")
    selected.quantity -= 1
    selected.save(update_fields=["quantity", "updated_at"])
    recipient, _ = MatchPlayerSkill.objects.select_for_update().get_or_create(
        player=context.source,
        match_skill=selected.match_skill,
    )
    recipient.quantity += 1
    recipient.save(update_fields=["quantity", "updated_at"])
    return None


def _apply_time_penalty(*, context, skill_use, preparation, prompt_selector):
    context.target.time_penalty_seconds += context.rules.time_drain_seconds
    context.target.save(update_fields=["time_penalty_seconds"])
    return None


def _create_timed_effect(*, context, skill_use):
    duration = context.match_skill.duration_seconds_snapshot
    if not duration:
        raise SkillEngineConfigurationError("Timed Skill duration is invalid.")
    return SkillEffect.objects.create(
        skill_use=skill_use,
        started_at=context.now,
        expires_at=context.now + timedelta(seconds=duration),
    )


def _apply_timed_effect(*, context, skill_use, preparation, prompt_selector):
    return _create_timed_effect(context=context, skill_use=skill_use)


def _apply_typing_challenge(*, context, skill_use, preparation, prompt_selector):
    effect = _create_timed_effect(context=context, skill_use=skill_use)
    TypingChallenge.objects.create(
        effect=effect,
        prompt=prompt_selector(context.rules.typing_prompts),
        started_at=effect.started_at,
        expires_at=effect.expires_at,
    )
    return effect


SKILL_HANDLERS = {
    TIMED_HANDLER: _apply_timed_effect,
    TIME_PENALTY_HANDLER: _apply_time_penalty,
    TYPING_HANDLER: _apply_typing_challenge,
    PURIFY_HANDLER: _apply_purify,
    STEAL_HANDLER: _apply_steal,
    SHIELD_HANDLER: _apply_timed_effect,
}


def outcome_for_preparation(*, context, preparation):
    if context.policy.handler == PURIFY_HANDLER:
        skill = preparation.purified_effect.skill_use.match_skill
        return {
            "kind": "PURIFIED_EFFECT",
            "effect_id": preparation.purified_effect.pk,
            "skill_code": skill.code_snapshot,
            "skill_name": skill.name_snapshot,
        }
    if context.policy.handler == STEAL_HANDLER:
        skill = preparation.selected_inventory.match_skill
        return {
            "kind": "STOLEN_SKILL",
            "match_skill_id": skill.pk,
            "skill_code": skill.code_snapshot,
            "skill_name": skill.name_snapshot,
        }
    return {}


def _is_purifiable(match_skill):
    try:
        policy = policy_for_match_skill(match_skill)
    except ValueError as error:
        raise SkillEngineConfigurationError(str(error)) from error
    return policy.disposition == HARMFUL and policy.dispellable
