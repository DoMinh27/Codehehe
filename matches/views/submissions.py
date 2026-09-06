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
from matches.views.api import (
    ApiPayloadError,
    api_error,
    clean_ui_message,
    parse_json_object,
)
from problems.services.judge import Judge0ConfigurationError, Judge0Service


def _payload_or_error(request):
    try:
        return parse_json_object(request), None
    except ApiPayloadError as error:
        return None, api_error(
            code=error.code,
            message=error.message,
            status=error.status,
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
        return api_error(
            code="RATE_LIMITED",
            message="Bạn chạy thử quá nhanh. Vui lòng chờ một chút.",
            status=429,
        )

    payload, error_response = _payload_or_error(request)
    if error_response is not None:
        return error_response

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
        return api_error(code="INVALID_CODE_RUN", message=str(error), status=400)
    except CodeRunPermissionError as error:
        return api_error(code="CODE_RUN_FORBIDDEN", message=str(error), status=403)
    except CodeRunNotFoundError as error:
        return api_error(
            code="MATCH_PROBLEM_NOT_FOUND",
            message=str(error),
            status=404,
        )
    except CodeRunConflictError as error:
        return api_error(code="CODE_RUN_CONFLICT", message=str(error), status=409)
    except CodeRunUnavailableError as error:
        return api_error(
            code="CODE_RUN_UNAVAILABLE",
            message=str(error),
            status=503,
        )

    messages = {
        "COMPLETED": "Program completed",
        "COMPILATION_ERROR": "Compilation error",
        "RUNTIME_ERROR": "Runtime error",
        "TIME_LIMIT_EXCEEDED": "Time limit exceeded",
    }
    return JsonResponse(
        {
            "verdict": result.verdict,
            "stdout": result.stdout,
            "message": clean_ui_message(
                result.diagnostic or messages[result.verdict]
            ),
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
        return api_error(
            code="RATE_LIMITED",
            message="Bạn nộp bài quá nhanh. Vui lòng chờ một chút.",
            status=429,
        )

    payload, error_response = _payload_or_error(request)
    if error_response is not None:
        return error_response

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
    except InvalidSubmissionError as error:
        return api_error(
            code="INVALID_SUBMISSION",
            message=str(error) or "source_code must not be empty.",
            status=400,
        )
    except SubmissionPermissionError as error:
        return api_error(
            code="SUBMISSION_FORBIDDEN",
            message=str(error) or "You are not a player in this match.",
            status=403,
        )
    except SubmissionNotFoundError as error:
        return api_error(
            code="MATCH_PROBLEM_NOT_FOUND",
            message=str(error) or "Match problem was not found.",
            status=404,
        )
    except SubmissionConflictError as error:
        return api_error(
            code="SUBMISSION_CONFLICT",
            message=str(error),
            status=409,
        )

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
            "message": clean_ui_message(
                submission.judge_message or "Submission is still being judged"
            ),
        },
        status=201,
    )
