from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse


def _iso(value):
    return value.isoformat() if value is not None else None


def _admin_changelist(app_label, model_name, **filters):
    url = reverse(f"admin:{app_label}_{model_name}_changelist")
    if filters:
        url = f"{url}?{urlencode(filters)}"
    return url


def build_alerts(*, now, health, metrics):
    alerts = []

    def add(severity, code, message, count, url=""):
        alerts.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "count": count,
                "checked_at": _iso(now),
                "url": url,
            }
        )

    if health["judge0"]["status"] == "unavailable":
        add("critical", "JUDGE0_UNAVAILABLE", health["judge0"]["detail"], 1)
    if metrics["stale_submissions"]:
        add(
            "critical",
            "STALE_SUBMISSIONS",
            "Submission pending quá thời gian phục hồi cho phép.",
            metrics["stale_submissions"],
            _admin_changelist("matches", "submission", verdict__exact="PENDING"),
        )
    if metrics["overdue_matches"]:
        add(
            "critical",
            "OVERDUE_MATCHES",
            "Trận vẫn đang chơi sau thời điểm phải kết thúc.",
            metrics["overdue_matches"],
            _admin_changelist("matches", "match", status__exact="PLAYING"),
        )
    if metrics["stale_waiting_matches"]:
        add(
            "warning",
            "STALE_WAITING_MATCHES",
            "Phòng chờ tồn tại lâu hơn ngưỡng cấu hình.",
            metrics["stale_waiting_matches"],
            _admin_changelist("matches", "match", status__exact="WAITING"),
        )
    if metrics["stale_ai_processing"]:
        add(
            "warning",
            "STALE_AI_PROCESSING",
            "AI Review ở trạng thái xử lý quá lâu.",
            metrics["stale_ai_processing"],
            _admin_changelist(
                "matches", "submissionaireview", status__exact="PROCESSING"
            ),
        )
    if metrics["delayed_ai_queue"]:
        add(
            "warning",
            "DELAYED_AI_QUEUE",
            "AI Review đã đến hạn nhưng vẫn chờ quá lâu.",
            metrics["delayed_ai_queue"],
            _admin_changelist(
                "matches", "submissionaireview", status__exact="PENDING"
            ),
        )
    if metrics["recent_ai_failures"] >= settings.OPERATIONS_AI_FAILURE_WARNING_COUNT:
        add(
            "warning",
            "AI_FAILURE_SPIKE",
            "Số AI Review thất bại gần đây vượt ngưỡng cảnh báo.",
            metrics["recent_ai_failures"],
            _admin_changelist(
                "matches", "submissionaireview", status__exact="FAILED"
            ),
        )
    for key, code, label, url in (
        (
            "ai_worker",
            "AI_WORKER_UNHEALTHY",
            "AI Worker",
            _admin_changelist(
                "operations", "workerheartbeat", worker__exact="AI_REVIEW"
            ),
        ),
        (
            "match_sweeper",
            "MATCH_SWEEPER_UNHEALTHY",
            "Match Sweeper",
            _admin_changelist(
                "operations", "workerheartbeat", worker__exact="MATCH_SWEEPER"
            ),
        ),
    ):
        if health[key]["status"] in {"unavailable", "degraded"}:
            add(
                "critical" if health[key]["status"] == "unavailable" else "warning",
                code,
                f"{label}: {health[key]['detail']}",
                1,
                url,
            )
    return alerts
