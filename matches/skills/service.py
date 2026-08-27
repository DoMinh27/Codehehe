"""Transactional Skill use validation and application."""

from dataclasses import dataclass
from secrets import choice
from typing import Callable, Sequence

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from matches.models import (
    Match,
    MatchPlayer,
    MatchPlayerSkill,
    MatchSkill,
    PlayerProblemProgress,
    SkillEffect,
    SkillUse,
)
from matches.rules import rules_for_match
from matches.services.db import retry_transient_db_lock

from .definitions import SKILL_REGISTRY, STEAL
from .handlers import SkillHandlerConfigurationError, apply_skill_effect
from .typing import has_active_typing_challenge


MAX_IDEMPOTENCY_KEY_LENGTH = 64


class SkillUseError(Exception):
    """Base class for expected Skill use failures."""


class InvalidSkillUseError(SkillUseError):
    """Raised when the request payload is invalid."""


class SkillUsePermissionError(SkillUseError):
    """Raised when source or target is not valid for the match."""


class SkillUseNotFoundError(SkillUseError):
    """Raised when the match or frozen Skill is missing."""


class SkillUseConflictError(SkillUseError):
    """Raised when the Skill cannot currently be used."""


@dataclass(frozen=True)
class SkillUseResult:
    skill_use: SkillUse
    created: bool


