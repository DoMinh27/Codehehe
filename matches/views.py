import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from problems.services.judge import Judge0ConfigurationError, Judge0Service

from .services.submission import (
    InvalidSubmissionError,
    SubmissionConflictError,
    SubmissionNotFoundError,
    SubmissionPermissionError,
    SubmissionService,
    UnavailableJudgeService,
)


@login_required
@require_POST
def submit_submission(request, match_id, match_problem_id):
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    try:
        judge_service = Judge0Service.from_environment()
    except Judge0ConfigurationError as error:
        judge_service = UnavailableJudgeService(error)

    try:
        submission = SubmissionService(judge_service).submit(
            user=request.user,
            match_id=match_id,
            match_problem_id=match_problem_id,
            source_code=payload.get("source_code"),
        )
    except InvalidSubmissionError:
        return JsonResponse({"error": "source_code must not be empty."}, status=400)
    except SubmissionPermissionError:
        return JsonResponse({"error": "You are not a player in this match."}, status=403)
    except SubmissionNotFoundError:
        return JsonResponse({"error": "Match problem was not found."}, status=404)
    except SubmissionConflictError as error:
        return JsonResponse({"error": str(error)}, status=409)

    return JsonResponse(
        {
            "id": submission.pk,
            "verdict": submission.verdict,
            "received_at": submission.received_at.isoformat(),
            "completed_at": submission.completed_at.isoformat(),
            "message": submission.judge_message,
        },
        status=201,
    )
