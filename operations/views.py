from copy import deepcopy

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .dashboard import get_dashboard_snapshot


def _require_dashboard_permission(request):
    if not request.user.has_perm("operations.view_operations_dashboard"):
        raise PermissionDenied


def _no_store(response):
    response["Cache-Control"] = "private, no-store"
    return response


def _snapshot_for_user(snapshot, user):
    """Hide links to sensitive ModelAdmin pages from limited operators."""
    if user.is_superuser:
        return snapshot

    sanitized = deepcopy(snapshot)
    for alert in sanitized.get("alerts", []):
        alert["url"] = ""
    for match in sanitized.get("live_matches", []):
        match["url"] = ""
    for item in sanitized.get("submissions", {}).get("internal_errors", []):
        item["url"] = ""
    return sanitized


@require_GET
def dashboard(request):
    _require_dashboard_permission(request)
    snapshot = _snapshot_for_user(get_dashboard_snapshot(), request.user)
    context = {
        **admin.site.each_context(request),
        "title": "Dashboard vận hành",
        "snapshot": snapshot,
        "health_items": (
            ("web", "Web App", snapshot["health"]["web"]),
            ("database", "Database", snapshot["health"]["database"]),
            ("judge0", "Judge0", snapshot["health"]["judge0"]),
            ("ai_worker", "AI Worker", snapshot["health"]["ai_worker"]),
            (
                "match_sweeper",
                "Match Sweeper",
                snapshot["health"]["match_sweeper"],
            ),
        ),
        "counter_items": (
            ("Phòng đang chờ", snapshot["counters"]["waiting_matches"]),
            ("Trận đang chơi", snapshot["counters"]["playing_matches"]),
            ("Người chơi trong trận", snapshot["counters"]["playing_players"]),
            ("Submission pending", snapshot["counters"]["pending_submissions"]),
            ("AI Review đang xử lý", snapshot["counters"]["active_ai_reviews"]),
            ("Cảnh báo", snapshot["counters"]["alerts"]),
        ),
        "kpi_items": (
            ("Tài khoản mới", snapshot["kpis"]["new_accounts"]),
            ("Người có hoạt động", snapshot["kpis"]["active_players"]),
            ("Trận hoàn thành", snapshot["kpis"]["finished_matches"]),
            ("Trận bị hủy", snapshot["kpis"]["cancelled_matches"]),
        ),
        "refresh_seconds": settings.OPERATIONS_DASHBOARD_REFRESH_SECONDS,
        "hidden_refresh_seconds": (
            settings.OPERATIONS_DASHBOARD_HIDDEN_REFRESH_SECONDS
        ),
        "request_timeout_seconds": 5,
    }
    return _no_store(render(request, "operations/dashboard.html", context))


@require_GET
def dashboard_state(request):
    _require_dashboard_permission(request)
    force = request.GET.get("refresh") == "1"
    snapshot = _snapshot_for_user(
        get_dashboard_snapshot(force=force),
        request.user,
    )
    return _no_store(JsonResponse(snapshot))
