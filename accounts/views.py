from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from matches.models import Match
from matches.services.room import get_active_match_player

from .forms import RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("lobby")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def lobby(request):
    active_player = get_active_match_player(user=request.user)
    if active_player is not None:
        if active_player.match.status == Match.Status.WAITING:
            return redirect("waiting-room", room_code=active_player.match.room_code)
        return redirect("battle", match_id=active_player.match_id)
    return render(request, "accounts/lobby.html")
