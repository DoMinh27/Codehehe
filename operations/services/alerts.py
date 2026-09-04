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

    def add(
        severity,
        code,
        message,
        count,
        *,
        category,
        action_label="Kiểm tra",
        oldest_at=None,
        url="",
        url_permission="",
    ):
        alerts.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "count": count,
                "checked_at": _iso(now),
                "category": category,
                "action_label": action_label,
                "oldest_at": oldest_at,
                "url": url,
                "url_permission": url_permission,
            }
        )

    if health["judge0"]["status"] == "unavailable":
        add(
            "critical",
            "JUDGE0_UNAVAILABLE",
            health["judge0"]["detail"],
            1,
            category="system",
            action_label="Kiểm tra Judge0",
            oldest_at=_iso(now),
        )
    if metrics["stale_submissions"]:
        add(
            "critical",
            "STALE_SUBMISSIONS",
            "Submission pending quá thời gian phục hồi cho phép.",
            metrics["stale_submissions"],
            category="queue",
            action_label="Xem hàng đợi",
            oldest_at=metrics["stale_submissions_oldest_at"],
            url=_admin_changelist("matches", "submission", verdict__exact="PENDING"),
            url_permission="matches.view_submission",
        )
    if metrics["overdue_matches"]:
        add(
            "critical",
            "OVERDUE_MATCHES",
            "Trận vẫn đang chơi sau thời điểm phải kết thúc.",
            metrics["overdue_matches"],
            category="matches",
            action_label="Xem trận",
            oldest_at=metrics["overdue_matches_oldest_at"],
            url=_admin_changelist("matches", "match", status__exact="PLAYING"),
            url_permission="matches.view_match",
        )
    if metrics["stale_waiting_matches"]:
        add(
            "warning",
            "STALE_WAITING_MATCHES",
            "Phòng chờ tồn tại lâu hơn ngưỡng cấu hình.",
            metrics["stale_waiting_matches"],
            category="matches",
            action_label="Xem phòng chờ",
            oldest_at=metrics["stale_waiting_matches_oldest_at"],
            url=_admin_changelist("matches", "match", status__exact="WAITING"),
            url_permission="matches.view_match",
        )
    if metrics["stale_ai_processing"]:
        add(
            "warning",
            "STALE_AI_PROCESSING",
            "AI Review ở trạng thái xử lý quá lâu.",
            metrics["stale_ai_processing"],
            category="queue",
            action_label="Xem hàng đợi",
            oldest_at=metrics["stale_ai_processing_oldest_at"],
            url=_admin_changelist(
                "matches", "submissionaireview", status__exact="PROCESSING"
            ),
            url_permission="matches.view_submissionaireview",
        )
    if metrics["delayed_ai_queue"]:
        add(
            "warning",
            "DELAYED_AI_QUEUE",
            "AI Review đã đến hạn nhưng vẫn chờ quá lâu.",
            metrics["delayed_ai_queue"],
            category="queue",
            action_label="Xem hàng đợi",
            oldest_at=metrics["delayed_ai_queue_oldest_at"],
            url=_admin_changelist(
                "matches", "submissionaireview", status__exact="PENDING"
            ),
            url_permission="matches.view_submissionaireview",
        )
    if metrics["recent_ai_failures"] >= settings.OPERATIONS_AI_FAILURE_WARNING_COUNT:
        add(
            "warning",
            "AI_FAILURE_SPIKE",
            "Số AI Review thất bại gần đây vượt ngưỡng cảnh báo.",
            metrics["recent_ai_failures"],
            category="queue",
            action_label="Xem nhật ký",
            oldest_at=metrics["recent_ai_failures_oldest_at"],
            url=_admin_changelist(
                "matches", "submissionaireview", status__exact="FAILED"
            ),
            url_permission="matches.view_submissionaireview",
        )
    if metrics["fair_play_flags"]:
        add(
            "warning",
            "FAIR_PLAY_FLAGS_24H",
            "Có trận bị gắn cờ Fair Play trong 24 giờ gần nhất.",
            metrics["fair_play_flags"],
            category="fair_play",
            action_label="Xem Fair Play",
            oldest_at=metrics["fair_play_flags_oldest_at"],
            url=_admin_changelist(
                "matches", "matchintegritystate", is_flagged__exact="1"
            ),
            url_permission="matches.view_matchintegritystate",
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
                category="system",
                action_label="Xem nhật ký",
                oldest_at=_iso(now),
                url=url,
                url_permission="operations.view_workerheartbeat",
            )
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(
        alerts,
        key=lambda alert: (
            severity_order.get(alert["severity"], 3),
            alert["oldest_at"] or alert["checked_at"],
            alert["code"],
        ),
    )
