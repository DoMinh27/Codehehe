"""Custom-input execution without submission or scoring side effects."""

import logging
from dataclasses import dataclass

from django.utils import timezone

from matches.models import Match, MatchPlayer, MatchProblem
from problems.services.judge import (
    CodeRunner,
    Judge0ConfigurationError,
    Judge0UnavailableError,
    RunResult,
)

logger = logging.getLogger(__name__)

MAX_SOURCE_BYTES = 64 * 1024
MAX_INPUT_BYTES = 16 * 1024
MAX_STDOUT_CHARS = 16 * 1024
MAX_DIAGNOSTIC_CHARS = 8 * 1024


class CodeRunError(Exception):
    """Base class for expected custom-input failures."""


class InvalidCodeRunError(CodeRunError):
    """Raised when source code or custom input is invalid."""


class CodeRunPermissionError(CodeRunError):
    """Raised when a non-player attempts to run code."""


class CodeRunNotFoundError(CodeRunError):
    """Raised when the match or match problem does not exist."""


class CodeRunConflictError(CodeRunError):
    """Raised when the match cannot currently run code."""


class CodeRunUnavailableError(CodeRunError):
    """Raised when the external runner cannot complete the request."""


@dataclass
class UnavailableCodeRunner:
    """Preserve a configuration failure until validation has completed."""

    error: Exception

    def run(self, **kwargs) -> RunResult:
        raise self.error


@dataclass
class CodeRunService:
    """Validate and execute player code without persisting a Submission."""

    runner: CodeRunner

    def run(
        self,
        *,
        user,
        match_id: int,
        match_problem_id: int,
        source_code: str,
        input_data: str,
    ) -> RunResult:
        self._validate_payload(source_code=source_code, input_data=input_data)
        self._validate_context(
            user=user,
            match_id=match_id,
            match_problem_id=match_problem_id,
        )

        try:
            result = self.runner.run(
                source_code=source_code,
                input_data=input_data,
            )
        except (Judge0ConfigurationError, Judge0UnavailableError) as error:
            logger.exception("Custom-input runner is unavailable")
            raise CodeRunUnavailableError(
                "Judge is temporarily unavailable. Please try again."
            ) from error
        except Exception as error:
            logger.exception("Unexpected custom-input runner failure")
            raise CodeRunUnavailableError(
                "Judge is temporarily unavailable. Please try again."
            ) from error

        return RunResult(
            verdict=result.verdict,
            stdout=self._safe_text(result.stdout, MAX_STDOUT_CHARS),
            diagnostic=self._safe_text(
                result.diagnostic,
                MAX_DIAGNOSTIC_CHARS,
            ),
        )

    @staticmethod
    def _validate_payload(*, source_code: str, input_data: str) -> None:
        if not isinstance(source_code, str) or not source_code.strip():
            raise InvalidCodeRunError("source_code must not be empty.")
        if not isinstance(input_data, str):
            raise InvalidCodeRunError("input_data must be a string.")
        if len(source_code.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise InvalidCodeRunError("source_code is too large.")
        if len(input_data.encode("utf-8")) > MAX_INPUT_BYTES:
            raise InvalidCodeRunError("input_data is too large.")

    @staticmethod
    def _validate_context(*, user, match_id: int, match_problem_id: int) -> None:
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist as error:
            raise CodeRunNotFoundError("Match was not found.") from error
        if not MatchPlayer.objects.filter(match=match, user=user).exists():
            raise CodeRunPermissionError("You are not a player in this match.")
        if not MatchProblem.objects.filter(
            pk=match_problem_id,
            match=match,
        ).exists():
            raise CodeRunNotFoundError("Match problem was not found.")
        if match.status != Match.Status.PLAYING:
            raise CodeRunConflictError("Match is not playing.")
        if match.ends_at is None or timezone.now() > match.ends_at:
            raise CodeRunConflictError("Match has ended.")

    @staticmethod
    def _safe_text(value: str, limit: int) -> str:
        return str(value or "").replace("\x00", "")[:limit]
