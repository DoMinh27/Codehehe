from django.contrib.auth import views as auth_views
from django.urls import path

from .views import player_profile, register

urlpatterns = [
    path("profile/", player_profile, name="player-profile"),
    path("register/", register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
