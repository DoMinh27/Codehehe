from django.urls import path

from .views import battle, reviews, rooms, skills, submissions

urlpatterns = [
    path("active/state/", rooms.active_match_state, name="active-match-state"),
    path("rooms/create/", rooms.create_room, name="room-create"),
    path("rooms/join/", rooms.join_room, name="room-join"),
    path("rooms/<str:room_code>/", rooms.waiting_room, name="waiting-room"),
    path(
        "rooms/<str:room_code>/leave/",
        rooms.leave_room,
        name="room-leave",
    ),
    path(
        "rooms/<str:room_code>/state/",
        rooms.waiting_room_state,
        name="waiting-room-state",
    ),
    path("<int:match_id>/start/", battle.start_match, name="match-start"),
    path("<int:match_id>/battle/", battle.battle, name="battle"),
    path("<int:match_id>/state/", battle.match_state, name="match-state"),
    path(
        "<int:match_id>/skills/<str:skill_code>/use/",
        skills.use_skill,
        name="skill-use",
    ),
    path(
        "<int:match_id>/typing-challenges/<int:challenge_id>/complete/",
        skills.complete_typing_challenge,
        name="typing-challenge-complete",
    ),
    path(
        "<int:match_id>/finalize/",
        battle.finalize_match,
        name="match-finalize",
    ),
    path(
        "<int:match_id>/surrender/",
        battle.surrender_match,
        name="match-surrender",
    ),
    path("<int:match_id>/result/", battle.match_result, name="match-result"),
    path(
        "<int:match_id>/ai-reviews/state/",
        reviews.ai_review_state,
        name="match-ai-review-state",
    ),
    path(
        "<int:match_id>/problems/<int:match_problem_id>/ai-review/",
        reviews.request_ai_review,
        name="match-ai-review-request",
    ),
    path(
        "<int:match_id>/problems/<int:match_problem_id>/run/",
        submissions.run_code,
        name="code-run",
    ),
    path(
        "<int:match_id>/problems/<int:match_problem_id>/submissions/",
        submissions.submit_submission,
        name="submission-create",
    ),
]
