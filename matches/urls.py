from django.urls import path

from . import views

urlpatterns = [
    path(
        "<int:match_id>/problems/<int:match_problem_id>/submissions/",
        views.submit_submission,
        name="submission-create",
    ),
]
