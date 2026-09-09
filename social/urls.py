from django.urls import path

from social import views

app_name = "social"

urlpatterns = [
    path("notifications/state/", views.notification_state, name="notification-state"),
]
