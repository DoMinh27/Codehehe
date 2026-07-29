import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from matches.services.gameplay import FinishMatchService
from matches.services.rate_limit import is_rate_limited
from matches.services.run import (
    CodeRunConflictError,
    CodeRunNotFoundError,
    CodeRunPermissionError,
    CodeRunService,
    CodeRunUnavailableError,
    InvalidCodeRunError,
    UnavailableCodeRunner,
)
from matches.services.scoring import ScoringService
from matches.services.submission import (
    InvalidSubmissionError,
    SubmissionConflictError,
    SubmissionNotFoundError,
    SubmissionPermissionError,
    SubmissionService,
    UnavailableJudgeService,
)
from problems.services.judge import (
    Judge0ConfigurationError,
    Judge0Service,
)


@login_required
@require_POST
def run_code(request, match_id, match_problem_id):
    if is_rate_limited(
        scope="run",
        identity=f"{request.user.pk}:{match_id}",
        limit=settings.MATCH_RUN_RATE_LIMIT,
        window_seconds=settings.MATCH_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return JsonResponse(
            {"error": "Bạn chạy thử quá nhanh. Vui lòng chờ một chút."},
            status=429,
        )
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Request body must be valid JSON."},
            status=400,
        )
    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Request body must be a JSON object."},
            status=400,
        )

    try:
        runner = Judge0Service.from_environment()
    except Judge0ConfigurationError as error:
        runner = UnavailableCodeRunner(error)

    try:
        result = CodeRunService(runner).run(
            user=request.user,
            match_id=match_id,
            match_problem_id=match_problem_id,
            source_code=payload.get("source_code"),
            input_data=payload.get("input_data", ""),
        )
    except InvalidCodeRunError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except CodeRunPermissionError as error:
        return JsonResponse({"error": str(error)}, status=403)
    except CodeRunNotFoundError as error:
        return JsonResponse({"error": str(error)}, status=404)
    except CodeRunConflictError as error:
        return JsonResponse({"error": str(error)}, status=409)
    except CodeRunUnavailableError as error:
        return JsonResponse({"error": str(error)}, status=503)

    messages = {
        "COMPLETED": "Program completed.",
        "COMPILATION_ERROR": "Compilation error.",
        "RUNTIME_ERROR": "Runtime error.",
        "TIME_LIMIT_EXCEEDED": "Time limit exceeded.",
    }
    return JsonResponse(
        {
            "verdict": result.verdict,
            "stdout": result.stdout,
            "message": result.diagnostic or messages[result.verdict],
        }
    )


@login_required
@require_POST
def submit_submission(request, match_id, match_problem_id):
    if is_rate_limited(
        scope="submit",
        identity=f"{request.user.pk}:{match_id}",
        limit=settings.MATCH_SUBMIT_RATE_LIMIT,
        window_seconds=settings.MATCH_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return JsonResponse(
            {"error": "Bạn nộp bài quá nhanh. Vui lòng chờ một chút."},
            status=429,
        )
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Request body must be valid JSON."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Request body must be a JSON object."},
            status=400,
        )

    try:
        judge_service = Judge0Service.from_environment()
    except Judge0ConfigurationError as error:
        judge_service = UnavailableJudgeService(error)

    try:
        submission = SubmissionService(
            judge_service,
            scoring_service=ScoringService(),
            finish_service=FinishMatchService(),
        ).submit(
            user=request.user,
            match_id=match_id,
            match_problem_id=match_problem_id,
            source_code=payload.get("source_code"),
            idempotency_key=payload.get("idempotency_key"),
        )
    except InvalidSubmissionError:
        return JsonResponse(
            {"error": "source_code must not be empty."},
            status=400,
        )
    except SubmissionPermissionError:
        return JsonResponse(
            {"error": "You are not a player in this match."},
            status=403,
        )
    except SubmissionNotFoundError:
        return JsonResponse(
            {"error": "Match problem was not found."},
            status=404,
        )
    except SubmissionConflictError as error:
        return JsonResponse({"error": str(error)}, status=409)

    return JsonResponse(
        {
            "id": submission.pk,
            "verdict": submission.verdict,
            "received_at": submission.received_at.isoformat(),
            "completed_at": (
                submission.completed_at.isoformat()
                if submission.completed_at is not None
                else None
            ),
            "message": (
                submission.judge_message
                or "Submission is still being judged."
            ),
        },
        status=201,
    )
