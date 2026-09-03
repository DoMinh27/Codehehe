"""Private Fair Play ingestion endpoint for Battle clients."""

from uuid import UUID

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from matches.services.integrity import (
    CLIENT_EVENT_KINDS,
    PASTE,
    IntegrityConfigurationError,
    IntegrityNotFoundError,
    IntegrityPermissionError,
    IntegrityStateError,
    MatchIntegrityService,
)
from matches.services.rate_limit import is_rate_limited

from .api import ApiPayloadError, api_error, parse_json_object


def _uuid_string(value, *, field):
    if not isinstance(value, str):
        raise ApiPayloadError(code="INVALID_BODY", message=f"{field} không hợp lệ.")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise ApiPayloadError(
            code="INVALID_BODY",
            message=f"{field} không hợp lệ.",
        ) from error


def _parse_events(request):
    payload = parse_json_object(request)
    if set(payload) != {"client_session_id", "events"}:
        raise ApiPayloadError(
            code="INVALID_BODY",
            message="Payload Fair Play không hợp lệ.",
        )
    _uuid_string(payload["client_session_id"], field="client_session_id")
    raw_events = payload["events"]
    if (
        not isinstance(raw_events, list)
        or not raw_events
        or len(raw_events) > settings.MATCH_INTEGRITY_MAX_BATCH_SIZE
    ):
        raise ApiPayloadError(
            code="INVALID_BODY",
            message="Danh sách sự kiện Fair Play không hợp lệ.",
        )
    events = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            raise ApiPayloadError(
                code="INVALID_BODY",
                message="Sự kiện Fair Play không hợp lệ.",
            )
        kind = raw_event.get("kind")
        expected_fields = (
            {"event_id", "kind", "character_count"}
            if kind == PASTE
            else {"event_id", "kind"}
        )
        if set(raw_event) != expected_fields or kind not in CLIENT_EVENT_KINDS:
            raise ApiPayloadError(
                code="INVALID_BODY",
                message="Sự kiện Fair Play không hợp lệ.",
            )
        event = {
            "event_id": _uuid_string(raw_event["event_id"], field="event_id"),
            "kind": kind,
        }
        if kind == PASTE:
            character_count = raw_event["character_count"]
            if (
                not isinstance(character_count, int)
                or isinstance(character_count, bool)
                or not 0 <= character_count <= 1_000_000
            ):
                raise ApiPayloadError(
                    code="INVALID_BODY",
                    message="Số ký tự paste không hợp lệ.",
                )
            event["character_count"] = character_count
        events.append(event)
    return events


@login_required
@require_POST
@never_cache
def integrity_events(request, match_id):
    if is_rate_limited(
        scope="integrity",
        identity=f"{request.user.pk}:{match_id}",
        limit=settings.MATCH_INTEGRITY_RATE_LIMIT,
        window_seconds=settings.MATCH_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return api_error(
            code="RATE_LIMITED",
            message="Bạn gửi sự kiện Fair Play quá nhanh.",
            status=429,
        )
    try:
        events = _parse_events(request)
        result = MatchIntegrityService().record(
            user=request.user,
            match_id=match_id,
            events=events,
        )
    except ApiPayloadError as error:
        return api_error(code=error.code, message=error.message, status=error.status)
    except IntegrityNotFoundError as error:
        return api_error(code="MATCH_NOT_FOUND", message=str(error), status=404)
    except IntegrityPermissionError as error:
        return api_error(code="MATCH_FORBIDDEN", message=str(error), status=403)
    except IntegrityStateError as error:
        return api_error(code="MATCH_STATE_CONFLICT", message=str(error), status=409)
    except IntegrityConfigurationError as error:
        return api_error(
            code="INTEGRITY_CONFIGURATION_ERROR",
            message=str(error),
            status=503,
        )
    response = JsonResponse(
        {
            "accepted_event_ids": list(result.accepted_event_ids),
            "notice": result.notice.as_dict() if result.notice else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
