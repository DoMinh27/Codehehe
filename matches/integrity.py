"""Versioned Fair Play policy snapshots for new matches."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.conf import settings


INTEGRITY_POLICY_VERSION = "v1"


class IntegrityPolicyError(ValueError):
    """Raised when an integrity policy snapshot is invalid."""


def _positive_integer(value: Any, *, field: str, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise IntegrityPolicyError(f"{field} must be an integer.")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise IntegrityPolicyError(f"{field} must be at least {minimum}.")
    return value


@dataclass(frozen=True)
class IntegrityPolicy:
    version: str
    heartbeat_seconds: int
    ignore_below_seconds: int
    strike_seconds: int
    flag_strikes: int
    flag_total_seconds: int
    connection_gap_seconds: int

    def __post_init__(self) -> None:
        if self.version != INTEGRITY_POLICY_VERSION:
            raise IntegrityPolicyError("Unsupported integrity policy version.")
        for field in (
            "heartbeat_seconds",
            "strike_seconds",
            "flag_strikes",
            "flag_total_seconds",
            "connection_gap_seconds",
        ):
            _positive_integer(getattr(self, field), field=field)
        _positive_integer(
            self.ignore_below_seconds,
            field="ignore_below_seconds",
            allow_zero=True,
        )
        if self.strike_seconds <= self.ignore_below_seconds:
            raise IntegrityPolicyError(
                "strike_seconds must be greater than ignore_below_seconds."
            )
        if self.connection_gap_seconds <= self.heartbeat_seconds:
            raise IntegrityPolicyError(
                "connection_gap_seconds must be greater than heartbeat_seconds."
            )

    def to_snapshot(self) -> dict[str, int | str]:
        return {
            "version": self.version,
            "heartbeat_seconds": self.heartbeat_seconds,
            "ignore_below_seconds": self.ignore_below_seconds,
            "strike_seconds": self.strike_seconds,
            "flag_strikes": self.flag_strikes,
            "flag_total_seconds": self.flag_total_seconds,
            "connection_gap_seconds": self.connection_gap_seconds,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> IntegrityPolicy:
        if not isinstance(snapshot, Mapping):
            raise IntegrityPolicyError("Integrity policy snapshot must be an object.")
        return cls(
            version=snapshot.get("version"),
            heartbeat_seconds=_positive_integer(
                snapshot.get("heartbeat_seconds"), field="heartbeat_seconds"
            ),
            ignore_below_seconds=_positive_integer(
                snapshot.get("ignore_below_seconds"),
                field="ignore_below_seconds",
                allow_zero=True,
            ),
            strike_seconds=_positive_integer(
                snapshot.get("strike_seconds"), field="strike_seconds"
            ),
            flag_strikes=_positive_integer(
                snapshot.get("flag_strikes"), field="flag_strikes"
            ),
            flag_total_seconds=_positive_integer(
                snapshot.get("flag_total_seconds"), field="flag_total_seconds"
            ),
            connection_gap_seconds=_positive_integer(
                snapshot.get("connection_gap_seconds"),
                field="connection_gap_seconds",
            ),
        )


def current_integrity_policy() -> IntegrityPolicy:
    return IntegrityPolicy(
        version=INTEGRITY_POLICY_VERSION,
        heartbeat_seconds=settings.MATCH_INTEGRITY_HEARTBEAT_SECONDS,
        ignore_below_seconds=settings.MATCH_INTEGRITY_IGNORE_BELOW_SECONDS,
        strike_seconds=settings.MATCH_INTEGRITY_STRIKE_SECONDS,
        flag_strikes=settings.MATCH_INTEGRITY_FLAG_STRIKES,
        flag_total_seconds=settings.MATCH_INTEGRITY_FLAG_TOTAL_SECONDS,
        connection_gap_seconds=settings.MATCH_INTEGRITY_CONNECTION_GAP_SECONDS,
    )
