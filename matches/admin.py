from django.contrib import admin

from .models import (
    Match,
    MatchPlayer,
    MatchPlayerSkill,
    MatchProblem,
    MatchSkill,
    PlayerProblemProgress,
    Skill,
    SkillEffect,
    SkillUse,
    Submission,
    TypingChallenge,
)


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
        "energy",
        "time_penalty_seconds",
        "is_host",
        "is_active",
        "joined_at",
    )
    list_filter = ("is_host", "is_active")
    search_fields = ("match__room_code", "user__username")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "energy_cost",
        "duration_seconds",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.append("code")
        return fields


@admin.register(MatchSkill)
class MatchSkillAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "code_snapshot",
        "energy_cost_snapshot",
        "duration_seconds_snapshot",
    )
    search_fields = ("match__room_code", "code_snapshot", "name_snapshot")
    readonly_fields = (
        "match",
        "skill",
        "code_snapshot",
        "name_snapshot",
        "description_snapshot",
        "energy_cost_snapshot",
        "duration_seconds_snapshot",
        "created_at",
    )


@admin.register(MatchPlayerSkill)
class MatchPlayerSkillAdmin(admin.ModelAdmin):
    list_display = ("player", "match_skill", "quantity", "used_count")
    search_fields = (
        "player__user__username",
        "player__match__room_code",
        "match_skill__code_snapshot",
    )


@admin.register(SkillUse)
class SkillUseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match",
        "source_player",
        "target_player",
        "match_skill",
        "energy_spent",
        "used_at",
    )
    search_fields = (
        "match__room_code",
        "source_player__user__username",
        "target_player__user__username",
        "match_skill__code_snapshot",
    )
    readonly_fields = (
        "match",
        "source_player",
        "target_player",
        "match_skill",
        "energy_spent",
        "idempotency_key",
        "used_at",
    )


@admin.register(SkillEffect)
class SkillEffectAdmin(admin.ModelAdmin):
    list_display = ("skill_use", "started_at", "expires_at", "cancelled_at")
    readonly_fields = ("skill_use", "started_at", "expires_at")


@admin.register(TypingChallenge)
class TypingChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "effect",
        "started_at",
        "expires_at",
        "completed_at",
    )
    search_fields = (
        "effect__skill_use__source_player__user__username",
        "effect__skill_use__target_player__user__username",
        "prompt",
    )
    readonly_fields = (
        "effect",
        "prompt",
        "started_at",
        "expires_at",
        "completed_at",
    )


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
        "energy_awarded",
        "skill_awarded",
    )
    list_filter = ("is_solved",)
    search_fields = ("match__room_code", "player__user__username")
