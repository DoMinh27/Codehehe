from django.urls import path

from . import views

urlpatterns = [
    path("", views.problem_list, name="problem-list"),
    path("<slug:slug>/", views.problem_detail, name="problem-detail"),
]
