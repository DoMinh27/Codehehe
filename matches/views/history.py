from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    PlayerProblemProgress,
    Submission,
)
from matches.services.history import get_match_history_page


@login_required
def match_history(request):
    page_obj, history_rows = get_match_history_page(
        user=request.user,
        page_number=request.GET.get("page"),
    )
    return render(
        request,
        "matches/history.html",
        {
            "page_obj": page_obj,
            "history_rows": history_rows,
        },
    )


@login_required
def my_submissions(request, match_id):
    player = get_object_or_404(
        MatchPlayer.objects.select_related("match"),
        match_id=match_id,
        match__status=Match.Status.FINISHED,
        user=request.user,
    )
    match_problems = list(
        MatchProblem.objects.filter(match_id=match_id)
        .only("id", "match_id", "order", "title_snapshot")
        .order_by("order", "id")
    )
    problem_by_id = {problem.id: problem for problem in match_problems}
    selected_problem = match_problems[0] if match_problems else None
    requested_problem_id = request.GET.get("problem")
    if requested_problem_id:
        try:
            selected_problem = problem_by_id[int(requested_problem_id)]
        except (KeyError, TypeError, ValueError) as error:
            raise Http404 from error

    accepted_submission_id = None
    if selected_problem is None:
        submissions = Submission.objects.none()
    else:
        accepted_submission_id = (
            PlayerProblemProgress.objects.filter(
                player=player,
                match_problem=selected_problem,
            )
            .values_list("accepted_submission_id", flat=True)
            .first()
        )
        submissions = (
            Submission.objects.filter(
                player=player,
                match_problem=selected_problem,
            )
            .only(
                "id",
                "player_id",
                "match_problem_id",
                "source_code",
                "language",
                "verdict",
                "received_at",
                "completed_at",
                "runtime_ms",
                "memory_kb",
            )
            .order_by("-received_at", "-id")
        )

    page_obj = Paginator(submissions, 20).get_page(request.GET.get("page"))
    response = render(
        request,
        "matches/my_submissions.html",
        {
            "match": player.match,
            "match_problems": match_problems,
            "selected_problem": selected_problem,
            "accepted_submission_id": accepted_submission_id,
            "page_obj": page_obj,
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response
