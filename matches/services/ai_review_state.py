"""Read-only projection for post-match AI review status."""

from dataclasses import dataclass

from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    SubmissionAIReview,
)


class AIReviewStateNotFoundError(Exception):
    """Raised when the requested match does not exist."""


class AIReviewStatePermissionError(Exception):
    """Raised when the caller cannot view reviews for the match."""


class AIReviewStateConflictError(Exception):
    """Raised when reviews are requested before the match finishes."""


@dataclass
class AIReviewStateService:
    def get(self, *, user, match_id: int) -> dict:
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist as error:
            raise AIReviewStateNotFoundError(
                "Không tìm thấy trận đấu."
            ) from error
        if match.status != Match.Status.FINISHED:
            raise AIReviewStateConflictError(
                "AI review chỉ khả dụng sau khi trận đấu kết thúc."
            )

        players = list(
            MatchPlayer.objects.filter(match=match)
            .select_related("user")
            .order_by("-score", "joined_at", "id")
        )
        current_player = next(
            (player for player in players if player.user_id == user.id),
            None,
        )
        can_view_all = user.is_staff or user.is_superuser
        if not can_view_all and current_player is None:
            raise AIReviewStatePermissionError(
                "Bạn không thuộc trận đấu này."
            )

        visible_players = players if can_view_all else [current_player]
        match_problems = list(
            MatchProblem.objects.filter(match=match).order_by("order", "id")
        )
        reviews = {}
        review_queryset = (
            SubmissionAIReview.objects.filter(submission__match=match)
            .select_related("submission")
            .order_by("submission_id", "-created_at", "-id")
        )
        for review in review_queryset:
            key = (
                review.submission.player_id,
                review.submission.match_problem_id,
            )
            reviews.setdefault(key, review)

        player_payloads = []
        all_terminal = True
        for player in visible_players:
            review_payloads = []
            for match_problem in match_problems:
                review = reviews.get((player.id, match_problem.id))
                status = (
                    review.status
                    if review is not None
                    else "NOT_ELIGIBLE"
                )
                if status in {
                    SubmissionAIReview.Status.PENDING,
                    SubmissionAIReview.Status.PROCESSING,
                }:
                    all_terminal = False
                review_payloads.append(
                    {
                        "match_problem_id": match_problem.id,
                        "title": match_problem.title_snapshot,
                        "status": status,
                        "analysis": (
                            review.result
                            if review is not None
                            and review.status
                            == SubmissionAIReview.Status.COMPLETED
                            else None
                        ),
                    }
                )
            player_payloads.append(
                {
                    "player_id": player.id,
                    "username": player.user.username,
                    "reviews": review_payloads,
                }
            )

        return {
            "match_id": match.id,
            "terminal": all_terminal,
            "players": player_payloads,
        }
