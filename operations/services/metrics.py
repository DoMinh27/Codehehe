import math
from collections import Counter
from datetime import datetime, time as datetime_time, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from accounts.models import PlayerActivityDay
from matches.models import (
    Match,
    MatchIntegrityState,
    MatchPlayer,
    Submission,
    SubmissionAIReview,
)


LATENCY_SAMPLE_LIMIT = 2000


def _iso(value):
    return value.isoformat() if value is not None else None


def _admin_changelist(model_name, **filters):
    url = reverse(f"admin:matches_{model_name}_changelist")
    if filters:
        return f"{url}?{urlencode(filters)}"
    return url


def _live_matches(*, now):
    player_queryset = (
        MatchPlayer.objects.select_related("user", "integrity_state")
        .only(
            "id",
            "match_id",
            "slot",
            "score",
            "user__username",
            "integrity_state__is_flagged",
        )
        .order_by("slot", "id")
    )
    matches = list(
        Match.objects.filter(status=Match.Status.PLAYING)
        .only("id", "room_code", "status", "started_at", "duration_seconds")
        .annotate(
            pending_submission_count=Count(
                "submissions",
                filter=Q(submissions__verdict=Submission.Verdict.PENDING),
                distinct=True,
            )
        )
        .prefetch_related(Prefetch("players", queryset=player_queryset))
        .order_by("-started_at", "-id")[:10]
    )
    rows = []
    for match in matches:
        ends_at = match.ends_at
        raw_remaining_seconds = (
            int((ends_at - now).total_seconds()) if ends_at else None
        )
        is_overdue = raw_remaining_seconds is not None and raw_remaining_seconds < 0
        fair_play_flag_count = 0
        for player in match.players.all():
            try:
                integrity_state = player.integrity_state
            except MatchIntegrityState.DoesNotExist:
                continue
            if integrity_state.is_flagged:
                fair_play_flag_count += 1
        rows.append(
            {
                "id": match.id,
                "room_code": match.room_code,
                "players": [
                    {"username": player.user.username, "score": player.score}
                    for player in match.players.all()
                ],
                "remaining_seconds": (
                    max(0, raw_remaining_seconds)
                    if raw_remaining_seconds is not None
                    else None
                ),
                "timing_status": "OVERDUE" if is_overdue else "RUNNING",
                "overdue_seconds": (
                    abs(raw_remaining_seconds) if is_overdue else 0
                ),
                "pending_submissions": match.pending_submission_count,
                "fair_play_flag_count": fair_play_flag_count,
                "status": "Đang chơi",
                "url": reverse("admin:matches_match_change", args=[match.id]),
                "url_permission": "matches.view_match",
            }
        )
    return rows


def _submission_metrics(*, now, stale_cutoff):
    window_start = now - timedelta(hours=24)
    counts = Counter(
        {
            row["verdict"]: row["count"]
            for row in (
                Submission.objects.filter(received_at__gte=window_start)
                .values("verdict")
                .annotate(count=Count("id"))
            )
        }
    )
    total = sum(counts.values())
    accepted = counts[Submission.Verdict.ACCEPTED]
    verdicts = []
    for code, label in Submission.Verdict.choices:
        count = counts[code]
        verdicts.append(
            {
                "code": code,
                "label": label,
                "count": count,
                "percentage": round((count / total) * 100, 1) if total else 0.0,
            }
        )

    pairs = list(
        Submission.objects.filter(
            received_at__gte=window_start,
            completed_at__isnull=False,
        )
        .order_by("-completed_at")
        .values_list("received_at", "completed_at")[:LATENCY_SAMPLE_LIMIT]
    )
    latencies = sorted(
        max(0, round((completed - received).total_seconds() * 1000))
        for received, completed in pairs
    )
    average_latency = round(sum(latencies) / len(latencies)) if latencies else None
    p95_latency = (
        latencies[max(0, math.ceil(len(latencies) * 0.95) - 1)]
        if latencies
        else None
    )

    internal_errors = []
    recent_errors = (
        Submission.objects.filter(
            verdict=Submission.Verdict.INTERNAL_ERROR,
            received_at__gte=window_start,
        )
        .select_related("match", "player__user", "match_problem")
        .only(
            "id",
            "received_at",
            "match__room_code",
            "player__user__username",
            "match_problem__title_snapshot",
        )
        .order_by("-received_at", "-id")[:10]
    )
    for submission in recent_errors:
        internal_errors.append(
            {
                "id": submission.id,
                "match_code": submission.match.room_code,
                "player": submission.player.user.username,
                "problem": submission.match_problem.title_snapshot,
                "received_at": _iso(submission.received_at),
                "url": reverse(
                    "admin:matches_submission_change", args=[submission.id]
                ),
                "url_permission": "matches.view_submission",
            }
        )

    pending = Submission.objects.filter(verdict=Submission.Verdict.PENDING).count()
    stale = Submission.objects.filter(
        verdict=Submission.Verdict.PENDING,
        received_at__lte=stale_cutoff,
    ).count()
    return {
        "total": total,
        "ac_rate": round((accepted / total) * 100, 1) if total else 0.0,
        "pending": pending,
        "stale": stale,
        "average_latency_ms": average_latency,
        "p95_latency_ms": p95_latency,
        "verdicts": verdicts,
        "internal_errors": internal_errors,
    }


