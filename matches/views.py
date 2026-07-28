import json
import math

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from problems.models import TestCase
from problems.services.judge import Judge0ConfigurationError, Judge0Service

from .models import Match, MatchPlayer, MatchProblem, PlayerProblemProgress
from .services.gameplay import (
    FinishMatchService,
    InsufficientProblemsError,
    MatchHasPendingSubmissionsError,
    MatchNotFoundError,
    MatchNotReadyToFinishError,
    MatchPermissionError,
    MatchPlayerCountError,
    MatchStateError,
    StartMatchService,
    SurrenderMatchService,
)
from .services.room import (
    AlreadyJoinedError,
    CreateRoomService,
    InvalidRoomCodeError,
    JoinRoomService,
    RoomCodeGenerationError,
    RoomFullError,
    RoomNotFoundError,
    RoomNotWaitingError,
    normalize_room_code,
)
from .services.scoring import ScoringService
from .services.run import (
    CodeRunConflictError,
    CodeRunNotFoundError,
    CodeRunPermissionError,
    CodeRunService,
    CodeRunUnavailableError,
    InvalidCodeRunError,
    UnavailableCodeRunner,
)
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
def create_room(request):
    try:
        match = CreateRoomService().create(user=request.user)
    except RoomCodeGenerationError as error:
        messages.error(request, str(error))
        return redirect("lobby")
    return redirect("waiting-room", room_code=match.room_code)


@login_required
@require_POST
def join_room(request):
    try:
        player = JoinRoomService().join(
            user=request.user,
            room_code=request.POST.get("room_code", ""),
        )
    except (
        InvalidRoomCodeError,
        RoomNotFoundError,
        RoomNotWaitingError,
        AlreadyJoinedError,
        RoomFullError,
    ) as error:
        messages.error(request, str(error))
        return redirect("lobby")
    return redirect("waiting-room", room_code=player.match.room_code)


def _get_room_for_member(*, user, room_code):
    try:
        normalized_code = normalize_room_code(room_code)
    except InvalidRoomCodeError:
        normalized_code = room_code
    match = get_object_or_404(Match, room_code=normalized_code)
    if not MatchPlayer.objects.filter(match=match, user=user).exists():
        raise PermissionDenied
    return match


def _room_players(match):
    return list(
        MatchPlayer.objects.filter(match=match)
        .select_related("user")
        .order_by("-is_host", "joined_at", "id")
    )


@login_required
def waiting_room(request, room_code):
    match = _get_room_for_member(user=request.user, room_code=room_code)
    players = _room_players(match)
    current_player = next(player for player in players if player.user_id == request.user.id)
    return render(
        request,
        "matches/waiting_room.html",
        {
            "match": match,
            "players": players,
            "current_player": current_player,
        },
    )


@login_required
def waiting_room_state(request, room_code):
    match = _get_room_for_member(user=request.user, room_code=room_code)
    players = _room_players(match)
    player_slots = [
        {"username": player.user.username, "is_host": player.is_host}
        for player in players
    ]
    while len(player_slots) < 2:
        player_slots.append(None)

    return JsonResponse(
        {
            "room_code": match.room_code,
            "status": match.status,
            "host": match.host.username,
            "players": player_slots,
            "is_full": len(players) == 2,
            "can_start": len(players) == 2 and match.status == Match.Status.WAITING,
            "battle_url": (
                reverse("battle", kwargs={"match_id": match.pk})
                if match.status in {Match.Status.PLAYING, Match.Status.FINISHED}
                else None
            ),
        }
    )


@login_required
@require_POST
def start_match(request, match_id):
    try:
        match = StartMatchService().start(user=request.user, match_id=match_id)
    except MatchNotFoundError:
        return JsonResponse({"error": "Không tìm thấy trận đấu."}, status=404)
    except MatchPermissionError as error:
        return JsonResponse({"error": str(error)}, status=403)
    except (
        MatchPlayerCountError,
        MatchStateError,
        InsufficientProblemsError,
    ) as error:
        messages.error(request, str(error))
        match = get_object_or_404(Match, pk=match_id)
        return redirect("waiting-room", room_code=match.room_code)
    return redirect("battle", match_id=match.pk)


