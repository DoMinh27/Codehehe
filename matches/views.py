import json
import math
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from problems.services.judge import Judge0ConfigurationError, Judge0Service

from .models import (
    Match,
    MatchPlayer,
    MatchProblem,
    MatchSkill,
    PlayerProblemProgress,
    SkillEffect,
    SkillUse,
)
from .services.gameplay import (
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
from .skills.service import (
    InvalidSkillUseError,
    SkillService,
    SkillUseConflictError,
    SkillUseNotFoundError,
    SkillUsePermissionError,
)
from .skills.typing import (
    InvalidTypingChallengeError,
    TypingChallengeConflictError,
    TypingChallengeNotFoundError,
    TypingChallengePermissionError,
    TypingChallengeService,
)
from .services.room import (
    AlreadyJoinedError,
    ActiveMatchExistsError,
    CreateRoomService,
    InvalidRoomCodeError,
    JoinRoomService,
    LeaveRoomService,
    RoomCodeGenerationError,
    RoomFullError,
    RoomNotFoundError,
    RoomNotWaitingError,
    RoomLeaveError,
    get_active_match_player,
    normalize_room_code,
)
from .services.rate_limit import is_rate_limited
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
    PendingSubmissionRecoveryService,
    UnavailableJudgeService,
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
        match = LeaveRoomService().leave(user=request.user, room_code=room_code)
    except RoomNotFoundError:
        return JsonResponse({"error": "Không tìm thấy phòng."}, status=404)
    except RoomLeaveError as error:
        return JsonResponse({"error": str(error)}, status=409)
    if match.status == Match.Status.CANCELLED:
        messages.info(request, "Phòng đã được hủy.")
    else:
        messages.info(request, "Bạn đã rời phòng.")
    return redirect("lobby")


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

    progress_rows = list(
        PlayerProblemProgress.objects.filter(match=match).values(
            "player_id",
            "match_problem_id",
            "is_solved",
            "match_problem__first_solver_id",
        )
    )
    match_skills = list(
        MatchSkill.objects.filter(match=match)
        .annotate(
            current_quantity=Coalesce(
                Max(
                    "player_inventory__quantity",
                    filter=Q(player_inventory__player=current_player),
                ),
                0,
            )
        )
        .order_by("id")
    )
    now = timezone.now()
    active_effects = list(
        SkillEffect.objects.filter(
            skill_use__match=match,
            skill_use__target_player=current_player,
            cancelled_at__isnull=True,
            expires_at__gt=now,
        )
        .select_related(
            "skill_use__match_skill",
            "skill_use__source_player__user",
            "typing_challenge",
        )
        .order_by("expires_at", "id")
    )
    active_typing_challenge = next(
        (
            effect.typing_challenge
            for effect in active_effects
            if hasattr(effect, "typing_challenge")
        ),
        None,
    )
    recent_skill_uses = list(
        SkillUse.objects.filter(match=match)
        .select_related(
            "match_skill",
            "source_player__user",
            "target_player__user",
        )
        .order_by("-used_at", "-id")[:10]
    )

    def remaining_seconds(player):
        deadline = None
        if (
            player is not None
            and match.started_at is not None
            and match.ends_at is not None
        ):
            deadline = max(
                match.started_at,
                match.ends_at
                - timedelta(seconds=player.time_penalty_seconds),
            )
        return (
            max(0, math.ceil((deadline - now).total_seconds()))
            if deadline is not None and match.status == Match.Status.PLAYING
            else 0
        )

    def solved_ids(player):
        return [
            row["match_problem_id"]
            for row in progress_rows
            if row["player_id"] == player.id and row["is_solved"]
        ]

    return JsonResponse(
        {
            "status": match.status,
            "server_time": now.isoformat(),
            "remaining_seconds": remaining_seconds(current_player),
            "opponent_remaining_seconds": remaining_seconds(opponent),
            "my_timed_out": remaining_seconds(current_player) == 0,
            "opponent_timed_out": remaining_seconds(opponent) == 0,
            "my_score": current_player.score,
            "opponent_score": opponent.score if opponent else 0,
            "my_energy": current_player.energy,
            "my_action_locked": active_typing_challenge is not None,
            "typing_challenge": (
                {
                    "id": active_typing_challenge.id,
                    "prompt": active_typing_challenge.prompt,
                    "expires_at": (
                        active_typing_challenge.expires_at.isoformat()
                    ),
                }
                if active_typing_challenge is not None
                else None
            ),
            "my_skills": [
                {
                    "code": match_skill.code_snapshot,
                    "name": match_skill.name_snapshot,
                    "description": match_skill.description_snapshot,
                    "energy_cost": match_skill.energy_cost_snapshot,
                    "duration_seconds": match_skill.duration_seconds_snapshot,
                    "quantity": match_skill.current_quantity,
                }
                for match_skill in match_skills
            ],
            "active_effects": [
                {
                    "id": effect.id,
                    "skill_use_id": effect.skill_use_id,
                    "code": effect.skill_use.match_skill.code_snapshot,
                    "source_player_id": effect.skill_use.source_player_id,
                    "source_username": (
                        effect.skill_use.source_player.user.username
                    ),
                    "started_at": effect.started_at.isoformat(),
                    "expires_at": effect.expires_at.isoformat(),
                }
                for effect in active_effects
            ],
            "recent_skill_uses": [
                {
                    "id": skill_use.id,
                    "code": skill_use.match_skill.code_snapshot,
                    "name": skill_use.match_skill.name_snapshot,
                    "source_player_id": skill_use.source_player_id,
                    "source_username": skill_use.source_player.user.username,
                    "target_player_id": skill_use.target_player_id,
                    "target_username": skill_use.target_player.user.username,
                    "used_at": skill_use.used_at.isoformat(),
                }
                for skill_use in reversed(recent_skill_uses)
            ],
            "my_solved_problem_ids": solved_ids(current_player),
            "opponent_solved_problem_ids": solved_ids(opponent) if opponent else [],
            "first_solvers": {
                str(row["match_problem_id"]): (
                    row["match_problem__first_solver_id"]
                )
                for row in progress_rows
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
def use_skill(request, match_id, skill_code):
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
        result = SkillService().use(
            user=request.user,
            match_id=match_id,
            skill_code=skill_code,
            target_player_id=payload.get("target_player_id"),
            idempotency_key=payload.get("idempotency_key"),
        )
    except InvalidSkillUseError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except SkillUsePermissionError as error:
        return JsonResponse({"error": str(error)}, status=403)
    except SkillUseNotFoundError as error:
        return JsonResponse({"error": str(error)}, status=404)
    except SkillUseConflictError as error:
        return JsonResponse({"error": str(error)}, status=409)

    skill_use = result.skill_use
    effect = (
        SkillEffect.objects.select_related("typing_challenge")
        .filter(skill_use=skill_use)
        .first()
    )
    typing_challenge = (
        effect.typing_challenge
        if effect is not None and hasattr(effect, "typing_challenge")
        else None
    )
    source = MatchPlayer.objects.select_related("match").get(
        pk=skill_use.source_player_id
    )
    target = MatchPlayer.objects.select_related("match").get(
        pk=skill_use.target_player_id
    )
    now = timezone.now()

    def remaining_seconds(player):
        deadline = player.personal_ends_at
        return (
            max(0, math.ceil((deadline - now).total_seconds()))
            if deadline is not None
            else 0
        )

    FinishMatchService().try_finalize(match_id=match_id, now=now)
    return JsonResponse(
        {
            "id": skill_use.id,
            "code": skill_use.match_skill.code_snapshot,
            "target_player_id": skill_use.target_player_id,
            "energy_spent": skill_use.energy_spent,
            "used_at": skill_use.used_at.isoformat(),
            "effect": (
                {
                    "id": effect.id,
                    "started_at": effect.started_at.isoformat(),
                    "expires_at": effect.expires_at.isoformat(),
                }
                if effect is not None
                else None
            ),
            "challenge": (
                {
                    "id": typing_challenge.id,
                    "expires_at": typing_challenge.expires_at.isoformat(),
                }
                if typing_challenge is not None
                else None
            ),
            "my_energy": source.energy,
            "remaining_seconds": remaining_seconds(source),
            "opponent_remaining_seconds": remaining_seconds(target),
        },
        status=201 if result.created else 200,
    )


@login_required
@require_POST
def complete_typing_challenge(request, match_id, challenge_id):
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
        result = TypingChallengeService().complete(
            user=request.user,
            match_id=match_id,
            challenge_id=challenge_id,
            typed_text=payload.get("typed_text"),
        )
    except InvalidTypingChallengeError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except TypingChallengePermissionError as error:
        return JsonResponse({"error": str(error)}, status=403)
    except TypingChallengeNotFoundError as error:
        return JsonResponse({"error": str(error)}, status=404)
    except TypingChallengeConflictError as error:
        return JsonResponse({"error": str(error)}, status=409)

    return JsonResponse(
        {
            "id": result.challenge.id,
            "status": "COMPLETED",
            "completed_at": result.challenge.completed_at.isoformat(),
            "completed_now": result.completed_now,
        }
    )


@login_required
@require_POST
def finalize_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if not MatchPlayer.objects.filter(match=match, user=request.user).exists():
        raise PermissionDenied
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
            idempotency_key=payload.get("idempotency_key"),
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
