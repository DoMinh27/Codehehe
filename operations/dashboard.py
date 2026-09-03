import logging

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone

from matches.models import SubmissionAIReview

from .services.alerts import build_alerts as _build_alerts
from .services.health import (
    JUDGE_HEALTH_CACHE_KEY as JUDGE_HEALTH_CACHE_KEY,
    _heartbeat_health as _heartbeat_health,
    _judge_health,
    _status,
    build_health,
    check_database_health,
)
from .services.metrics import collect_dashboard_metrics


SNAPSHOT_CACHE_KEY = "operations:dashboard:snapshot:v1"
logger = logging.getLogger(__name__)


def _iso(value):
    return value.isoformat() if value is not None else None


def _empty_snapshot(*, now, judge_health, database_health):
    return {
        "generated_at": _iso(now),
        "health": {
            "web": _status(
                status="ok",
                label="Hoạt động",
                detail="Ứng dụng đang phản hồi.",
            ),
            "database": database_health,
            "judge0": judge_health,
            "ai_worker": _status(
                status="unknown",
                label="Chưa có dữ liệu",
                detail="Không thể đọc heartbeat.",
            ),
            "match_sweeper": _status(
                status="unknown",
                label="Chưa có dữ liệu",
                detail="Không thể đọc heartbeat.",
            ),
        },
        "counters": {
            "waiting_matches": 0,
            "playing_matches": 0,
            "playing_players": 0,
            "pending_submissions": 0,
            "active_ai_reviews": 0,
            "fair_play_flags": 0,
            "alerts": 1,
        },
        "alerts": [
            {
                "severity": "critical",
                "code": "DATABASE_UNAVAILABLE",
                "message": "Không thể đọc dữ liệu vận hành từ database.",
                "count": 1,
                "checked_at": _iso(now),
                "url": "",
            }
        ],
        "live_matches": [],
        "submissions": {
            "total": 0,
            "ac_rate": 0.0,
            "pending": 0,
            "stale": 0,
            "average_latency_ms": None,
            "p95_latency_ms": None,
            "verdicts": [],
            "internal_errors": [],
        },
        "ai_reviews": {
            "counts": {
                choice: 0 for choice, _label in SubmissionAIReview.Status.choices
            },
            "oldest_eligible_at": None,
            "success_rate": 0.0,
            "provider": settings.AI_REVIEW_PROVIDER,
            "configured_model": settings.AI_REVIEW_MODEL,
            "actual_model": None,
            "tokens": {"input": 0, "output": 0, "reasoning": 0},
            "errors": [],
            "last_completed_at": None,
        },
        "kpis": {
            "new_accounts": 0,
            "active_players": 0,
            "finished_matches": 0,
            "cancelled_matches": 0,
        },
    }


def build_dashboard_snapshot(*, now=None):
    now = now or timezone.now()
    judge_health = _judge_health()
    database_health = check_database_health()
    if database_health["status"] == "unavailable":
        return _empty_snapshot(
            now=now,
            judge_health=judge_health,
            database_health=database_health,
        )

    health = build_health(
        now=now,
        judge_health=judge_health,
        database_health=database_health,
    )
    metrics = collect_dashboard_metrics(now=now)
    alerts = _build_alerts(
        now=now,
        health=health,
        metrics=metrics["alert_metrics"],
    )
    counters = {**metrics["counters"], "alerts": len(alerts)}

    return {
        "generated_at": _iso(now),
        "health": health,
        "counters": counters,
        "alerts": alerts,
        "live_matches": metrics["live_matches"],
        "submissions": metrics["submissions"],
        "ai_reviews": metrics["ai_reviews"],
        "kpis": metrics["kpis"],
    }


def get_dashboard_snapshot(*, force=False):
    if not force:
        cached = cache.get(SNAPSHOT_CACHE_KEY)
        if cached is not None:
            return cached
    try:
        snapshot = build_dashboard_snapshot()
    except DatabaseError:
        logger.exception("Operations dashboard database query failed")
        now = timezone.now()
        snapshot = _empty_snapshot(
            now=now,
            judge_health=_judge_health(),
            database_health=_status(
                status="unavailable",
                label="Không khả dụng",
                detail="Không thể truy vấn database.",
            ),
        )
    cache.set(
        SNAPSHOT_CACHE_KEY,
        snapshot,
        settings.OPERATIONS_DASHBOARD_SNAPSHOT_CACHE_SECONDS,
    )
    return snapshot
