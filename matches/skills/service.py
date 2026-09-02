"""Transactional, server-authoritative Skill pipeline."""

from dataclasses import dataclass
from secrets import choice
from typing import Callable, Sequence

from django.db import transaction
from django.utils import timezone

from matches.models import (
    Match,
    MatchPlayer,
    MatchPlayerSkill,
    MatchSkill,
    SkillUse,
)
from matches.rules import rules_for_match
from matches.services.db import retry_transient_db_lock
from matches.services.events import record_skill_used

from .definitions import SKILL_REGISTRY, policy_for_match_skill
from .engine import (
    SkillConditionError,
    SkillContext,
    SkillEngineConfigurationError,
    SkillTargetError,
    apply_skill,
    find_active_shield,
    outcome_for_preparation,
    validate_and_prepare,
)


MAX_IDEMPOTENCY_KEY_LENGTH = 64


class SkillUseError(Exception):
    """Base class for expected Skill use failures."""


class InvalidSkillUseError(SkillUseError):
    pass


class SkillUsePermissionError(SkillUseError):
    pass


class SkillUseNotFoundError(SkillUseError):
    pass


class SkillUseConflictError(SkillUseError):
    def __init__(self, message, reason_code="SKILL_USE_CONFLICT"):
        self.reason_code = reason_code
        super().__init__(message)


@dataclass(frozen=True)
class SkillUseResult:
    skill_use: SkillUse
    created: bool


@dataclass
class SkillService:
    prompt_selector: Callable[[Sequence[str]], str] = choice
    steal_selector: Callable[[Sequence[MatchPlayerSkill]], MatchPlayerSkill] = choice

    def use(
        self,
        *,
        user,
        match_id: int,
        skill_code: str,
        target_player_id: int,
        idempotency_key: str,
        now=None,
    ) -> SkillUseResult:
        skill_code, idempotency_key = self._validate_payload(
            skill_code=skill_code,
            target_player_id=target_player_id,
            idempotency_key=idempotency_key,
        )
        return retry_transient_db_lock(
            lambda: self._use_once(
                user=user,
                match_id=match_id,
                skill_code=skill_code,
                target_player_id=target_player_id,
                idempotency_key=idempotency_key,
                now=now,
            )
        )

    @staticmethod
    def _validate_payload(*, skill_code, target_player_id, idempotency_key):
        if not isinstance(skill_code, str) or skill_code not in SKILL_REGISTRY:
            raise InvalidSkillUseError("Skill code is invalid.")
        if not isinstance(target_player_id, int):
            raise InvalidSkillUseError("target_player_id must be an integer.")
        if not isinstance(idempotency_key, str):
            raise InvalidSkillUseError("idempotency_key must be a string.")
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise InvalidSkillUseError("idempotency_key is invalid.")
        return skill_code, idempotency_key

    def _use_once(
        self,
        *,
        user,
        match_id,
        skill_code,
        target_player_id,
        idempotency_key,
        now,
    ) -> SkillUseResult:
        evaluation_time = now or timezone.now()
        try:
            with transaction.atomic():
                try:
                    match = Match.objects.select_for_update().get(pk=match_id)
                except Match.DoesNotExist as error:
                    raise SkillUseNotFoundError("Match was not found.") from error

                players = list(
                    MatchPlayer.objects.select_for_update()
                    .filter(match=match)
                    .select_related("user")
                    .order_by("id")
                )
                source = next(
                    (player for player in players if player.user_id == user.id),
                    None,
                )
                if source is None:
                    raise SkillUsePermissionError("You are not a player in this match.")
                target = next(
                    (player for player in players if player.pk == target_player_id),
                    None,
                )
                if target is None:
                    raise SkillUsePermissionError(
                        "Target must be a player in this match."
                    )
                try:
                    match_skill = MatchSkill.objects.get(
                        match=match,
                        code_snapshot=skill_code,
                    )
                    policy = policy_for_match_skill(match_skill)
                except MatchSkill.DoesNotExist as error:
                    raise SkillUseNotFoundError(
                        "Skill is not available in this match."
                    ) from error
                except ValueError as error:
                    raise SkillUseConflictError(
                        "Skill is temporarily unavailable.",
                        "INVALID_POLICY",
                    ) from error
                existing = (
                    SkillUse.objects.select_related("match_skill", "effect")
                    .filter(
                        source_player=source,
                        idempotency_key=idempotency_key,
                    )
                    .first()
                )
                if existing is not None:
                    if (
                        existing.match_id != match.pk
                        or existing.target_player_id != target.pk
                        or existing.match_skill.code_snapshot != skill_code
                    ):
                        raise SkillUseConflictError(
                            "Idempotency key was used with a different request.",
                            "IDEMPOTENCY_CONFLICT",
                        )
                    return SkillUseResult(existing, created=False)

                inventory = (
                    MatchPlayerSkill.objects.select_for_update()
                    .filter(player=source, match_skill=match_skill)
                    .first()
                )
                quantity = inventory.quantity if inventory else 0
                rules = rules_for_match(match)
                context = SkillContext(
                    match=match,
                    source=source,
                    target=target,
                    match_skill=match_skill,
                    policy=policy,
                    rules=rules,
                    now=evaluation_time,
                )
                try:
                    preparation = validate_and_prepare(
                        context=context,
                        quantity=quantity,
                        lock=True,
                        steal_selector=self.steal_selector,
                    )
                except SkillTargetError as error:
                    raise SkillUsePermissionError(str(error)) from error
                shield = find_active_shield(context=context, lock=True)
                outcome = outcome_for_preparation(
                    context=context,
                    preparation=preparation,
                )
                if shield is not None:
                    shield_skill = shield.skill_use.match_skill
                    outcome = {
                        "kind": "BLOCKED_BY_SHIELD",
                        "effect_id": shield.pk,
                        "skill_use_id": shield.skill_use_id,
                        "skill_code": shield_skill.code_snapshot,
                        "skill_name": shield_skill.name_snapshot,
                    }

                skill_use = SkillUse.objects.create(
                    match=match,
                    source_player=source,
                    target_player=target,
                    match_skill=match_skill,
                    energy_spent=match_skill.energy_cost_snapshot,
                    idempotency_key=idempotency_key,
                    outcome_snapshot=outcome,
                )
                source.energy -= match_skill.energy_cost_snapshot
                source.save(update_fields=["energy"])
                inventory.quantity -= 1
                inventory.used_count += 1
                inventory.save(update_fields=["quantity", "used_count", "updated_at"])
                if shield is not None:
                    shield.consumed_at = evaluation_time
                    shield.save(update_fields=["consumed_at"])
                else:
                    apply_skill(
                        context=context,
                        skill_use=skill_use,
                        preparation=preparation,
                        prompt_selector=self.prompt_selector,
                    )

                record_skill_used(
                    match=match,
                    skill_use=skill_use,
                    source=source,
                    target=target,
                    rules=rules,
                    now=evaluation_time,
                )
                return SkillUseResult(skill_use, created=True)
        except SkillConditionError as error:
            raise SkillUseConflictError(str(error), error.code) from error
        except SkillEngineConfigurationError as error:
            raise SkillUseConflictError(
                "Skill is temporarily unavailable.",
                "INVALID_POLICY",
            ) from error
