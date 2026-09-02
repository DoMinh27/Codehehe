"""Read-only Match State query and JSON projection."""

import math
from datetime import timedelta

from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from matches.models import (
    Match,
    MatchPlayer,
    MatchSkill,
    PlayerProblemProgress,
    SkillEffect,
    SkillUse,
)
from matches.rules import rules_for_match
from matches.skills.definitions import (
    OPPONENT,
    SKILL_REGISTRY,
    STEAL,
    policy_for_match_skill,
)
from matches.skills.effects import active_effect_condition
from matches.skills.engine import (
    SkillAvailabilityFacts,
    SkillConditionError,
    SkillContext,
    SkillEngineConfigurationError,
    SkillTargetError,
    validate_and_prepare,
)


UNAVAILABLE_REASONS = {
    "MATCH_NOT_PLAYING": "Trận đấu không ở trạng thái đang chơi.",
    "PLAYER_TIMED_OUT": "Bạn đã hết thời gian.",
    "ACTION_LOCKED": "Hành động đang bị khóa bởi Thử thách gõ chữ.",
    "NO_QUANTITY": "Đã hết lượt sử dụng.",
    "INSUFFICIENT_ENERGY": "Không đủ năng lượng.",
    "EFFECT_ALREADY_ACTIVE": "Hiệu ứng này đang hoạt động.",
    "TARGET_FINISHED": "Đối thủ đã hoàn thành hoặc hết thời gian.",
    "NO_DISPELLABLE_EFFECT": "Không có hiệu ứng nào để thanh tẩy.",
    "NO_STEALABLE_SKILL": "Đối thủ không còn skill có thể đánh cắp.",
    "INVALID_STEAL_SELECTION": "Không thể chọn skill để đánh cắp.",
    "INVALID_TARGET": "Mục tiêu skill không hợp lệ.",
    "NO_OPPONENT": "Chưa có đối thủ để sử dụng skill.",
    "INVALID_POLICY": "Skill tạm thời không khả dụng.",
}


class MatchStateError(Exception):
    """Base class for expected Match State failures."""


class MatchStateNotFoundError(MatchStateError):
    """Raised when the requested Match does not exist."""


class MatchStatePermissionError(MatchStateError):
    """Raised when the caller is not a player in the Match."""


