from django.contrib.auth.decorators import login_required
from django.db import OperationalError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from matches.rules import RulesetConfigurationError
from matches.services.rematch import RematchError, RematchService, get_rematch_state
from matches.services.room import RoomCodeGenerationError
from matches.views.api import ApiPayloadError, api_error, parse_json_object


@never_cache
@login_required
@require_GET
def rematch_state(request, match_id):
    try:
        return JsonResponse(get_rematch_state(user=request.user, match_id=match_id))
    except RematchError as error:
        return api_error(code=error.code, message=error.message, status=error.status)


@never_cache
@login_required
@require_POST
def rematch_action(request, match_id):
    try:
        payload = parse_json_object(request)
        state = RematchService().act(
            user=request.user, match_id=match_id, action=payload.get("action")
        )
        return JsonResponse(state)
    except (ApiPayloadError, RematchError) as error:
        return api_error(code=error.code, message=error.message, status=error.status)
    except (RoomCodeGenerationError, RulesetConfigurationError):
        return api_error(
            code="REMATCH_UNAVAILABLE",
            message="Chưa thể tạo phòng tái đấu. Vui lòng thử lại.",
            status=503,
        )
    except OperationalError as error:
        if "locked" not in str(error).lower() and "busy" not in str(error).lower():
            raise
        return api_error(
            code="REMATCH_BUSY",
            message="Máy chủ đang bận. Vui lòng cập nhật rồi thử lại.",
            status=503,
        )
