from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from matches.models import Match, MatchPlayer
from matches.services.room import (
    ActiveMatchExistsError,
    AlreadyJoinedError,
    CreateRoomService,
    InvalidRoomCodeError,
    JoinRoomService,
    LeaveRoomService,
    RoomCodeGenerationError,
    RoomFullError,
    RoomLeaveError,
    RoomNotFoundError,
    RoomNotWaitingError,
    get_active_match_player,
    normalize_room_code,
)


def _active_match_redirect(match):
    if match.status == Match.Status.WAITING:
        return redirect("waiting-room", room_code=match.room_code)
    if match.status == Match.Status.PLAYING:
        return redirect("battle", match_id=match.pk)
    return redirect("match-result", match_id=match.pk)


@login_required
def active_match_state(request):
    active_player = get_active_match_player(user=request.user)
    if active_player is None:
        return JsonResponse({"active": False, "status": None, "url": None})
    match = active_player.match
    target = (
        reverse("waiting-room", kwargs={"room_code": match.room_code})
        if match.status == Match.Status.WAITING
        else reverse("battle", kwargs={"match_id": match.pk})
    )
    return JsonResponse(
        {
            "active": True,
            "status": match.status,
            "url": target,
        }
    )


@login_required
@require_POST
def create_room(request):
    try:
        match = CreateRoomService().create(user=request.user)
    except ActiveMatchExistsError as error:
        messages.info(request, str(error))
        return _active_match_redirect(error.match)
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
    except ActiveMatchExistsError as error:
        messages.info(request, str(error))
        return _active_match_redirect(error.match)
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
    if match.status == Match.Status.PLAYING:
        return redirect("battle", match_id=match.pk)
    if match.status == Match.Status.FINISHED:
        return redirect("match-result", match_id=match.pk)
    if match.status == Match.Status.CANCELLED:
        messages.info(request, "Phòng đã bị hủy.")
        return redirect("lobby")
    players = _room_players(match)
    current_player = next(
        player for player in players if player.user_id == request.user.id
    )
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
            "can_start": (
                len(players) == 2
                and match.status == Match.Status.WAITING
            ),
            "battle_url": (
                reverse("battle", kwargs={"match_id": match.pk})
                if match.status
                in {Match.Status.PLAYING, Match.Status.FINISHED}
                else None
            ),
            "lobby_url": (
                reverse("lobby")
                if match.status == Match.Status.CANCELLED
                else None
            ),
        }
    )


@login_required
@require_POST
def leave_room(request, room_code):
    try:
        match = LeaveRoomService().leave(
            user=request.user,
            room_code=room_code,
        )
    except RoomNotFoundError:
        return JsonResponse({"error": "Không tìm thấy phòng."}, status=404)
    except RoomLeaveError as error:
        return JsonResponse({"error": str(error)}, status=409)
    if match.status == Match.Status.CANCELLED:
        messages.info(request, "Phòng đã được hủy.")
    else:
        messages.info(request, "Bạn đã rời phòng.")
    return redirect("lobby")
