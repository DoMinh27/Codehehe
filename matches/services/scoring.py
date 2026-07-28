"""Idempotent score and first-solve processing."""

from django.db import transaction
from django.db.models import Q, Sum

from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
)


class ScoringError(Exception):
    """Base class for scoring failures."""


class ProgressNotFoundError(ScoringError):
    """Raised when a started match is missing player progress."""


class ScoringService:
    """Apply base points and safely finalize first-solve."""

    def process_submission(self, submission_id: int) -> Submission:
        submission_reference = Submission.objects.only("match_id").get(
            pk=submission_id
        )
        with transaction.atomic():
            match = Match.objects.select_for_update().get(
                pk=submission_reference.match_id
            )
            submission = (
                Submission.objects.select_for_update()
                .select_related("player", "match_problem")
                .get(pk=submission_id)
            )
            if submission.verdict == Submission.Verdict.PENDING:
                return submission
            if match.status != Match.Status.PLAYING:
                if not submission.is_score_processed:
                    submission.is_score_processed = True
                    submission.save(update_fields=["is_score_processed"])
                return submission

            match_problem = MatchProblem.objects.select_for_update().get(
                pk=submission.match_problem_id
            )
            if submission.verdict == Submission.Verdict.ACCEPTED:
                self._award_base_score(submission, match_problem)

            finalized = self._finalize_first_solve(match_problem)
            if finalized:
                Submission.objects.filter(match_problem=match_problem).exclude(
                    verdict=Submission.Verdict.PENDING
                ).update(is_score_processed=True)
            elif submission.verdict != Submission.Verdict.ACCEPTED:
                submission.is_score_processed = True
                submission.save(update_fields=["is_score_processed"])

            submission.refresh_from_db()
            return submission

    def _award_base_score(
        self,
        submission: Submission,
        match_problem: MatchProblem,
    ) -> None:
        try:
            progress = PlayerProblemProgress.objects.select_for_update().get(
                player_id=submission.player_id,
                match_problem=match_problem,
            )
        except PlayerProblemProgress.DoesNotExist as error:
            raise ProgressNotFoundError(
                "Player progress is missing for a started match."
            ) from error

        if not progress.is_solved:
            progress.is_solved = True
            progress.solved_at = submission.received_at
            progress.base_points_awarded = match_problem.points
            progress.accepted_submission = submission
            progress.save(
                update_fields=[
                    "is_solved",
                    "solved_at",
                    "base_points_awarded",
                    "accepted_submission",
                    "updated_at",
                ]
            )
            self._sync_player_score(submission.player_id)
        elif progress.solved_at is None or submission.received_at < progress.solved_at:
            progress.solved_at = submission.received_at
            progress.accepted_submission = submission
            progress.save(
                update_fields=["solved_at", "accepted_submission", "updated_at"]
            )

    def _finalize_first_solve(self, match_problem: MatchProblem) -> bool:
        if match_problem.first_solver_id is not None:
            return True

        candidate = (
            Submission.objects.filter(
                match_problem=match_problem,
                verdict=Submission.Verdict.ACCEPTED,
            )
            .order_by("received_at", "id")
            .first()
        )
        if candidate is None:
            return False

        earlier_pending = Submission.objects.filter(
            match_problem=match_problem,
            verdict=Submission.Verdict.PENDING,
        ).filter(
            Q(received_at__lt=candidate.received_at)
            | Q(received_at=candidate.received_at, id__lt=candidate.id)
        )
        if earlier_pending.exists():
            return False

        progress = PlayerProblemProgress.objects.select_for_update().get(
            player_id=candidate.player_id,
            match_problem=match_problem,
        )
        if progress.first_solve_bonus_awarded == 0:
            progress.first_solve_bonus_awarded = 1
            progress.save(
                update_fields=["first_solve_bonus_awarded", "updated_at"]
            )

        match_problem.first_solver_id = candidate.player_id
        match_problem.first_solved_at = candidate.received_at
        match_problem.save(update_fields=["first_solver", "first_solved_at"])
        self._sync_player_score(candidate.player_id)
        return True

    @staticmethod
    def _sync_player_score(player_id: int) -> None:
        player = MatchPlayer.objects.select_for_update().get(pk=player_id)
        totals = PlayerProblemProgress.objects.filter(player_id=player_id).aggregate(
            base=Sum("base_points_awarded"),
            bonus=Sum("first_solve_bonus_awarded"),
        )
        player.score = (totals["base"] or 0) + (totals["bonus"] or 0)
        player.save(update_fields=["score"])
