"""Match start and finish lifecycle services."""

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
)
from problems.models import Problem

from .scoring import ScoringService


class MatchLifecycleError(Exception):
    """Base class for expected match lifecycle failures."""


class MatchNotFoundError(MatchLifecycleError):
    """Raised when a requested match does not exist."""


class MatchPermissionError(MatchLifecycleError):
    """Raised when a non-host attempts a host-only action."""


class MatchStateError(MatchLifecycleError):
    """Raised when the match is not in the required state."""


class MatchPlayerCountError(MatchLifecycleError):
    """Raised when the match does not have exactly two players."""


class InsufficientProblemsError(MatchLifecycleError):
    """Raised when the problem bank cannot supply the V1 set."""


class MatchNotReadyToFinishError(MatchLifecycleError):
    """Raised when neither finish condition has been reached."""


class MatchHasPendingSubmissionsError(MatchLifecycleError):
    """Raised while an on-time submission is still being judged."""


@dataclass
class StartMatchService:
    """Create a frozen four-problem battle and start its server timer."""

    def start(self, *, user, match_id: int) -> Match:
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise MatchNotFoundError("Không tìm thấy trận đấu.") from error

            if match.host_id != user.id:
                raise MatchPermissionError("Chỉ host được bắt đầu trận.")
            if match.status != Match.Status.WAITING or match.started_at is not None:
                raise MatchStateError("Trận đấu không còn ở trạng thái chờ.")

            players = list(
                MatchPlayer.objects.select_for_update()
                .filter(match=match)
                .order_by("joined_at", "id")
            )
            if len(players) != 2:
                raise MatchPlayerCountError("Phòng cần đúng hai người để bắt đầu.")

            easy_problems = list(
                Problem.objects.filter(
                    is_active=True,
                    difficulty=Problem.Difficulty.EASY,
                ).order_by("order", "id")[:2]
            )
            medium_problems = list(
                Problem.objects.filter(
                    is_active=True,
                    difficulty=Problem.Difficulty.MEDIUM,
                ).order_by("order", "id")[:2]
            )
            if len(easy_problems) != 2 or len(medium_problems) != 2:
                raise InsufficientProblemsError(
                    "Cần ít nhất 2 bài Easy và 2 bài Medium đang hoạt động."
                )

            match_problems = [
                MatchProblem(
                    match=match,
                    problem=problem,
                    order=order,
                    points=problem.points,
                    title_snapshot=problem.title,
                    statement_snapshot=problem.statement,
                    starter_code_snapshot=problem.starter_code,
                    difficulty_snapshot=problem.difficulty,
                )
                for order, problem in enumerate(
                    [*easy_problems, *medium_problems],
                    start=1,
                )
            ]
            MatchProblem.objects.bulk_create(match_problems)
            PlayerProblemProgress.objects.bulk_create(
                [
                    PlayerProblemProgress(
                        match=match,
                        player=player,
                        match_problem=match_problem,
                    )
                    for player in players
                    for match_problem in match_problems
                ]
            )

            match.status = Match.Status.PLAYING
            match.started_at = timezone.now()
            match.save(update_fields=["status", "started_at", "updated_at"])
            return match


@dataclass
class FinishMatchService:
    """Idempotently finalize an eligible match and persist its result."""

    scoring_service: ScoringService = field(default_factory=ScoringService)

    def finalize(self, *, match_id: int, now=None) -> Match:
        evaluation_time = now or timezone.now()
        unprocessed_ids = list(
            Submission.objects.filter(
                match_id=match_id,
                is_score_processed=False,
            )
            .exclude(verdict=Submission.Verdict.PENDING)
            .values_list("id", flat=True)
        )
        for submission_id in unprocessed_ids:
            self.scoring_service.process_submission(submission_id)

        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise MatchNotFoundError("Không tìm thấy trận đấu.") from error

            if match.status == Match.Status.FINISHED:
                return match
            if match.status != Match.Status.PLAYING or match.ends_at is None:
                raise MatchStateError("Trận đấu không ở trạng thái đang chơi.")

            players = list(
                MatchPlayer.objects.select_for_update()
                .filter(match=match)
                .order_by("id")
            )
            if len(players) != 2:
                raise MatchPlayerCountError(
                    "Trận đấu cần đúng hai người để kết thúc."
                )
            problem_count = MatchProblem.objects.filter(match=match).count()
            solved_counts = {
                row["player_id"]: row["count"]
                for row in PlayerProblemProgress.objects.filter(
                    match=match,
                    is_solved=True,
                )
                .values("player_id")
                .annotate(count=Count("id"))
            }
            both_solved_all = problem_count > 0 and all(
                solved_counts.get(player.id, 0) == problem_count for player in players
            )
            deadline_reached = evaluation_time >= match.ends_at
            if not deadline_reached and not both_solved_all:
                raise MatchNotReadyToFinishError(
                    "Trận đấu chưa đủ điều kiện kết thúc."
                )

            if Submission.objects.filter(
                match=match,
                verdict=Submission.Verdict.PENDING,
                received_at__lte=match.ends_at,
            ).exists():
                raise MatchHasPendingSubmissionsError(
                    "Đang chờ submission hợp lệ hoàn tất."
                )

            if Submission.objects.filter(
                match=match,
                is_score_processed=False,
            ).exists():
                raise MatchHasPendingSubmissionsError(
                    "Đang hoàn tất tính điểm submission."
                )

            highest_score = max(player.score for player in players)
            leaders = [player for player in players if player.score == highest_score]
            match.status = Match.Status.FINISHED
            match.ended_at = evaluation_time
            if len(leaders) == 1:
                match.winner_id = leaders[0].user_id
                match.is_draw = False
            else:
                match.winner = None
                match.is_draw = True
            match.save(
                update_fields=[
                    "status",
                    "ended_at",
                    "winner",
                    "is_draw",
                    "updated_at",
                ]
            )
            return match

    def try_finalize(self, *, match_id: int, now=None) -> Match | None:
        try:
            return self.finalize(match_id=match_id, now=now)
        except (
            MatchHasPendingSubmissionsError,
            MatchNotReadyToFinishError,
            MatchPlayerCountError,
            MatchStateError,
        ):
            return None
