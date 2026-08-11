from django.contrib import admin

from .models import WorkerHeartbeat


@admin.register(WorkerHeartbeat)
class WorkerHeartbeatAdmin(admin.ModelAdmin):
    list_display = (
        "worker",
        "status",
        "last_heartbeat_at",
        "last_success_at",
        "last_failure_at",
        "last_duration_ms",
        "error_code",
    )
    list_filter = ("worker", "status")
    readonly_fields = (
        "worker",
        "status",
        "last_heartbeat_at",
        "last_success_at",
        "last_failure_at",
        "last_duration_ms",
        "error_code",
        "summary",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

