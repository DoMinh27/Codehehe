from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from matches.services.ai_review import (
    AIReviewRequestConflictError,
    AIReviewRequestNotFoundError,
    AIReviewRequestPermissionError,
    AIReviewRequestService,
)

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


@login_required
@require_POST
def request_ai_review(request, match_id, match_problem_id):
    try:
        _review, queued = AIReviewRequestService().request(
            user=request.user,
            match_id=match_id,
            match_problem_id=match_problem_id,
        )
    except AIReviewRequestNotFoundError as error:
        return api_error(code=error.code, message=str(error), status=404)
    except AIReviewRequestPermissionError as error:
        return api_error(code=error.code, message=str(error), status=403)
    except AIReviewRequestConflictError as error:
        return api_error(code=error.code, message=str(error), status=409)

    payload = AIReviewStateService().get(
        user=request.user,
        match_id=match_id,
    )
    return JsonResponse(payload, status=202 if queued else 200)
