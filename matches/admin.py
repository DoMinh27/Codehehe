from django.contrib import admin

from .models import Match, MatchPlayer, MatchProblem, PlayerProblemProgress, Submission


class MatchPlayerInline(admin.TabularInline):
    model = MatchPlayer
    extra = 0


class MatchProblemInline(admin.TabularInline):
    model = MatchProblem
    extra = 0


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("room_code", "host", "status", "is_draw", "winner", "created_at")
    list_filter = ("status", "is_draw")
    search_fields = ("room_code", "host__username", "winner__username")
    readonly_fields = ("created_at", "updated_at")
    inlines = (MatchPlayerInline, MatchProblemInline)


@admin.register(MatchPlayer)
class MatchPlayerAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "user",
        "slot",
        "score",
        "is_host",
        "is_active",
        "joined_at",
    )
    list_filter = ("is_host", "is_active")
    search_fields = ("match__room_code", "user__username")


@admin.register(MatchProblem)
class MatchProblemAdmin(admin.ModelAdmin):
    list_display = ("match", "order", "title_snapshot", "points", "first_solver")
    search_fields = ("match__room_code", "title_snapshot", "problem__title")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "player", "match_problem", "verdict", "received_at")
    list_filter = ("verdict", "language", "is_score_processed")
    search_fields = ("match__room_code", "player__user__username")
    readonly_fields = ("received_at", "completed_at")


@admin.register(PlayerProblemProgress)
class PlayerProblemProgressAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "player",
        "match_problem",
        "is_solved",
        "base_points_awarded",
        "first_solve_bonus_awarded",
    )
    list_filter = ("is_solved",)
    search_fields = ("match__room_code", "player__user__username")
