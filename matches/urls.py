from django.urls import path

from . import views

urlpatterns = [
    path("active/state/", views.active_match_state, name="active-match-state"),
    path("rooms/create/", views.create_room, name="room-create"),
    path("rooms/join/", views.join_room, name="room-join"),
    path("rooms/<str:room_code>/", views.waiting_room, name="waiting-room"),
    path(
        "rooms/<str:room_code>/leave/",
        views.leave_room,
        name="room-leave",
    ),
    path(
        "rooms/<str:room_code>/state/",
        views.waiting_room_state,
        name="waiting-room-state",
    ),
    path("<int:match_id>/start/", views.start_match, name="match-start"),
    path("<int:match_id>/battle/", views.battle, name="battle"),
    path("<int:match_id>/state/", views.match_state, name="match-state"),
    path(
        "<int:match_id>/skills/<str:skill_code>/use/",
        views.use_skill,
        name="skill-use",
    ),
    path("<int:match_id>/finalize/", views.finalize_match, name="match-finalize"),
    path("<int:match_id>/surrender/", views.surrender_match, name="match-surrender"),
    path("<int:match_id>/result/", views.match_result, name="match-result"),
    path(
        "<int:match_id>/problems/<int:match_problem_id>/run/",
        views.run_code,
        name="code-run",
    ),
    path(
        "<int:match_id>/problems/<int:match_problem_id>/submissions/",
        views.submit_submission,
        name="submission-create",
    ),
]