class MatchStateService:
    """Build the private, server-authoritative state visible to one player."""

    def get(self, *, user, match_id: int, now=None) -> dict:
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist as error:
            raise MatchStateNotFoundError("Match was not found.") from error

        players = list(
            MatchPlayer.objects.filter(match=match)
            .select_related("user", "match")
            .order_by("-is_host", "joined_at", "id")
        )
        current_player = next(
            (player for player in players if player.user_id == user.id),
            None,
        )
        if current_player is None:
            raise MatchStatePermissionError("You are not a player in this match.")
        opponent = next(
            (player for player in players if player.pk != current_player.pk),
            None,
        )

        progress_rows = list(
            PlayerProblemProgress.objects.filter(match=match).values(
                "player_id",
                "match_problem_id",
                "is_solved",
                "match_problem__first_solver_id",
            )
        )
        match_skills = list(
            MatchSkill.objects.filter(match=match)
            .annotate(
                current_quantity=Coalesce(
                    Max(
                        "player_inventory__quantity",
                        filter=Q(
                            player_inventory__player=current_player,
                        ),
                    ),
                    0,
                ),
                opponent_quantity=Coalesce(
                    Max(
                        "player_inventory__quantity",
                        filter=Q(player_inventory__player=opponent),
                    ),
                    0,
                ),
            )
            .order_by("id")
        )
        evaluation_time = now or timezone.now()
        all_active_effects = list(
            SkillEffect.objects.filter(
                active_effect_condition(evaluation_time),
                skill_use__match=match,
            )
            .select_related(
                "skill_use__match_skill",
                "skill_use__source_player__user",
                "typing_challenge",
            )
            .order_by("expires_at", "id")
        )
        active_effects = [
            effect
            for effect in all_active_effects
            if effect.skill_use.target_player_id == current_player.pk
        ]
        active_typing_challenge = next(
            (
                effect.typing_challenge
                for effect in active_effects
                if hasattr(effect, "typing_challenge")
            ),
            None,
        )
        recent_skill_uses = list(
            SkillUse.objects.filter(match=match)
            .select_related(
                "match_skill",
                "source_player__user",
                "target_player__user",
            )
            .order_by("-used_at", "-id")[:10]
        )

        remaining_seconds = {
            player.pk: self._remaining_seconds(
                match=match,
                player=player,
                now=evaluation_time,
            )
            for player in players
        }

        def solved_ids(player):
            return [
                row["match_problem_id"]
                for row in progress_rows
                if row["player_id"] == player.id and row["is_solved"]
            ]

        my_remaining = remaining_seconds[current_player.pk]
        opponent_remaining = (
            remaining_seconds[opponent.pk] if opponent is not None else 0
        )
        rules = rules_for_match(match)
        active_skill_ids_by_target = {
            player.pk: frozenset(
                effect.skill_use.match_skill_id
                for effect in all_active_effects
                if effect.skill_use.target_player_id == player.pk
            )
            for player in players
        }
        has_dispellable_effect = any(
            self._is_dispellable(effect.skill_use.match_skill)
            for effect in active_effects
        )
        stealable_skill_available = any(
            match_skill.code_snapshot != STEAL
            and match_skill.opponent_quantity > 0
            for match_skill in match_skills
        )

        def target_finished(player):
            deadline = player.personal_ends_at
            rows = [
                row for row in progress_rows if row["player_id"] == player.pk
            ]
            return (
                deadline is None
                or evaluation_time >= deadline
                or (bool(rows) and all(row["is_solved"] for row in rows))
            )

        def skill_payload(match_skill):
            unavailable_code = None
            try:
                definition = policy_for_match_skill(match_skill)
                target = (
                    opponent if definition.target_mode == OPPONENT else current_player
                )
                if target is None:
                    unavailable_code = "NO_OPPONENT"
                else:
                    context = SkillContext(
                        match=match,
                        source=current_player,
                        target=target,
                        match_skill=match_skill,
                        policy=definition,
                        rules=rules,
                        now=evaluation_time,
                    )
                    validate_and_prepare(
                        context=context,
                        quantity=match_skill.current_quantity,
                        action_locked=active_typing_challenge is not None,
                        facts=SkillAvailabilityFacts(
                            active_match_skill_ids=(
                                active_skill_ids_by_target[target.pk]
                            ),
                            has_dispellable_effect=has_dispellable_effect,
                            has_stealable_skill=stealable_skill_available,
                            target_finished=target_finished(target),
                        ),
                    )
            except SkillConditionError as error:
                unavailable_code = error.code
            except SkillTargetError:
                unavailable_code = "INVALID_TARGET"
            except (SkillEngineConfigurationError, ValueError):
                unavailable_code = "INVALID_POLICY"
                definition = SKILL_REGISTRY[match_skill.code_snapshot]
            return {
                "code": match_skill.code_snapshot,
                "name": match_skill.name_snapshot,
                "description": match_skill.description_snapshot,
                "energy_cost": match_skill.energy_cost_snapshot,
                "duration_seconds": match_skill.duration_seconds_snapshot,
                "quantity": match_skill.current_quantity,
                "target_mode": definition.target_mode,
                "ui_group": definition.ui_group,
                "can_use_while_action_locked": (definition.can_use_while_action_locked),
                "unavailable_code": unavailable_code,
                "unavailable_reason": UNAVAILABLE_REASONS.get(unavailable_code),
            }

        return {
            "status": match.status,
            "server_time": evaluation_time.isoformat(),
            "remaining_seconds": my_remaining,
            "opponent_remaining_seconds": opponent_remaining,
            "my_timed_out": my_remaining == 0,
            "opponent_timed_out": opponent_remaining == 0,
            "my_score": current_player.score,
            "opponent_score": opponent.score if opponent else 0,
            "my_energy": current_player.energy,
            "my_action_locked": active_typing_challenge is not None,
            "typing_challenge": (
                {
                    "id": active_typing_challenge.id,
                    "prompt": active_typing_challenge.prompt,
                    "expires_at": (active_typing_challenge.expires_at.isoformat()),
                }
                if active_typing_challenge is not None
                else None
            ),
            "my_skills": [skill_payload(match_skill) for match_skill in match_skills],
            "active_effects": [
                {
                    "id": effect.id,
                    "skill_use_id": effect.skill_use_id,
                    "code": effect.skill_use.match_skill.code_snapshot,
                    "source_player_id": effect.skill_use.source_player_id,
                    "source_username": (effect.skill_use.source_player.user.username),
                    "started_at": effect.started_at.isoformat(),
                    "expires_at": effect.expires_at.isoformat(),
                }
                for effect in active_effects
            ],
            "recent_skill_uses": [
                {
                    "id": skill_use.id,
                    "code": skill_use.match_skill.code_snapshot,
                    "name": skill_use.match_skill.name_snapshot,
                    "source_player_id": skill_use.source_player_id,
                    "source_username": (skill_use.source_player.user.username),
                    "target_player_id": skill_use.target_player_id,
                    "target_username": (skill_use.target_player.user.username),
                    "used_at": skill_use.used_at.isoformat(),
                    "outcome_kind": skill_use.outcome_snapshot.get("kind"),
                }
                for skill_use in reversed(recent_skill_uses)
            ],
            "my_solved_problem_ids": solved_ids(current_player),
            "opponent_solved_problem_ids": (solved_ids(opponent) if opponent else []),
            "first_solvers": {
                str(row["match_problem_id"]): (row["match_problem__first_solver_id"])
                for row in progress_rows
            },
            "winner_id": match.winner_id,
            "is_draw": match.is_draw,
            "finish_reason": match.finish_reason,
            "surrendered_by_id": match.surrendered_by_id,
            "result_url": reverse(
                "match-result",
                kwargs={"match_id": match.pk},
            ),
        }

    @staticmethod
    def _remaining_seconds(*, match, player, now) -> int:
        deadline = None
        if match.started_at is not None and match.ends_at is not None:
            deadline = max(
                match.started_at,
                match.ends_at - timedelta(seconds=player.time_penalty_seconds),
            )
        if deadline is None or match.status != Match.Status.PLAYING:
            return 0
        return max(0, math.ceil((deadline - now).total_seconds()))

    @staticmethod
    def _is_dispellable(match_skill) -> bool:
        try:
            policy = policy_for_match_skill(match_skill)
        except ValueError:
            return False
        return policy.disposition == "HARMFUL" and policy.dispellable
