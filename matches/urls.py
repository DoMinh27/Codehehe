from django.urls import path

from . import views

urlpatterns = [
    path("rooms/create/", views.create_room, name="room-create"),
    path("rooms/join/", views.join_room, name="room-join"),
    path("rooms/<str:room_code>/", views.waiting_room, name="waiting-room"),
    path(
        "rooms/<str:room_code>/state/",
        views.waiting_room_state,
        name="waiting-room-state",
    ),
    path("<int:match_id>/start/", views.start_match, name="match-start"),
    path("<int:match_id>/battle/", views.battle, name="battle"),
    path("<int:match_id>/state/", views.match_state, name="match-state"),
    path("<int:match_id>/finalize/", views.finalize_match, name="match-finalize"),
    path("<int:match_id>/result/", views.match_result, name="match-result"),
    path(
        "<int:match_id>/problems/<int:match_problem_id>/submissions/",
        views.submit_submission,
        name="submission-create",
    ),
]
