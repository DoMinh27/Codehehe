from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import CodeHeheAuthenticationForm, CodeHeheSetPasswordForm
from .views import (
    RateLimitedPasswordResetView,
    email_verification_confirm,
    email_verification_resend,
    email_verification_sent,
    player_profile,
    register,
)

urlpatterns = [
    path("profile/", player_profile, name="player-profile"),
    path("register/", register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=CodeHeheAuthenticationForm,
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "email-verification/sent/",
        email_verification_sent,
        name="email-verification-sent",
    ),
    path(
        "email-verification/confirm/<str:token>/",
        email_verification_confirm,
        name="email-verification-confirm",
    ),
    path(
        "email-verification/resend/",
        email_verification_resend,
        name="email-verification-resend",
    ),
    path(
        "password-reset/",
        RateLimitedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=CodeHeheSetPasswordForm,
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
