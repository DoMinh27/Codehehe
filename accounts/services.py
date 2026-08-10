from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from matches.models import Match, MatchPlayer

from .models import PlayerActivityDay


@dataclass(frozen=True)
class PlayerProfileStats:
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    current_streak: int
    active_today: bool


def record_player_activity(*, user, occurred_at: datetime) -> tuple[PlayerActivityDay, bool]:
    activity_date = timezone.localdate(occurred_at)
    return PlayerActivityDay.objects.get_or_create(
        user=user,
        activity_date=activity_date,
        defaults={"first_activity_at": occurred_at},
    )


def get_current_activity_streak(*, user, today: date | None = None) -> int:
    today = today or timezone.localdate()
    activity_dates = iter(
        PlayerActivityDay.objects.filter(user=user)
        .order_by("-activity_date")
        .values_list("activity_date", flat=True)
    )
    latest_date = next(activity_dates, None)
    if latest_date not in {today, today - timedelta(days=1)}:
        return 0

    streak = 1
    expected_date = latest_date - timedelta(days=1)
    for activity_date in activity_dates:
        if activity_date != expected_date:
            break
        streak += 1
        expected_date -= timedelta(days=1)
    return streak


def get_player_profile_stats(*, user) -> PlayerProfileStats:
    aggregates = MatchPlayer.objects.filter(
        user=user,
        match__status=Match.Status.FINISHED,
    ).aggregate(
        total_matches=Count("id"),
        wins=Count("id", filter=Q(match__winner_id=user.id)),
        draws=Count("id", filter=Q(match__is_draw=True)),
        losses=Count(
            "id",
            filter=(
                Q(match__winner__isnull=False)
                & ~Q(match__winner_id=user.id)
                & Q(match__is_draw=False)
            ),
        ),
    )
    total_matches = aggregates["total_matches"] or 0
    wins = aggregates["wins"] or 0
    draws = aggregates["draws"] or 0
    losses = aggregates["losses"] or 0
    valid_results = wins + draws + losses
    today = timezone.localdate()
    return PlayerProfileStats(
        total_matches=total_matches,
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate=round((wins / valid_results) * 100, 1) if valid_results else 0.0,
        current_streak=get_current_activity_streak(user=user, today=today),
        active_today=PlayerActivityDay.objects.filter(
            user=user,
            activity_date=today,
        ).exists(),
    )