@login_required
def battle(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    players = list(
        MatchPlayer.objects.filter(match=match)
        .select_related("user")
        .order_by("-is_host", "joined_at", "id")
    )
    current_player = next(
        (player for player in players if player.user_id == request.user.id),
        None,
    )
    if current_player is None:
        raise PermissionDenied
    if match.status == Match.Status.WAITING:
        return redirect("waiting-room", room_code=match.room_code)
    if match.status == Match.Status.FINISHED:
        return redirect("match-result", match_id=match.pk)

    sample_tests = TestCase.objects.filter(is_sample=True).order_by("order", "id")
    match_problems = list(
        match.match_problems.select_related("problem").prefetch_related(
            Prefetch(
                "problem__test_cases",
                queryset=sample_tests,
                to_attr="battle_sample_tests",
            )
        )
    )
    opponent = next(
        (player for player in players if player.pk != current_player.pk),
        None,
    )
    return render(
        request,
        "matches/battle.html",
        {
            "match": match,
            "match_problems": match_problems,
            "current_player": current_player,
            "opponent": opponent,
        },
    )


@login_required
def match_state(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    players = list(
        MatchPlayer.objects.filter(match=match)
        .select_related("user")
        .order_by("-is_host", "joined_at", "id")
    )
    current_player = next(
        (player for player in players if player.user_id == request.user.id),
        None,
    )
    if current_player is None:
        raise PermissionDenied
    opponent = next(
        (player for player in players if player.pk != current_player.pk),
        None,
    )

    solved_progress = list(
        PlayerProblemProgress.objects.filter(match=match, is_solved=True).values(
            "player_id",
            "match_problem_id",
        )
    )
    match_problems = list(
        MatchProblem.objects.filter(match=match)
        .select_related("first_solver")
        .order_by("order", "id")
    )
    now = timezone.now()
    remaining_seconds = (
        max(0, math.ceil((match.ends_at - now).total_seconds()))
        if match.ends_at is not None and match.status == Match.Status.PLAYING
        else 0
    )

    def solved_ids(player):
        return [
            row["match_problem_id"]
            for row in solved_progress
            if row["player_id"] == player.id
        ]

    return JsonResponse(
        {
            "status": match.status,
            "server_time": now.isoformat(),
            "remaining_seconds": remaining_seconds,
            "my_score": current_player.score,
            "opponent_score": opponent.score if opponent else 0,
            "my_solved_problem_ids": solved_ids(current_player),
            "opponent_solved_problem_ids": solved_ids(opponent) if opponent else [],
            "first_solvers": {
                str(match_problem.id): (
                    match_problem.first_solver_id
                    if match_problem.first_solver_id
                    else None
                )
                for match_problem in match_problems
            },
            "winner_id": match.winner_id,
            "is_draw": match.is_draw,
            "finish_reason": match.finish_reason,
            "surrendered_by_id": match.surrendered_by_id,
            "result_url": reverse("match-result", kwargs={"match_id": match.pk}),
        }
    )


@login_required
@require_POST
def finalize_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if not MatchPlayer.objects.filter(match=match, user=request.user).exists():
        raise PermissionDenied
    try:
        match = FinishMatchService().finalize(match_id=match_id)
    except MatchHasPendingSubmissionsError as error:
        return JsonResponse(
            {"status": "PENDING", "message": str(error)},
            status=202,
        )
    except MatchNotReadyToFinishError as error:
        return JsonResponse({"error": str(error)}, status=409)
    except (MatchPlayerCountError, MatchStateError) as error:
        return JsonResponse({"error": str(error)}, status=409)
    return JsonResponse(
        {
            "status": match.status,
            "result_url": reverse("match-result", kwargs={"match_id": match.pk}),
        }
    )


@login_required
@require_POST
def surrender_match(request, match_id):
    try:
        match = SurrenderMatchService().surrender(
            user=request.user,
            match_id=match_id,
        )
    except MatchNotFoundError:
        return JsonResponse({"error": "Không tìm thấy trận đấu."}, status=404)
    except MatchPermissionError as error:
        return JsonResponse({"error": str(error)}, status=403)
    except (MatchPlayerCountError, MatchStateError) as error:
        return JsonResponse({"error": str(error)}, status=409)
    return JsonResponse(
        {
            "status": match.status,
            "result_url": reverse("match-result", kwargs={"match_id": match.pk}),
        }
    )


@login_required
def match_result(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    players = list(
        MatchPlayer.objects.filter(match=match)
        .select_related("user")
        .order_by("-score", "joined_at", "id")
    )
    if not request.user.is_staff and all(
        player.user_id != request.user.id for player in players
    ):
        raise PermissionDenied
    if match.status != Match.Status.FINISHED:
        if any(player.user_id == request.user.id for player in players):
            return redirect("battle", match_id=match.pk)
        raise PermissionDenied

    solved_counts = {
        row["player_id"]: row["count"]
        for row in PlayerProblemProgress.objects.filter(
            match=match,
            is_solved=True,
        )
        .values("player_id")
        .annotate(count=Count("id"))
    }
    match_problems = list(
        MatchProblem.objects.filter(match=match)
        .select_related("first_solver__user")
        .order_by("order", "id")
    )
    return render(
        request,
        "matches/result.html",
        {
            "match": match,
            "player_results": [
                {
                    "player": player,
                    "solved_count": solved_counts.get(player.id, 0),
                }
                for player in players
            ],
            "match_problems": match_problems,
        },
    )


@login_required
@require_POST
def run_code(request, match_id, match_problem_id):
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

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
        submission = SubmissionService(
            judge_service,
            scoring_service=ScoringService(),
            finish_service=FinishMatchService(),
        ).submit(
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
