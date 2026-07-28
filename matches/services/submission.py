"""Submission orchestration for match problems."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from matches.models import Match, MatchPlayer, MatchProblem, Submission
from problems.models import TestCase
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
    ) -> Submission:
        if not isinstance(source_code, str) or not source_code.strip():
            raise InvalidSubmissionError("source_code must not be empty")

        submission = self._create_pending_submission(
            user=user,
            match_id=match_id,
            match_problem_id=match_problem_id,
            source_code=source_code,
        )
        test_cases = tuple(
            JudgeTestCase(
                input_data=test_case.input_data,
                expected_output=test_case.expected_output,
            )
            for test_case in TestCase.objects.filter(
                problem=submission.match_problem.problem,
                is_sample=False,
            )
        )

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
    ) -> Submission:
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
            if match.ends_at is None or timezone.now() > match.ends_at:
                raise SubmissionConflictError("match has ended")

            return Submission.objects.create(
                match=match,
                player=player,
                match_problem=match_problem,
                source_code=source_code,
            )

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
        submission.verdict = verdict
        submission.completed_at = timezone.now()
        submission.judge_message = messages[verdict]
        submission.save(update_fields=["verdict", "completed_at", "judge_message"])
        return submission

    def _complete_internal_error(self, submission: Submission) -> Submission:
        submission.verdict = Submission.Verdict.INTERNAL_ERROR
        submission.completed_at = timezone.now()
        submission.judge_message = "Judge is temporarily unavailable. Please try again."
        submission.save(update_fields=["verdict", "completed_at", "judge_message"])
        return submission
