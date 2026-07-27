import json

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
from .models import Match, MatchPlayer


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
