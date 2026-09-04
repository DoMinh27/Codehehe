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
    """Keep only shortcuts whose underlying ModelAdmin is viewable by the user."""
    if user.is_superuser:
        return snapshot

    def sanitize(value):
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if not isinstance(value, dict):
            return value

        cleaned = {}
        for key, item in value.items():
            if key.endswith("_permission"):
                continue
            if key == "url" or key.endswith("_url"):
                permission = value.get(f"{key}_permission") or value.get(
                    "url_permission"
                )
                cleaned[key] = item if permission and user.has_perm(permission) else ""
                continue
            cleaned[key] = sanitize(item)
        return cleaned

    return sanitize(deepcopy(snapshot))


@require_GET
def dashboard(request):
    _require_dashboard_permission(request)
    snapshot = _snapshot_for_user(get_dashboard_snapshot(), request.user)
    context = {
        **admin.site.each_context(request),
        "title": "Dashboard vận hành",
        "snapshot": snapshot,
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
