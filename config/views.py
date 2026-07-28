import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse

from problems.services.judge import (
    Judge0ConfigurationError,
    Judge0Service,
    Judge0UnavailableError,
)

logger = logging.getLogger(__name__)


def health(request):
    return JsonResponse({"status": "ok"})


def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.exception("Database readiness check failed")
        return JsonResponse(
            {"status": "unavailable", "dependency": "database"},
            status=503,
        )
    if settings.READINESS_CHECK_JUDGE0:
        try:
            Judge0Service.from_environment().healthcheck()
        except (Judge0ConfigurationError, Judge0UnavailableError):
            logger.exception("Judge0 readiness check failed")
            return JsonResponse(
                {"status": "unavailable", "dependency": "judge0"},
                status=503,
            )
    return JsonResponse({"status": "ready"})
