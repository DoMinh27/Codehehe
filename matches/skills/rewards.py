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
from matches.rules import rules_for_match


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
        rules = rules_for_match(progress.match)
        energy_awarded = min(
            rules.energy_per_first_solve,
            max(0, rules.max_energy - player.energy),
        )
        if energy_awarded:
            player.energy += energy_awarded
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