@dataclass
class SkillService:
    prompt_selector: Callable[[Sequence[str]], str] = choice
    steal_selector: Callable[
        [Sequence[MatchPlayerSkill]], MatchPlayerSkill
    ] = choice

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
        if (
            not idempotency_key
            or len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH
        ):
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
                raise SkillUsePermissionError(
                    "You are not a player in this match."
                )
            definition = SKILL_REGISTRY[skill_code]
            target = next(
                (player for player in players if player.id == target_player_id),
                None,
            )
            if target is None:
                raise SkillUsePermissionError(
                    "Target must be a player in this match."
                )
            if definition.target_mode == "SELF" and target.id != source.id:
                raise SkillUsePermissionError("Target must be yourself.")
            if definition.target_mode == "OPPONENT" and target.id == source.id:
                raise SkillUsePermissionError(
                    "Target must be your opponent in this match."
                )

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
                    existing.match_id != match.id
                    or existing.target_player_id != target.id
                    or existing.match_skill.code_snapshot != skill_code
                ):
                    raise SkillUseConflictError(
                        "Idempotency key was used with a different request."
                    )
                return SkillUseResult(existing, created=False)

            if match.status != Match.Status.PLAYING or match.ends_at is None:
                raise SkillUseConflictError("Match is not playing.")
            rules = rules_for_match(match)
            source_deadline = source.personal_ends_at
            if source_deadline is None or evaluation_time > source_deadline:
                raise SkillUseConflictError("Your personal time has ended.")
            if (
                not definition.can_use_while_action_locked
                and has_active_typing_challenge(
                player_id=source.id,
                now=evaluation_time,
                )
            ):
                raise SkillUseConflictError(
                    "Complete the Typing challenge before using a Skill."
                )

            try:
                match_skill = MatchSkill.objects.get(
                    match=match,
                    code_snapshot=skill_code,
                )
            except MatchSkill.DoesNotExist as error:
                raise SkillUseNotFoundError(
                    "Skill is not available in this match."
                ) from error

            try:
                inventory = MatchPlayerSkill.objects.select_for_update().get(
                    player=source,
                    match_skill=match_skill,
                )
            except MatchPlayerSkill.DoesNotExist as error:
                raise SkillUseConflictError(
                    "You do not have this Skill."
                ) from error

            if inventory.quantity < 1:
                raise SkillUseConflictError("You do not have this Skill.")
            if source.energy < match_skill.energy_cost_snapshot:
                raise SkillUseConflictError("Not enough Energy.")

            if definition.effect_kind in {
                "TIMED",
                "TYPING_CHALLENGE",
            } and SkillEffect.objects.filter(
                skill_use__match=match,
                skill_use__target_player=target,
                skill_use__match_skill__code_snapshot=skill_code,
                cancelled_at__isnull=True,
                expires_at__gt=evaluation_time,
            ).exists():
                raise SkillUseConflictError("This effect is already active.")
            if definition.effect_kind == "TYPING_CHALLENGE":
                target_deadline = target.personal_ends_at
                if target_deadline is None or evaluation_time >= target_deadline:
                    raise SkillUseConflictError(
                        "The opponent has already finished."
                    )
                progress_summary = PlayerProblemProgress.objects.filter(
                    match=match,
                    player=target,
                ).aggregate(
                    total=Count("id"),
                    solved=Count("id", filter=Q(is_solved=True)),
                )
                if (
                    progress_summary["total"] > 0
                    and progress_summary["solved"] == progress_summary["total"]
                ):
                    raise SkillUseConflictError(
                        "The opponent has already finished."
                    )

            purified_effect = None
            stolen_inventory = None
            outcome_snapshot = {}
            if definition.effect_kind == "PURIFY":
                purified_effect = (
                    SkillEffect.objects.select_for_update()
                    .filter(
                        skill_use__match=match,
                        skill_use__target_player=source,
                        cancelled_at__isnull=True,
                        expires_at__gt=evaluation_time,
                    )
                    .select_related("skill_use__match_skill")
                    .order_by("-started_at", "-id")
                    .first()
                )
                if purified_effect is None:
                    raise SkillUseConflictError(
                        "You have no active effect to purify."
                    )
                cancelled_skill = purified_effect.skill_use.match_skill
                outcome_snapshot = {
                    "kind": "PURIFIED_EFFECT",
                    "effect_id": purified_effect.id,
                    "skill_code": cancelled_skill.code_snapshot,
                    "skill_name": cancelled_skill.name_snapshot,
                }
            elif definition.effect_kind == "STEAL":
                stealable_inventory = list(
                    MatchPlayerSkill.objects.select_for_update()
                    .filter(
                        player=target,
                        match_skill__match=match,
                        quantity__gt=0,
                    )
                    .exclude(match_skill__code_snapshot=STEAL)
                    .select_related("match_skill")
                    .order_by("match_skill_id", "id")
                )
                if not stealable_inventory:
                    raise SkillUseConflictError(
                        "The opponent has no Skill available to steal."
                    )
                stolen_inventory = self.steal_selector(stealable_inventory)
                if stolen_inventory not in stealable_inventory:
                    raise SkillUseConflictError("Skill steal selection is invalid.")
                stolen_skill = stolen_inventory.match_skill
                outcome_snapshot = {
                    "kind": "STOLEN_SKILL",
                    "match_skill_id": stolen_skill.id,
                    "skill_code": stolen_skill.code_snapshot,
                    "skill_name": stolen_skill.name_snapshot,
                }

            skill_use = SkillUse.objects.create(
                match=match,
                source_player=source,
                target_player=target,
                match_skill=match_skill,
                energy_spent=match_skill.energy_cost_snapshot,
                idempotency_key=idempotency_key,
                outcome_snapshot=outcome_snapshot,
            )
            source.energy -= match_skill.energy_cost_snapshot
            source.save(update_fields=["energy"])
            inventory.quantity -= 1
            inventory.used_count += 1
            inventory.save(
                update_fields=["quantity", "used_count", "updated_at"]
            )
            if definition.effect_kind == "PURIFY":
                purified_effect.cancelled_at = evaluation_time
                purified_effect.save(update_fields=["cancelled_at"])
            elif definition.effect_kind == "STEAL":
                stolen_inventory.quantity -= 1
                stolen_inventory.save(update_fields=["quantity", "updated_at"])
                recipient_inventory = (
                    MatchPlayerSkill.objects.select_for_update()
                    .filter(player=source, match_skill=stolen_inventory.match_skill)
                    .first()
                )
                if recipient_inventory is None:
                    MatchPlayerSkill.objects.create(
                        player=source,
                        match_skill=stolen_inventory.match_skill,
                        quantity=1,
                    )
                else:
                    recipient_inventory.quantity += 1
                    recipient_inventory.save(
                        update_fields=["quantity", "updated_at"]
                    )
            else:
                try:
                    apply_skill_effect(
                        skill_use=skill_use,
                        target_player=target,
                        rules=rules,
                        now=evaluation_time,
                        prompt_selector=self.prompt_selector,
                    )
                except SkillHandlerConfigurationError as error:
                    raise SkillUseConflictError(
                        "Skill is temporarily unavailable."
                    ) from error

            return SkillUseResult(skill_use, created=True)
