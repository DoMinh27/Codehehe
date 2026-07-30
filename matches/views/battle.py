from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
)
from matches.services.gameplay import (
    FinishMatchService,
    InsufficientProblemsError,
    InsufficientSkillsError,
    MatchHasPendingSubmissionsError,
    MatchNotFoundError,
    MatchNotReadyToFinishError,
    MatchPermissionError,
    MatchPlayerCountError,
    MatchStateError,
    StartMatchService,
    SurrenderMatchService,
)
from matches.services.match_state import (
    MatchStateNotFoundError,
    MatchStatePermissionError,
    MatchStateService,
)
from matches.services.scoring import ScoringService
from matches.services.submission import PendingSubmissionRecoveryService

from .api import api_error


@login_required
@require_POST
def start_match(request, match_id):
    try:
        match = StartMatchService().start(
            user=request.user,
            match_id=match_id,
        )
    except MatchNotFoundError:
        return api_error(
            code="MATCH_NOT_FOUND",
            message="Không tìm thấy trận đấu.",
            status=404,
        )
    except MatchPermissionError as error:
        return api_error(
            code="MATCH_FORBIDDEN",
            message=str(error),
            status=403,
        )
    except (
        MatchPlayerCountError,
        MatchStateError,
        InsufficientProblemsError,
        InsufficientSkillsError,
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

    match_problems = list(match.match_problems.order_by("order", "id"))
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
            "battle_config": {
                "matchId": match.pk,
                "userId": request.user.pk,
                "currentPlayerId": current_player.pk,
                "opponentPlayerId": opponent.pk if opponent else None,
                "stateUrl": reverse(
                    "match-state",
                    kwargs={"match_id": match.pk},
                ),
                "finalizeUrl": reverse(
                    "match-finalize",
                    kwargs={"match_id": match.pk},
                ),
                "surrenderUrl": reverse(
                    "match-surrender",
                    kwargs={"match_id": match.pk},
                ),
                "resultUrl": reverse(
                    "match-result",
                    kwargs={"match_id": match.pk},
                ),
                "skillUseUrlTemplate": reverse(
                    "skill-use",
                    kwargs={
                        "match_id": match.pk,
                        "skill_code": "__skill__",
                    },
                ),
                "typingCompleteUrlTemplate": reverse(
                    "typing-challenge-complete",
                    kwargs={
                        "match_id": match.pk,
                        "challenge_id": 999999,
                    },
                ).replace("999999", "__challenge__"),
            },
        },
    )


@login_required
def match_state(request, match_id):
    try:
        payload = MatchStateService().get(
            user=request.user,
            match_id=match_id,
        )
    except MatchStateNotFoundError as error:
        return api_error(
            code="MATCH_NOT_FOUND",
            message=str(error),
            status=404,
        )
    except MatchStatePermissionError as error:
        return api_error(
            code="MATCH_FORBIDDEN",
            message=str(error),
            status=403,
        )
    return JsonResponse(payload)


@login_required
@require_POST
def finalize_match(request, match_id):
    try:
        match = Match.objects.get(pk=match_id)
    except Match.DoesNotExist:
        return api_error(
            code="MATCH_NOT_FOUND",
            message="Không tìm thấy trận đấu.",
            status=404,
        )
    if not MatchPlayer.objects.filter(
        match=match,
        user=request.user,
    ).exists():
        return api_error(
            code="MATCH_FORBIDDEN",
            message="Bạn không thuộc trận đấu này.",
            status=403,
        )
    PendingSubmissionRecoveryService(
        scoring_service=ScoringService(),
    ).recover(match_id=match_id)
    try:
        match = FinishMatchService().finalize(match_id=match_id)
    except MatchHasPendingSubmissionsError as error:
        return JsonResponse(
            {"status": "PENDING", "message": str(error)},
            status=202,
        )
    except MatchNotReadyToFinishError as error:
        return api_error(
            code="MATCH_NOT_READY",
            message=str(error),
            status=409,
        )
    except MatchPlayerCountError as error:
        return api_error(
            code="MATCH_PLAYER_COUNT_INVALID",
            message=str(error),
            status=409,
        )
    except MatchStateError as error:
        return api_error(
            code="MATCH_STATE_CONFLICT",
            message=str(error),
            status=409,
        )
    return JsonResponse(
        {
            "status": match.status,
            "result_url": reverse(
                "match-result",
                kwargs={"match_id": match.pk},
            ),
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
        return api_error(
            code="MATCH_NOT_FOUND",
            message="Không tìm thấy trận đấu.",
            status=404,
        )
    except MatchPermissionError as error:
        return api_error(
            code="MATCH_FORBIDDEN",
            message=str(error),
            status=403,
        )
    except MatchPlayerCountError as error:
        return api_error(
            code="MATCH_PLAYER_COUNT_INVALID",
            message=str(error),
            status=409,
        )
    except MatchStateError as error:
        return api_error(
            code="MATCH_STATE_CONFLICT",
            message=str(error),
            status=409,
        )
    return JsonResponse(
        {
            "status": match.status,
            "result_url": reverse(
                "match-result",
                kwargs={"match_id": match.pk},
            ),
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
        if any(
            player.user_id == request.user.id for player in players
        ):
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
