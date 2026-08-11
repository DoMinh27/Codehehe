from django.contrib import admin
from django.urls import path

from . import views


app_name = "operations"

urlpatterns = [
    path("", admin.site.admin_view(views.dashboard), name="dashboard"),
    path(
        "state/",
        admin.site.admin_view(views.dashboard_state),
        name="dashboard_state",
    ),
]
