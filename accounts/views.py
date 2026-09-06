from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from matches.models import Match
from matches.services.room import get_active_match_player

from .email_services import (
    confirm_verification_token,
    email_request_is_limited,
    inspect_verification_token,
    resend_verification_email,
    send_verification_email,
)
from .forms import (
    EmailAddressForm,
    RegisterForm,
    VerifiedEmailPasswordResetForm,
)
from .registration_services import PendingRegistrationConflict
from .services import get_player_profile_stats


def register(request):
    if request.user.is_authenticated:
        return redirect("lobby")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            try:
                pending_registration = form.save()
            except PendingRegistrationConflict as error:
                if error.code == "PENDING_ACTIVE":
                    form.add_error(
                        None,
                        "Thông tin này đang chờ xác minh. "
                        "Hãy kiểm tra email hoặc yêu cầu gửi lại liên kết",
                    )
                elif error.field == "username":
                    form.add_error("username", "Tên đăng nhập này đã được sử dụng")
                else:
                    form.add_error("email", "Email này đã được sử dụng")
            else:
                if not email_request_is_limited(
                    request=request,
                    email=pending_registration.email,
                    scope="verification",
                ):
                    send_verification_email(
                        request=request,
                        pending_registration=pending_registration,
                    )
                return redirect("email-verification-sent")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def email_verification_sent(request):
    return render(request, "registration/email_verification_sent.html")


@never_cache
@require_http_methods(["GET", "POST"])
def email_verification_confirm(request, token):
    lookup = inspect_verification_token(token)
    if request.method == "POST" and lookup.status == "valid":
        lookup = confirm_verification_token(token)
    return render(
        request,
        "registration/email_verification_confirm.html",
        {"verification_status": lookup.status},
    )


@never_cache
@require_http_methods(["GET", "POST"])
def email_verification_resend(request):
    form = EmailAddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resend_verification_email(
            request=request,
            email=form.cleaned_data["email"],
        )
        return redirect("email-verification-sent")
    return render(
        request,
        "registration/email_verification_resend.html",
        {"form": form},
    )


class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    form_class = VerifiedEmailPasswordResetForm
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    html_email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        if email_request_is_limited(
            request=self.request,
            email=email,
            scope="password-reset",
        ):
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)


@login_required
def lobby(request):
    active_player = get_active_match_player(user=request.user)
    if active_player is not None:
        if active_player.match.status == Match.Status.WAITING:
            return redirect("waiting-room", room_code=active_player.match.room_code)
        return redirect("battle", match_id=active_player.match_id)
    return render(request, "accounts/lobby.html")


@login_required
def player_profile(request):
    return render(
        request,
        "accounts/profile.html",
        {"stats": get_player_profile_stats(user=request.user)},
    )
