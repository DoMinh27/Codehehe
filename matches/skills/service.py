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
from matches.services.db import retry_transient_db_lock

from .definitions import SKILL_REGISTRY
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
            target = next(
                (player for player in players if player.id == target_player_id),
                None,
            )
            if target is None or target.id == source.id:
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
            source_deadline = source.personal_ends_at
            if source_deadline is None or evaluation_time > source_deadline:
                raise SkillUseConflictError("Your personal time has ended.")
            if has_active_typing_challenge(
                player_id=source.id,
                now=evaluation_time,
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

            definition = SKILL_REGISTRY[skill_code]
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

            skill_use = SkillUse.objects.create(
                match=match,
                source_player=source,
                target_player=target,
                match_skill=match_skill,
                energy_spent=match_skill.energy_cost_snapshot,
                idempotency_key=idempotency_key,
            )
            source.energy -= match_skill.energy_cost_snapshot
            source.save(update_fields=["energy"])
            inventory.quantity -= 1
            inventory.used_count += 1
            inventory.save(
                update_fields=["quantity", "used_count", "updated_at"]
            )
            try:
                apply_skill_effect(
                    skill_use=skill_use,
                    target_player=target,
                    now=evaluation_time,
                    prompt_selector=self.prompt_selector,
                )
            except SkillHandlerConfigurationError as error:
                raise SkillUseConflictError(
                    "Skill is temporarily unavailable."
                ) from error

            return SkillUseResult(skill_use, created=True)
