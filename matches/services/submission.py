"""Submission orchestration for match problems."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from matches.models import Match, MatchPlayer, MatchProblem, Submission
from matches.skills.typing import has_active_typing_challenge
from problems.services.judge import (
    Judge0ConfigurationError,
    Judge0UnavailableError,
    JudgeResult,
    JudgeService,
    JudgeTestCase,
    Verdict,
)

from .gameplay import FinishMatchService
from .scoring import ScoringService

logger = logging.getLogger(__name__)
MAX_SOURCE_CODE_BYTES = 64 * 1024
MAX_IDEMPOTENCY_KEY_LENGTH = 64


class SubmissionError(Exception):
    """Base class for expected submission failures."""


class InvalidSubmissionError(SubmissionError):
    """Raised when the submitted source is invalid."""


class SubmissionPermissionError(SubmissionError):
    """Raised when the user is not a player in the match."""


class SubmissionNotFoundError(SubmissionError):
    """Raised when a requested match problem is not in the match."""


class SubmissionConflictError(SubmissionError):
    """Raised when the match cannot currently accept submissions."""


@dataclass
class UnavailableJudgeService:
    """Defers a judge setup failure until a pending submission exists."""

    error: Exception

    def judge(self, **kwargs) -> JudgeResult:
        raise self.error


@dataclass
class SubmissionService:
    """Validate, persist, and judge a source-code submission."""

    judge_service: JudgeService
    scoring_service: ScoringService | None = None
    finish_service: FinishMatchService | None = None

    def submit(
        self,
        *,
        user,
        match_id: int,
        match_problem_id: int,
        source_code: str,
        idempotency_key: str | None = None,
    ) -> Submission:
        if not isinstance(source_code, str) or not source_code.strip():
            raise InvalidSubmissionError("source_code must not be empty")
        if len(source_code.encode("utf-8")) > MAX_SOURCE_CODE_BYTES:
            raise InvalidSubmissionError("source_code is too large")
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str):
                raise InvalidSubmissionError("idempotency_key must be a string")
            idempotency_key = idempotency_key.strip()
            if not idempotency_key or len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
                raise InvalidSubmissionError("idempotency_key is invalid")

        try:
            submission, created = self._create_pending_submission(
                user=user,
                match_id=match_id,
                match_problem_id=match_problem_id,
                source_code=source_code,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            if idempotency_key is None:
                raise
            submission = Submission.objects.get(
                player__user=user,
                match_id=match_id,
                match_problem_id=match_problem_id,
                idempotency_key=idempotency_key,
            )
            created = False
        if not created:
            return submission

        try:
            test_cases = tuple(
                JudgeTestCase(
                    input_data=test_case["input_data"],
                    expected_output=test_case["expected_output"],
                )
                for test_case in submission.match_problem.hidden_tests_snapshot
            )
        except (KeyError, TypeError):
            logger.error(
                "Invalid hidden-test snapshot for match problem %s",
                submission.match_problem_id,
            )
            test_cases = ()

        if not test_cases:
            logger.error(
                "No hidden-test snapshot for submission %s",
                submission.pk,
            )
            completed_submission = self._complete_internal_error(submission)
            return self._after_completion(completed_submission)

        try:
            result = self.judge_service.judge(
                source_code=source_code,
                test_cases=test_cases,
            )
        except (Judge0ConfigurationError, Judge0UnavailableError):
            logger.exception("Judge is unavailable for submission %s", submission.pk)
            completed_submission = self._complete_internal_error(submission)
        except Exception:
            logger.exception("Unexpected judge failure for submission %s", submission.pk)
            completed_submission = self._complete_internal_error(submission)
        else:
            completed_submission = self._complete_submission(submission, result)

        return self._after_completion(completed_submission)

    def _after_completion(self, completed_submission: Submission) -> Submission:
        if self.scoring_service is not None:
            completed_submission = self.scoring_service.process_submission(
                completed_submission.pk
            )
        if self.finish_service is not None:
            self.finish_service.try_finalize(match_id=completed_submission.match_id)
        return completed_submission

    def _create_pending_submission(
        self,
        *,
        user,
        match_id: int,
        match_problem_id: int,
        source_code: str,
        idempotency_key: str | None,
    ) -> tuple[Submission, bool]:
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise SubmissionNotFoundError("match does not exist") from error

            try:
                player = MatchPlayer.objects.get(match=match, user=user)
            except MatchPlayer.DoesNotExist as error:
                raise SubmissionPermissionError("user is not a match player") from error

            try:
                match_problem = MatchProblem.objects.select_related("problem").get(
                    pk=match_problem_id,
                    match=match,
                )
            except MatchProblem.DoesNotExist as error:
                raise SubmissionNotFoundError("match problem does not exist") from error

            if match.status != Match.Status.PLAYING:
                raise SubmissionConflictError("match is not playing")
            player_deadline = player.personal_ends_at
            if player_deadline is None or timezone.now() > player_deadline:
                raise SubmissionConflictError("your personal time has ended")
            if has_active_typing_challenge(player_id=player.id):
                raise SubmissionConflictError(
                    "complete the Typing challenge before submitting"
                )

            if idempotency_key is not None:
                existing = Submission.objects.filter(
                    player=player,
                    match_problem=match_problem,
                    idempotency_key=idempotency_key,
                ).first()
                if existing is not None:
                    return existing, False

            return Submission.objects.create(
                match=match,
                player=player,
                match_problem=match_problem,
                source_code=source_code,
                idempotency_key=idempotency_key,
            ), True

    def _complete_submission(
        self, submission: Submission, result: JudgeResult
    ) -> Submission:
        verdict = {
            Verdict.ACCEPTED: Submission.Verdict.ACCEPTED,
            Verdict.WRONG_ANSWER: Submission.Verdict.WRONG_ANSWER,
            Verdict.COMPILATION_ERROR: Submission.Verdict.COMPILATION_ERROR,
            Verdict.RUNTIME_ERROR: Submission.Verdict.RUNTIME_ERROR,
            Verdict.TIME_LIMIT_EXCEEDED: Submission.Verdict.TIME_LIMIT_EXCEEDED,
        }.get(result.verdict, Submission.Verdict.INTERNAL_ERROR)
        messages = {
            Submission.Verdict.ACCEPTED: "Accepted.",
            Submission.Verdict.WRONG_ANSWER: "Wrong answer.",
            Submission.Verdict.COMPILATION_ERROR: "Compilation error.",
            Submission.Verdict.RUNTIME_ERROR: "Runtime error.",
            Submission.Verdict.TIME_LIMIT_EXCEEDED: "Time limit exceeded.",
            Submission.Verdict.INTERNAL_ERROR: "Judge is temporarily unavailable. Please try again.",
        }
        Submission.objects.filter(
            pk=submission.pk,
            verdict=Submission.Verdict.PENDING,
        ).update(
            verdict=verdict,
            completed_at=timezone.now(),
            judge_message=messages[verdict],
        )
        submission.refresh_from_db()
        return submission

    def _complete_internal_error(self, submission: Submission) -> Submission:
        Submission.objects.filter(
            pk=submission.pk,
            verdict=Submission.Verdict.PENDING,
        ).update(
            verdict=Submission.Verdict.INTERNAL_ERROR,
            completed_at=timezone.now(),
            judge_message="Judge is temporarily unavailable. Please try again.",
        )
        submission.refresh_from_db()
        return submission


@dataclass
class PendingSubmissionRecoveryService:
    """Turn abandoned pending records into safe terminal errors."""

    scoring_service: ScoringService | None = None
    finish_service: FinishMatchService | None = None
    timeout_seconds: int | None = None

    def recover(self, *, match_id: int | None = None, now=None) -> int:
        recovery_time = now or timezone.now()
        timeout_seconds = self.timeout_seconds
        if timeout_seconds is None:
            timeout_seconds = settings.MATCH_PENDING_SUBMISSION_TIMEOUT_SECONDS
        cutoff = recovery_time - timedelta(seconds=timeout_seconds)
        stale_ids = list(
            Submission.objects.filter(
                verdict=Submission.Verdict.PENDING,
                received_at__lte=cutoff,
            )
            .filter(**({"match_id": match_id} if match_id is not None else {}))
            .values_list("id", flat=True)
        )
        recovered = 0
        affected_match_ids = set()
        for submission_id in stale_ids:
            updated = Submission.objects.filter(
                pk=submission_id,
                verdict=Submission.Verdict.PENDING,
            ).update(
                verdict=Submission.Verdict.INTERNAL_ERROR,
                completed_at=recovery_time,
                judge_message="Judge timed out. Please submit again.",
            )
            if not updated:
                continue
            recovered += 1
            submission = Submission.objects.get(pk=submission_id)
            affected_match_ids.add(submission.match_id)
            if self.scoring_service is not None:
                self.scoring_service.process_submission(submission_id)

        if self.finish_service is not None:
            for affected_match_id in affected_match_ids:
                self.finish_service.try_finalize(match_id=affected_match_id, now=recovery_time)
        return recovered
