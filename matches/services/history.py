from django.core.paginator import Paginator
from django.db.models import Count, F, Prefetch, Q
from django.urls import reverse

from matches.models import Match, MatchPlayer


FINISH_REASON_LABELS = {
    Match.FinishReason.TIMEOUT: "Hết giờ",
    Match.FinishReason.ALL_SOLVED: "Hoàn thành tất cả bài",
    Match.FinishReason.SURRENDER: "Đầu hàng",
}


def get_match_history_page(*, user, page_number, page_size: int = 10):
    players = (
        MatchPlayer.objects.select_related(
            "match",
            "match__winner",
            "match__surrendered_by",
        )
        .prefetch_related(
            Prefetch(
                "match__players",
                queryset=MatchPlayer.objects.select_related("user").order_by(
                    "joined_at",
                    "id",
                ),
                to_attr="history_players",
            )
        )
        .filter(
            user=user,
            match__status=Match.Status.FINISHED,
        )
        .annotate(
            solved_count=Count(
                "problem_progress",
                filter=Q(problem_progress__is_solved=True),
                distinct=True,
            ),
            problem_count=Count("match__match_problems", distinct=True),
        )
        .order_by(
            F("match__ended_at").desc(nulls_last=True),
            "-match_id",
        )
    )

    page_obj = Paginator(players, page_size).get_page(page_number)
    rows = []
    for player in page_obj.object_list:
        match = player.match
        opponent = next(
            (
                candidate
                for candidate in match.history_players
                if candidate.user_id != user.id
            ),
            None,
        )
        if match.is_draw:
            outcome = "DRAW"
            outcome_label = "Hòa"
        elif match.winner_id == user.id:
            outcome = "WIN"
            outcome_label = "Thắng"
        elif match.winner_id is not None:
            outcome = "LOSS"
            outcome_label = "Thua"
        else:
            outcome = "UNKNOWN"
            outcome_label = "Không xác định"

        rows.append(
            {
                "match": match,
                "opponent": opponent,
                "outcome": outcome,
                "outcome_label": outcome_label,
                "score": player.score,
                "opponent_score": opponent.score if opponent is not None else None,
                "solved_count": player.solved_count,
                "problem_count": player.problem_count,
                "finish_reason": FINISH_REASON_LABELS.get(
                    match.finish_reason,
                    "Không xác định",
                ),
                "result_url": reverse("match-result", args=[match.id]),
                "submissions_url": reverse("my-submissions", args=[match.id]),
            }
        )
    return page_obj, rows
