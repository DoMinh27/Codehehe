import json
import math

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from matches.models import MatchPlayer, SkillEffect
from matches.services.gameplay import FinishMatchService
from matches.skills.service import (
    InvalidSkillUseError,
    SkillService,
    SkillUseConflictError,
    SkillUseNotFoundError,
    SkillUsePermissionError,
)
from matches.skills.typing import (
    InvalidTypingChallengeError,
    TypingChallengeConflictError,
    TypingChallengeNotFoundError,
    TypingChallengePermissionError,
    TypingChallengeService,
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
