from django.urls import path

from social import views

app_name = "social"

urlpatterns = [
    path("notifications/state/", views.notification_state, name="notification-state"),
    path("friends/", views.friends, name="friends"),
    path("friends/state/", views.friends_state, name="friends-state"),
    path("friends/requests/", views.friend_request_send, name="friend-request-send"),
    path("friends/requests/<uuid:request_id>/action/", views.friend_request_action, name="friend-request-action"),
    path("match-invitations/", views.match_invitation_send, name="match-invitation-send"),
    path(
        "match-invitations/<uuid:invitation_id>/action/",
        views.match_invitation_action,
        name="match-invitation-action",
    ),
    path("friends/<int:user_id>/remove/", views.friendship_remove, name="friend-remove"),
    path("friends/<int:user_id>/block/", views.user_block, name="user-block"),
    path("friends/<int:user_id>/unblock/", views.user_unblock, name="user-unblock"),
    path("presence/heartbeat/", views.presence_heartbeat, name="presence-heartbeat"),
    path("presence/privacy/", views.presence_privacy, name="presence-privacy"),
]
