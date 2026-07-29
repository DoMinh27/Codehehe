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
            .select_related("user")
            .order_by("-is_host", "joined_at", "id")
        )
        current_player = next(
            (player for player in players if player.user_id == user.id),
            None,
        )
        if current_player is None:
            raise MatchStatePermissionError(
                "You are not a player in this match."
            )
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
                )
            )
            .order_by("id")
        )
        evaluation_time = now or timezone.now()
        active_effects = list(
            SkillEffect.objects.filter(
                skill_use__match=match,
                skill_use__target_player=current_player,
                cancelled_at__isnull=True,
                expires_at__gt=evaluation_time,
            )
            .select_related(
                "skill_use__match_skill",
                "skill_use__source_player__user",
                "typing_challenge",
            )
            .order_by("expires_at", "id")
        )
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
                    "expires_at": (
                        active_typing_challenge.expires_at.isoformat()
                    ),
                }
                if active_typing_challenge is not None
                else None
            ),
            "my_skills": [
                {
                    "code": match_skill.code_snapshot,
                    "name": match_skill.name_snapshot,
                    "description": match_skill.description_snapshot,
                    "energy_cost": match_skill.energy_cost_snapshot,
                    "duration_seconds": (
                        match_skill.duration_seconds_snapshot
                    ),
                    "quantity": match_skill.current_quantity,
                }
                for match_skill in match_skills
            ],
            "active_effects": [
                {
                    "id": effect.id,
                    "skill_use_id": effect.skill_use_id,
                    "code": effect.skill_use.match_skill.code_snapshot,
                    "source_player_id": effect.skill_use.source_player_id,
                    "source_username": (
                        effect.skill_use.source_player.user.username
                    ),
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
                    "source_username": (
                        skill_use.source_player.user.username
                    ),
                    "target_player_id": skill_use.target_player_id,
                    "target_username": (
                        skill_use.target_player.user.username
                    ),
                    "used_at": skill_use.used_at.isoformat(),
                }
                for skill_use in reversed(recent_skill_uses)
            ],
            "my_solved_problem_ids": solved_ids(current_player),
            "opponent_solved_problem_ids": (
                solved_ids(opponent) if opponent else []
            ),
            "first_solvers": {
                str(row["match_problem_id"]): (
                    row["match_problem__first_solver_id"]
                )
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
                match.ends_at
                - timedelta(seconds=player.time_penalty_seconds),
            )
        if deadline is None or match.status != Match.Status.PLAYING:
            return 0
        return max(0, math.ceil((deadline - now).total_seconds()))