def _ai_review_metrics(*, now):
    window_start = now - timedelta(hours=24)
    status_counts = {
        code: 0 for code, _label in SubmissionAIReview.Status.choices
    }
    status_counts.update(
        {
            row["status"]: row["count"]
            for row in SubmissionAIReview.objects.values("status").annotate(
                count=Count("id")
            )
        }
    )

    terminal = SubmissionAIReview.objects.filter(
        status__in=(
            SubmissionAIReview.Status.COMPLETED,
            SubmissionAIReview.Status.FAILED,
        ),
        updated_at__gte=window_start,
    )
    terminal_counts = terminal.aggregate(
        total=Count("id"),
        completed=Count(
            "id", filter=Q(status=SubmissionAIReview.Status.COMPLETED)
        ),
    )
    terminal_total = terminal_counts["total"] or 0
    terminal_completed = terminal_counts["completed"] or 0

    eligible = SubmissionAIReview.objects.filter(
        status=SubmissionAIReview.Status.PENDING,
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
    oldest_eligible_at = (
        eligible.annotate(
            effective_eligible_at=Coalesce("next_attempt_at", "created_at")
        )
        .order_by("effective_eligible_at", "id")
        .values_list("effective_eligible_at", flat=True)
        .first()
    )

    latest_completed = (
        SubmissionAIReview.objects.filter(
            status=SubmissionAIReview.Status.COMPLETED
        )
        .only("model", "completed_at")
        .order_by("-completed_at", "-id")
        .first()
    )
    token_totals = SubmissionAIReview.objects.filter(
        completed_at__gte=window_start
    ).aggregate(
        input=Sum("input_tokens"),
        output=Sum("output_tokens"),
        reasoning=Sum("reasoning_tokens"),
    )
    errors = [
        {"code": row["error_code"], "count": row["count"]}
        for row in (
            SubmissionAIReview.objects.filter(
                status=SubmissionAIReview.Status.FAILED,
                updated_at__gte=window_start,
            )
            .exclude(error_code="")
            .values("error_code")
            .annotate(count=Count("id"))
            .order_by("-count", "error_code")[:8]
        )
    ]
    return {
        "counts": status_counts,
        "oldest_eligible_at": _iso(oldest_eligible_at),
        "success_rate": (
            round((terminal_completed / terminal_total) * 100, 1)
            if terminal_total
            else 0.0
        ),
        "provider": settings.AI_REVIEW_PROVIDER,
        "configured_model": settings.AI_REVIEW_MODEL,
        "actual_model": latest_completed.model if latest_completed else None,
        "tokens": {
            "input": token_totals["input"] or 0,
            "output": token_totals["output"] or 0,
            "reasoning": token_totals["reasoning"] or 0,
        },
        "errors": errors,
        "last_completed_at": _iso(
            latest_completed.completed_at if latest_completed else None
        ),
    }


def _today_bounds(now):
    current_timezone = timezone.get_current_timezone()
    today = timezone.localdate(now)
    start = timezone.make_aware(
        datetime.combine(today, datetime_time.min),
        current_timezone,
    )
    return today, start, start + timedelta(days=1)


def _fair_play_metrics(*, window_start):
    states = list(
        MatchIntegrityState.objects.filter(
            is_flagged=True,
            flagged_at__gte=window_start,
        )
        .select_related("player__match", "player__user")
        .only(
            "id",
            "flag_reason",
            "strike_count",
            "away_duration_ms",
            "paste_count",
            "flagged_at",
            "player__id",
            "player__match__id",
            "player__match__room_code",
            "player__user__username",
        )
        .order_by("-flagged_at", "-id")[:20]
    )
    rows = []
    for state in states:
        rows.append(
            {
                "id": state.id,
                "room_code": state.player.match.room_code,
                "username": state.player.user.username,
                "reason": state.get_flag_reason_display() or "Cần xem xét",
                "strike_count": state.strike_count,
                "away_duration_seconds": round(state.away_duration_ms / 1000, 1),
                "paste_count": state.paste_count,
                "flagged_at": _iso(state.flagged_at),
                "url": reverse(
                    "admin:matches_matchintegritystate_change", args=[state.id]
                ),
                "url_permission": "matches.view_matchintegritystate",
                "timeline_url": _admin_changelist(
                    "matchintegrityevent",
                    player__id__exact=state.player_id,
                ),
                "timeline_url_permission": "matches.view_matchintegrityevent",
            }
        )
    return {"flagged_players": rows}


def _earliest(queryset, field_name):
    return queryset.order_by(field_name, "id").values_list(field_name, flat=True).first()


def collect_dashboard_metrics(*, now):
    stale_submission_cutoff = now - timedelta(
        seconds=settings.MATCH_PENDING_SUBMISSION_TIMEOUT_SECONDS
    )
    waiting_cutoff = now - timedelta(seconds=settings.OPERATIONS_WAITING_STALE_SECONDS)
    ai_processing_cutoff = now - timedelta(seconds=settings.AI_REVIEW_STALE_SECONDS)
    ai_queue_cutoff = now - timedelta(
        seconds=settings.OPERATIONS_AI_QUEUE_WARNING_SECONDS
    )
    ai_failure_cutoff = now - timedelta(
        seconds=settings.OPERATIONS_AI_FAILURE_WINDOW_SECONDS
    )
    integrity_cutoff = now - timedelta(
        seconds=settings.OPERATIONS_INTEGRITY_ALERT_WINDOW_SECONDS
    )
    flagged_integrity_states = MatchIntegrityState.objects.filter(
            is_flagged=True,
            flagged_at__gte=integrity_cutoff,
        )
    flagged_integrity_matches = (
        flagged_integrity_states
        .values("player__match_id")
        .distinct()
        .count()
    )

    stale_submissions = Submission.objects.filter(
        verdict=Submission.Verdict.PENDING,
        received_at__lte=stale_submission_cutoff,
    )
    stale_waiting_matches = Match.objects.filter(
        status=Match.Status.WAITING,
        created_at__lte=waiting_cutoff,
    )
    overdue_ends_at = [
        started_at
        + timedelta(
            seconds=duration_seconds + settings.OPERATIONS_MATCH_GRACE_SECONDS
        )
        for started_at, duration_seconds in Match.objects.filter(
            status=Match.Status.PLAYING,
            started_at__isnull=False,
        ).values_list("started_at", "duration_seconds")
        if started_at
        + timedelta(
            seconds=duration_seconds + settings.OPERATIONS_MATCH_GRACE_SECONDS
        )
        <= now
    ]
    stale_ai_processing = SubmissionAIReview.objects.filter(
        status=SubmissionAIReview.Status.PROCESSING,
        processing_started_at__lte=ai_processing_cutoff,
    )
    delayed_ai_queue = SubmissionAIReview.objects.filter(
        Q(next_attempt_at__lte=ai_queue_cutoff)
        | Q(next_attempt_at__isnull=True, created_at__lte=ai_queue_cutoff),
        status=SubmissionAIReview.Status.PENDING,
    )
    recent_ai_failures = SubmissionAIReview.objects.filter(
        status=SubmissionAIReview.Status.FAILED,
        updated_at__gte=ai_failure_cutoff,
    )

    alert_metrics = {
        "stale_submissions": stale_submissions.count(),
        "stale_submissions_oldest_at": _iso(
            _earliest(stale_submissions, "received_at")
        ),
        "stale_waiting_matches": stale_waiting_matches.count(),
        "stale_waiting_matches_oldest_at": _iso(
            _earliest(stale_waiting_matches, "created_at")
        ),
        "overdue_matches": len(overdue_ends_at),
        "overdue_matches_oldest_at": _iso(min(overdue_ends_at, default=None)),
        "stale_ai_processing": stale_ai_processing.count(),
        "stale_ai_processing_oldest_at": _iso(
            _earliest(stale_ai_processing, "processing_started_at")
        ),
        "delayed_ai_queue": delayed_ai_queue.count(),
        "delayed_ai_queue_oldest_at": _iso(
            delayed_ai_queue.annotate(
                effective_eligible_at=Coalesce("next_attempt_at", "created_at")
            )
            .order_by("effective_eligible_at", "id")
            .values_list("effective_eligible_at", flat=True)
            .first()
        ),
        "recent_ai_failures": recent_ai_failures.count(),
        "recent_ai_failures_oldest_at": _iso(
            _earliest(recent_ai_failures, "updated_at")
        ),
        "fair_play_flags": flagged_integrity_matches,
        "fair_play_flags_oldest_at": _iso(
            _earliest(flagged_integrity_states, "flagged_at")
        ),
    }

    counters = {
        "waiting_matches": Match.objects.filter(status=Match.Status.WAITING).count(),
        "playing_matches": Match.objects.filter(status=Match.Status.PLAYING).count(),
        "playing_players": MatchPlayer.objects.filter(
            match__status=Match.Status.PLAYING,
            is_active=True,
        ).count(),
        "pending_submissions": Submission.objects.filter(
            verdict=Submission.Verdict.PENDING
        ).count(),
        "active_ai_reviews": SubmissionAIReview.objects.filter(
            status__in=(
                SubmissionAIReview.Status.PENDING,
                SubmissionAIReview.Status.PROCESSING,
            )
        ).count(),
        "fair_play_flags": flagged_integrity_matches,
    }

    today, day_start, day_end = _today_bounds(now)
    user_model = get_user_model()
    kpis = {
        "new_accounts": user_model.objects.filter(
            date_joined__gte=day_start,
            date_joined__lt=day_end,
        ).count(),
        "active_players": PlayerActivityDay.objects.filter(
            activity_date=today
        ).count(),
        "finished_matches": Match.objects.filter(
            status=Match.Status.FINISHED,
            ended_at__gte=day_start,
            ended_at__lt=day_end,
        ).count(),
        "cancelled_matches": Match.objects.filter(
            status=Match.Status.CANCELLED,
            ended_at__gte=day_start,
            ended_at__lt=day_end,
        ).count(),
    }

    return {
        "alert_metrics": alert_metrics,
        "counters": counters,
        "live_matches": _live_matches(now=now),
        "submissions": _submission_metrics(
            now=now,
            stale_cutoff=stale_submission_cutoff,
        ),
        "ai_reviews": _ai_review_metrics(now=now),
        "fair_play": _fair_play_metrics(window_start=integrity_cutoff),
        "kpis": kpis,
        "links": {
            "live_matches": {
                "url": _admin_changelist("match", status__exact="PLAYING"),
                "url_permission": "matches.view_match",
            },
            "waiting_matches": {
                "url": _admin_changelist("match", status__exact="WAITING"),
                "url_permission": "matches.view_match",
            },
            "overdue_matches": {
                "url": _admin_changelist("match", status__exact="PLAYING"),
                "url_permission": "matches.view_match",
            },
            "pending_submissions": {
                "url": _admin_changelist("submission", verdict__exact="PENDING"),
                "url_permission": "matches.view_submission",
            },
            "ai_reviews": {
                "url": _admin_changelist("submissionaireview"),
                "url_permission": "matches.view_submissionaireview",
            },
            "fair_play": {
                "url": _admin_changelist("matchintegritystate", is_flagged__exact="1"),
                "url_permission": "matches.view_matchintegritystate",
            },
            "worker_heartbeats": {
                "url": reverse("admin:operations_workerheartbeat_changelist"),
                "url_permission": "operations.view_workerheartbeat",
            },
        },
    }
