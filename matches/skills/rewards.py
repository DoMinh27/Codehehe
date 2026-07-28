"""Idempotent Energy and inventory rewards for first problem solves."""

from dataclasses import dataclass
from secrets import choice
from typing import Callable, Sequence

from matches.models import (
    MatchPlayer,
    MatchPlayerSkill,
    MatchSkill,
    PlayerProblemProgress,
)


class RewardConfigurationError(Exception):
    """Raised when a playing match has no frozen Skill catalog."""


SkillSelector = Callable[[Sequence[MatchSkill]], MatchSkill]


@dataclass
class RewardService:
    selector: SkillSelector = choice

    def award_first_solve(
        self,
        *,
        progress: PlayerProblemProgress,
        player: MatchPlayer,
    ) -> None:
        if progress.reward_processed:
            return

        match_skills = list(
            MatchSkill.objects.filter(match_id=progress.match_id).order_by("id")
        )
        if not match_skills:
            progress.reward_processed = True
            progress.save(
                update_fields=["reward_processed", "updated_at"]
            )
            return

        selected_skill = self.selector(match_skills)
        energy_awarded = int(player.energy < 3)
        if energy_awarded:
            player.energy += 1
            player.save(update_fields=["energy"])

        inventory, _ = MatchPlayerSkill.objects.select_for_update().get_or_create(
            player=player,
            match_skill=selected_skill,
        )
        inventory.quantity += 1
        inventory.save(update_fields=["quantity", "updated_at"])

        progress.reward_processed = True
        progress.energy_awarded = energy_awarded
        progress.skill_awarded = selected_skill
        progress.save(
            update_fields=[
                "reward_processed",
                "energy_awarded",
                "skill_awarded",
                "updated_at",
            ]
        )
