"""Server-authoritative Typing challenge lifecycle."""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from matches.models import Match, TypingChallenge
from matches.services.db import retry_transient_db_lock


class TypingChallengeError(Exception):
    """Base class for expected Typing challenge failures."""


class InvalidTypingChallengeError(TypingChallengeError):
    """Raised when the completion payload is invalid."""


class TypingChallengePermissionError(TypingChallengeError):
    """Raised when the caller is not the challenge target."""


class TypingChallengeNotFoundError(TypingChallengeError):
    """Raised when the challenge does not belong to the requested match."""


class TypingChallengeConflictError(TypingChallengeError):
    """Raised when the challenge can no longer be completed."""


@dataclass(frozen=True)
class TypingChallengeResult:
    challenge: TypingChallenge
    completed_now: bool


def has_active_typing_challenge(*, player_id: int, now=None) -> bool:
    evaluation_time = now or timezone.now()
    return TypingChallenge.objects.filter(
        effect__skill_use__target_player_id=player_id,
        effect__cancelled_at__isnull=True,
        completed_at__isnull=True,
        expires_at__gt=evaluation_time,
    ).exists()


@dataclass
class TypingChallengeService:
    def complete(
        self,
        *,
        user,
        match_id: int,
        challenge_id: int,
        typed_text: str,
        now=None,
    ) -> TypingChallengeResult:
        if not isinstance(typed_text, str):
            raise InvalidTypingChallengeError("typed_text must be a string.")
        return retry_transient_db_lock(
            lambda: self._complete_once(
                user=user,
                match_id=match_id,
                challenge_id=challenge_id,
                typed_text=typed_text,
                now=now,
            )
        )

    @staticmethod
    def _complete_once(
        *,
        user,
        match_id,
        challenge_id,
        typed_text,
        now,
    ) -> TypingChallengeResult:
        evaluation_time = now or timezone.now()
        with transaction.atomic():
            try:
                challenge = (
                    TypingChallenge.objects.select_for_update()
                    .select_related(
                        "effect__skill_use__match",
                        "effect__skill_use__target_player",
                    )
                    .get(
                        pk=challenge_id,
                        effect__skill_use__match_id=match_id,
                    )
                )
            except TypingChallenge.DoesNotExist as error:
                raise TypingChallengeNotFoundError(
                    "Typing challenge was not found."
                ) from error

            skill_use = challenge.effect.skill_use
            if skill_use.target_player.user_id != user.id:
                raise TypingChallengePermissionError(
                    "Only the challenged player can complete this challenge."
                )
            if challenge.completed_at is not None:
                return TypingChallengeResult(challenge, completed_now=False)

            match = Match.objects.select_for_update().get(pk=match_id)
            if match.status != Match.Status.PLAYING:
                raise TypingChallengeConflictError("Match is not playing.")
            if evaluation_time >= challenge.expires_at:
                raise TypingChallengeConflictError(
                    "Typing challenge has expired."
                )
            if typed_text != challenge.prompt:
                raise InvalidTypingChallengeError(
                    "The typed text does not match the prompt."
                )

            challenge.completed_at = evaluation_time
            challenge.save(update_fields=["completed_at"])
            challenge.effect.cancelled_at = evaluation_time
            challenge.effect.save(update_fields=["cancelled_at"])
            return TypingChallengeResult(challenge, completed_now=True)
