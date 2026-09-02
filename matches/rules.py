"""Versioned, snapshotted gameplay rules for a Match."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from matches.skills.definitions import (
    REQUIRED_SKILL_CODES,
    SKILL_REGISTRY,
    TYPING_PROMPTS,
)


CURRENT_RULESET_VERSION = "v3.2"
SUPPORTED_RULESET_VERSIONS = {"v3.1", CURRENT_RULESET_VERSION}
DEFAULT_MATCH_DURATION_SECONDS = 300
DEFAULT_EASY_PROBLEM_COUNT = 2
DEFAULT_MEDIUM_PROBLEM_COUNT = 1
DEFAULT_HARD_PROBLEM_COUNT = 1
DEFAULT_FIRST_SOLVE_BONUS = 1
DEFAULT_MAX_ENERGY = 3
DEFAULT_ENERGY_PER_FIRST_SOLVE = 1
DEFAULT_TIME_DRAIN_SECONDS = 60


class RulesetConfigurationError(ValueError):
    """Raised when a Match rules snapshot is missing or inconsistent."""


def _require_integer(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RulesetConfigurationError(f"{field} must be an integer.")
    return value


def _require_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RulesetConfigurationError(f"{field} must be an object.")
    return value


@dataclass(frozen=True)
class MatchRules:
    """Validated rules that stay stable for the lifetime of one Match."""

    version: str
    match_duration_seconds: int
    easy_problem_count: int
    medium_problem_count: int
    hard_problem_count: int
    first_solve_bonus: int
    max_energy: int
    energy_per_first_solve: int
    required_skill_codes: tuple[str, ...]
    time_drain_seconds: int
    typing_prompts: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version not in SUPPORTED_RULESET_VERSIONS:
            raise RulesetConfigurationError(
                f"Unsupported ruleset version: {self.version!r}."
            )
        if self.match_duration_seconds <= 0:
            raise RulesetConfigurationError(
                "match_duration_seconds must be greater than zero."
            )
        problem_counts = self.problem_counts
        if any(count < 0 for count in problem_counts.values()):
            raise RulesetConfigurationError("Problem counts must not be negative.")
        if sum(problem_counts.values()) == 0:
            raise RulesetConfigurationError("At least one problem is required.")
        if self.first_solve_bonus not in {0, 1}:
            raise RulesetConfigurationError("first_solve_bonus must be zero or one.")
        if not 0 <= self.max_energy <= 3:
            raise RulesetConfigurationError(
                "max_energy must be between zero and three."
            )
        if self.energy_per_first_solve not in {0, 1}:
            raise RulesetConfigurationError(
                "energy_per_first_solve must be zero or one."
            )
        if not self.required_skill_codes:
            raise RulesetConfigurationError("At least one Skill code is required.")
        if len(set(self.required_skill_codes)) != len(self.required_skill_codes):
            raise RulesetConfigurationError("Skill codes must not be duplicated.")
        unsupported_codes = set(self.required_skill_codes) - set(SKILL_REGISTRY)
        if unsupported_codes:
            raise RulesetConfigurationError(
                "Ruleset contains an unsupported Skill code."
            )
        if self.time_drain_seconds < 0:
            raise RulesetConfigurationError("time_drain_seconds must not be negative.")
        if not self.typing_prompts or any(
            not isinstance(prompt, str) or not prompt for prompt in self.typing_prompts
        ):
            raise RulesetConfigurationError(
                "Typing Prompt catalog must contain non-empty strings."
            )

    @property
    def problem_counts(self) -> dict[str, int]:
        return {
            "EASY": self.easy_problem_count,
            "MEDIUM": self.medium_problem_count,
            "HARD": self.hard_problem_count,
        }

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "match_duration_seconds": self.match_duration_seconds,
            "problem_counts": self.problem_counts,
            "scoring": {
                "first_solve_bonus": self.first_solve_bonus,
            },
            "energy": {
                "max": self.max_energy,
                "per_first_solve": self.energy_per_first_solve,
            },
            "required_skill_codes": list(self.required_skill_codes),
            "skill_effects": {
                "TIME_DRAIN_60": {
                    "time_penalty_seconds": self.time_drain_seconds,
                },
            },
            "typing": {
                "prompts": list(self.typing_prompts),
            },
        }

    @classmethod
    def from_snapshot(
        cls,
        *,
        version: str,
        snapshot: Mapping[str, Any],
    ) -> MatchRules:
        snapshot = _require_mapping(snapshot, field="rules_snapshot")
        problem_counts = _require_mapping(
            snapshot.get("problem_counts"),
            field="problem_counts",
        )
        scoring = _require_mapping(snapshot.get("scoring"), field="scoring")
        energy = _require_mapping(snapshot.get("energy"), field="energy")
        skill_effects = _require_mapping(
            snapshot.get("skill_effects"),
            field="skill_effects",
        )
        time_drain = _require_mapping(
            skill_effects.get("TIME_DRAIN_60"),
            field="skill_effects.TIME_DRAIN_60",
        )
        typing = _require_mapping(snapshot.get("typing"), field="typing")

        skill_codes = snapshot.get("required_skill_codes")
        if not isinstance(skill_codes, list) or any(
            not isinstance(code, str) for code in skill_codes
        ):
            raise RulesetConfigurationError(
                "required_skill_codes must be a list of strings."
            )
        prompts = typing.get("prompts")
        if not isinstance(prompts, list):
            raise RulesetConfigurationError("typing.prompts must be a list.")

        return cls(
            version=version,
            match_duration_seconds=_require_integer(
                snapshot.get("match_duration_seconds"),
                field="match_duration_seconds",
            ),
            easy_problem_count=_require_integer(
                problem_counts.get("EASY"),
                field="problem_counts.EASY",
            ),
            medium_problem_count=_require_integer(
                problem_counts.get("MEDIUM"),
                field="problem_counts.MEDIUM",
            ),
            hard_problem_count=_require_integer(
                problem_counts.get("HARD"),
                field="problem_counts.HARD",
            ),
            first_solve_bonus=_require_integer(
                scoring.get("first_solve_bonus"),
                field="scoring.first_solve_bonus",
            ),
            max_energy=_require_integer(
                energy.get("max"),
                field="energy.max",
            ),
            energy_per_first_solve=_require_integer(
                energy.get("per_first_solve"),
                field="energy.per_first_solve",
            ),
            required_skill_codes=tuple(skill_codes),
            time_drain_seconds=_require_integer(
                time_drain.get("time_penalty_seconds"),
                field="skill_effects.TIME_DRAIN_60.time_penalty_seconds",
            ),
            typing_prompts=tuple(prompts),
        )


def build_v3_rules(*, match_duration_seconds: int) -> MatchRules:
    return MatchRules(
        version=CURRENT_RULESET_VERSION,
        match_duration_seconds=match_duration_seconds,
        easy_problem_count=DEFAULT_EASY_PROBLEM_COUNT,
        medium_problem_count=DEFAULT_MEDIUM_PROBLEM_COUNT,
        hard_problem_count=DEFAULT_HARD_PROBLEM_COUNT,
        first_solve_bonus=DEFAULT_FIRST_SOLVE_BONUS,
        max_energy=DEFAULT_MAX_ENERGY,
        energy_per_first_solve=DEFAULT_ENERGY_PER_FIRST_SOLVE,
        required_skill_codes=tuple(REQUIRED_SKILL_CODES),
        time_drain_seconds=DEFAULT_TIME_DRAIN_SECONDS,
        typing_prompts=tuple(TYPING_PROMPTS),
    )


def default_v3_rules_snapshot() -> dict[str, Any]:
    """Return a stable ORM default independent of environment overrides."""
    return build_v3_rules(
        match_duration_seconds=DEFAULT_MATCH_DURATION_SECONDS,
    ).to_snapshot()


def current_match_rules() -> MatchRules:
    return build_v3_rules(
        match_duration_seconds=settings.MATCH_DURATION_SECONDS,
    )


def rules_for_match(match) -> MatchRules:
    return MatchRules.from_snapshot(
        version=match.ruleset_version,
        snapshot=match.rules_snapshot,
    )
