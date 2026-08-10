"""Read-only projection for post-match AI review status."""

from dataclasses import dataclass

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
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
                "Phân tích AI chỉ khả dụng sau khi trận đấu kết thúc."
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
        visible_player_ids = [player.id for player in visible_players]
        match_problems = list(
            MatchProblem.objects.filter(match=match).order_by("order", "id")
        )
        progress_by_key = {
            (progress.player_id, progress.match_problem_id): progress
            for progress in PlayerProblemProgress.objects.filter(
                match=match,
                player__in=visible_players,
            )
        }
        accepted_keys = set(
            Submission.objects.filter(
                match=match,
                player__in=visible_players,
                verdict=Submission.Verdict.ACCEPTED,
            ).values_list("player_id", "match_problem_id")
        )
        reviews = {}
        review_queryset = (
            SubmissionAIReview.objects.filter(
                Q(
                    progress__match=match,
                    progress__player_id__in=visible_player_ids,
                )
                | Q(
                    progress__isnull=True,
                    submission__match=match,
                    submission__player_id__in=visible_player_ids,
                )
            )
            .exclude(error_code="DUPLICATE_SUPERSEDED")
            .select_related("progress", "submission")
            .defer(
                "submission__source_code",
                "submission__judge_message",
                "submission__judge_token",
            )
            .order_by("-created_at", "-id")
        )
        for review in review_queryset:
            key = (
                (review.progress.player_id, review.progress.match_problem_id)
                if review.progress_id
                else (
                    review.submission.player_id,
                    review.submission.match_problem_id,
                )
            )
            reviews.setdefault(key, review)

        player_payloads = []
        all_terminal = True
        feature_enabled = settings.AI_REVIEW_ENABLED and match.ai_review_enabled
        for player in visible_players:
            review_payloads = []
            owns_row = current_player is not None and player.id == current_player.id
            for match_problem in match_problems:
                key = (player.id, match_problem.id)
                progress = progress_by_key.get(key)
                eligible = (
                    progress is not None
                    and progress.is_solved
                    and key in accepted_keys
                    and bool(match_problem.reference_solution_snapshot)
                )
                review = reviews.get(key)
                status = review.status if review is not None else (
                    "ELIGIBLE" if eligible else "NOT_ELIGIBLE"
                )
                if status in {
                    SubmissionAIReview.Status.PENDING,
                    SubmissionAIReview.Status.PROCESSING,
                }:
                    all_terminal = False
                can_request = status == "ELIGIBLE" and owns_row and feature_enabled
                can_retry = (
                    review is not None
                    and status == SubmissionAIReview.Status.FAILED
                    and review.failure_retryable
                    and review.manual_retry_count
                    < settings.AI_REVIEW_MAX_MANUAL_RETRIES
                    and owns_row
                    and feature_enabled
                )
                request_url = None
                if owns_row:
                    request_url = reverse(
                        "match-ai-review-request",
                        args=[match.id, match_problem.id],
                    )
                review_payloads.append(
                    {
                        "match_problem_id": match_problem.id,
                        "title": match_problem.title_snapshot,
                        "status": status,
                        "can_request": can_request,
                        "can_retry": can_retry,
                        "request_url": request_url,
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
