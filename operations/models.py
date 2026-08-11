from django.db import models


class WorkerHeartbeat(models.Model):
    class Worker(models.TextChoices):
        AI_REVIEW = "AI_REVIEW", "AI review"
        MATCH_SWEEPER = "MATCH_SWEEPER", "Match sweeper"

    class Status(models.TextChoices):
        OK = "OK", "OK"
        FAILED = "FAILED", "Failed"
        DISABLED = "DISABLED", "Disabled"

    worker = models.CharField(max_length=32, choices=Worker.choices, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    last_heartbeat_at = models.DateTimeField(db_index=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["worker"]
        permissions = [
            (
                "view_operations_dashboard",
                "Can view the operations dashboard",
            ),
        ]

    def __str__(self):
        return f"{self.get_worker_display()}: {self.get_status_display()}"

