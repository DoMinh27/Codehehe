from __future__ import annotations

import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from operations.models import WorkerHeartbeat

IDLE_WRITE_INTERVAL = timedelta(seconds=60)
_SUMMARY_KEYS = {
    WorkerHeartbeat.Worker.AI_REVIEW: frozenset({"processed"}),
    WorkerHeartbeat.Worker.MATCH_SWEEPER: frozenset(
        {"recovered", "finalized"}
    ),
}


def heartbeat_error_code(error: BaseException) -> str:
    """Return a stable, message-free error code for persisted heartbeats."""

    class_name = type(error).__name__
    snake_name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    snake_name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", snake_name).upper()
    return _sanitize_error_code(snake_name)


def record_worker_success(
    worker: str,
    *,
    duration_ms: int,
    summary: dict[str, int],
    has_work: bool,
    at=None,
) -> bool:
    """Record a successful run and return whether a database write occurred."""

    return _record_heartbeat(
        worker=worker,
        status=WorkerHeartbeat.Status.OK,
        duration_ms=duration_ms,
        summary=summary,
        error_code="",
        has_work=has_work,
        at=at,
    )


def record_worker_failure(
    worker: str,
    *,
    error_code: str,
    duration_ms: int,
    summary: dict[str, int] | None = None,
    at=None,
) -> bool:
    """Record every failed run immediately."""

    return _record_heartbeat(
        worker=worker,
        status=WorkerHeartbeat.Status.FAILED,
        duration_ms=duration_ms,
        summary=summary or {},
        error_code=_sanitize_error_code(error_code),
        has_work=True,
        at=at,
    )


def record_worker_disabled(
    worker: str,
    *,
    duration_ms: int = 0,
    summary: dict[str, int] | None = None,
    at=None,
) -> bool:
    """Record a disabled worker, throttling repeated identical heartbeats."""

    return _record_heartbeat(
        worker=worker,
        status=WorkerHeartbeat.Status.DISABLED,
        duration_ms=duration_ms,
        summary=summary or {},
        error_code="",
        has_work=False,
        at=at,
    )


def _record_heartbeat(
    *,
    worker: str,
    status: str,
    duration_ms: int,
    summary: dict[str, int],
    error_code: str,
    has_work: bool,
    at,
) -> bool:
    worker = _validate_worker(worker)
    recorded_at = at or timezone.now()
    safe_summary = _sanitize_summary(worker, summary)
    safe_duration_ms = max(0, int(duration_ms))

    with transaction.atomic():
        heartbeat = (
            WorkerHeartbeat.objects.select_for_update()
            .filter(worker=worker)
            .first()
        )
        if heartbeat is None:
            heartbeat = WorkerHeartbeat.objects.create(
                worker=worker,
                status=status,
                last_heartbeat_at=recorded_at,
                last_success_at=(
                    recorded_at if status == WorkerHeartbeat.Status.OK else None
                ),
                last_failure_at=(
                    recorded_at
                    if status == WorkerHeartbeat.Status.FAILED
                    else None
                ),
                last_duration_ms=safe_duration_ms,
                error_code=error_code,
                summary=safe_summary,
            )
            return True

        same_idle_state = (
            not has_work
            and heartbeat.status == status
            and heartbeat.last_heartbeat_at
            > recorded_at - IDLE_WRITE_INTERVAL
        )
        if same_idle_state:
            return False

        heartbeat.status = status
        heartbeat.last_heartbeat_at = recorded_at
        heartbeat.last_duration_ms = safe_duration_ms
        heartbeat.error_code = error_code
        heartbeat.summary = safe_summary
        if status == WorkerHeartbeat.Status.OK:
            heartbeat.last_success_at = recorded_at
        elif status == WorkerHeartbeat.Status.FAILED:
            heartbeat.last_failure_at = recorded_at
        heartbeat.save(
            update_fields=[
                "status",
                "last_heartbeat_at",
                "last_success_at",
                "last_failure_at",
                "last_duration_ms",
                "error_code",
                "summary",
                "updated_at",
            ]
        )
        return True


def _validate_worker(worker: str) -> str:
    valid_workers = {choice.value for choice in WorkerHeartbeat.Worker}
    if worker not in valid_workers:
        raise ValueError("Unknown worker heartbeat identifier.")
    return worker


def _sanitize_summary(worker: str, summary: dict[str, int]) -> dict[str, int]:
    allowed_keys = _SUMMARY_KEYS[worker]
    safe_summary = {}
    for key, value in summary.items():
        if key not in allowed_keys:
            raise ValueError("Worker heartbeat summary contains an unsafe key.")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Worker heartbeat summary counts must be non-negative integers.")
        safe_summary[key] = value
    return safe_summary


def _sanitize_error_code(value: str) -> str:
    safe_value = re.sub(r"[^A-Z0-9_]+", "_", str(value).upper()).strip("_")
    return (safe_value or "UNKNOWN_ERROR")[:64]
