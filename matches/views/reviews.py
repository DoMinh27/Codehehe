from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from matches.services.ai_review_state import (
    AIReviewStateConflictError,
    AIReviewStateNotFoundError,
    AIReviewStatePermissionError,
    AIReviewStateService,
)

from .api import api_error


@login_required
@require_GET
def ai_review_state(request, match_id):
    try:
        payload = AIReviewStateService().get(
            user=request.user,
            match_id=match_id,
        )
    except AIReviewStateNotFoundError as error:
        return api_error(
            code="MATCH_NOT_FOUND",
            message=str(error),
            status=404,
        )
    except AIReviewStatePermissionError as error:
        return api_error(
            code="MATCH_FORBIDDEN",
            message=str(error),
            status=403,
        )
    except AIReviewStateConflictError as error:
        return api_error(
            code="MATCH_NOT_FINISHED",
            message=str(error),
            status=409,
        )
    return JsonResponse(payload)
