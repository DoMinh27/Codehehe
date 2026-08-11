import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection

from problems.services.judge import (
    Judge0ConfigurationError,
    Judge0Service,
    Judge0UnavailableError,
)

from operations.models import WorkerHeartbeat


JUDGE_HEALTH_CACHE_KEY = "operations:dashboard:judge-health:v1"
logger = logging.getLogger(__name__)


def _status(*, status, label, detail, latency_ms=None):
    payload = {"status": status, "label": label, "detail": detail}
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    return payload


def _judge_health():
    cached = cache.get(JUDGE_HEALTH_CACHE_KEY)
    if cached is not None:
        return cached

    started = time.perf_counter()
    try:
        judge = Judge0Service.from_environment()
        judge.timeout_seconds = 2
        judge.healthcheck()
    except Judge0ConfigurationError:
        result = _status(
            status="unavailable",
            label="Chưa cấu hình",
            detail="Judge0 chưa được cấu hình.",
        )
    except Judge0UnavailableError:
        result = _status(
            status="unavailable",
            label="Không khả dụng",
            detail="Không thể kết nối Judge0.",
        )
    except Exception as error:  # Defensive boundary around an external dependency.
        logger.warning(
            "Unexpected Judge0 healthcheck failure (%s)",
            type(error).__name__,
        )
        result = _status(
            status="unavailable",
            label="Không khả dụng",
            detail="Không thể kiểm tra Judge0.",
        )
    else:
        latency_ms = round((time.perf_counter() - started) * 1000)
        is_slow = latency_ms >= settings.OPERATIONS_JUDGE_SLOW_MS
        result = _status(
            status="degraded" if is_slow else "ok",
            label="Phản hồi chậm" if is_slow else "Hoạt động",
            detail=f"Judge0 phản hồi trong {latency_ms} ms.",
            latency_ms=latency_ms,
        )

    cache.set(
        JUDGE_HEALTH_CACHE_KEY,
        result,
        settings.OPERATIONS_JUDGE_HEALTH_CACHE_SECONDS,
    )
    return result


def _heartbeat_health(*, heartbeat, now, stale_seconds, disabled=False):
    if disabled:
        return _status(
            status="disabled",
            label="Đã tắt",
            detail="Tính năng đã được tắt theo cấu hình.",
        )
    if heartbeat is None or heartbeat.last_heartbeat_at is None:
        return _status(
            status="unknown",
            label="Chưa có dữ liệu",
            detail="Chưa nhận được heartbeat từ worker.",
        )
    if heartbeat.status == WorkerHeartbeat.Status.DISABLED:
        return _status(
            status="disabled",
            label="Đã tắt",
            detail="Worker đã báo trạng thái tắt.",
        )
    failure_is_latest = heartbeat.last_failure_at is not None and (
        heartbeat.last_success_at is None
        or heartbeat.last_failure_at > heartbeat.last_success_at
    )
    legacy_failed = (
        heartbeat.status == WorkerHeartbeat.Status.FAILED
        and heartbeat.last_failure_at is None
    )
    if failure_is_latest or legacy_failed:
        code = heartbeat.error_code or "WORKER_FAILED"
        return _status(
            status="unavailable",
            label="Lỗi",
            detail=f"Lần chạy gần nhất thất bại ({code}).",
        )

    age_seconds = max(0, int((now - heartbeat.last_heartbeat_at).total_seconds()))
    if age_seconds > stale_seconds:
        return _status(
            status="degraded",
            label="Heartbeat trễ",
            detail=f"Không nhận heartbeat trong {age_seconds} giây.",
        )
    return _status(
        status="ok",
        label="Hoạt động",
        detail=f"Heartbeat cách đây {age_seconds} giây.",
    )


def check_database_health():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return _status(
            status="unavailable",
            label="Không khả dụng",
            detail="Không thể truy vấn database.",
        )
    return _status(
        status="ok",
        label="Hoạt động",
        detail="Kết nối database bình thường.",
    )


def build_health(*, now, judge_health, database_health):
    heartbeats = {
        row.worker: row
        for row in WorkerHeartbeat.objects.filter(
            worker__in=(
                WorkerHeartbeat.Worker.AI_REVIEW,
                WorkerHeartbeat.Worker.MATCH_SWEEPER,
            )
        )
    }
    return {
        "web": _status(
            status="ok",
            label="Hoạt động",
            detail="Ứng dụng đang phản hồi.",
        ),
        "database": database_health,
        "judge0": judge_health,
        "ai_worker": _heartbeat_health(
            heartbeat=heartbeats.get(WorkerHeartbeat.Worker.AI_REVIEW),
            now=now,
            stale_seconds=settings.OPERATIONS_AI_WORKER_STALE_SECONDS,
            disabled=not settings.AI_REVIEW_ENABLED,
        ),
        "match_sweeper": _heartbeat_health(
            heartbeat=heartbeats.get(WorkerHeartbeat.Worker.MATCH_SWEEPER),
            now=now,
            stale_seconds=settings.OPERATIONS_SWEEPER_STALE_SECONDS,
        ),
    }
