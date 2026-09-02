from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    AIReviewProviderThrottle,
    Match,
    MatchEvent,
    MatchPlayer,
    MatchPlayerSkill,
    MatchProblem,
    MatchSkill,
    PlayerProblemProgress,
    RematchRequest,
    Skill,
    SkillEffect,
    SkillUse,
    Submission,
    SubmissionAIReview,
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
    list_display = (
        "room_code",
        "host",
        "status",
        "ai_review_enabled",
        "ruleset_version",
        "is_draw",
        "winner",
        "created_at",
    )
    list_filter = ("status", "is_draw")
    search_fields = ("room_code", "host__username", "winner__username")
    readonly_fields = (
        "ruleset_version",
        "rules_snapshot",
        "ai_review_enabled",
        "created_at",
        "updated_at",
        "timeline_version",
        "timeline_link",
    )
    inlines = (MatchPlayerInline, MatchProblemInline)

    @admin.display(description="Diễn biến")
    def timeline_link(self, obj):
        if not obj.pk:
            return "—"
        return format_html(
            '<a href="{}?match__id__exact={}">Xem sự kiện trận</a>',
            reverse("admin:matches_matchevent_changelist"),
            obj.pk,
        )


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MatchEvent)
class MatchEventAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "id",
        "match",
        "kind",
        "actor_name_snapshot",
        "target_name_snapshot",
        "recorded_at",
    )
    list_filter = ("kind",)
    search_fields = ("match__room_code", "actor_name_snapshot", "target_name_snapshot")
    list_select_related = ("match",)
    ordering = ("-id",)


@admin.register(RematchRequest)
class RematchRequestAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "id",
        "match",
        "requester",
        "recipient",
        "current_status",
        "expires_at",
        "new_match",
    )
    list_select_related = ("match", "requester", "recipient", "new_match")
    search_fields = ("match__room_code", "requester__username", "recipient__username")

    @admin.display(description="Trạng thái")
    def current_status(self, obj):
        status = obj.effective_status()
        return "Đã hết hạn" if status == "EXPIRED" else obj.get_status_display()


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
        "policy_snapshot",
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
        "outcome_snapshot",
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
        "outcome_snapshot",
        "used_at",
    )


@admin.register(SkillEffect)
class SkillEffectAdmin(admin.ModelAdmin):
    list_display = (
        "skill_use",
        "started_at",
        "expires_at",
        "cancelled_at",
        "consumed_at",
    )
    readonly_fields = (
        "skill_use",
        "started_at",
        "expires_at",
        "cancelled_at",
        "consumed_at",
    )


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


@admin.register(SubmissionAIReview)
class SubmissionAIReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "submission",
        "progress",
        "status",
        "provider",
        "model",
        "attempt_count",
        "manual_retry_count",
        "failure_retryable",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "provider", "model", "prompt_version")
    search_fields = (
        "submission__match__room_code",
        "submission__player__user__username",
    )
    readonly_fields = (
        "submission",
        "progress",
        "prompt_version",
        "status",
        "provider",
        "model",
        "result",
        "attempt_count",
        "manual_retry_count",
        "failure_retryable",
        "next_attempt_at",
        "processing_started_at",
        "completed_at",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "error_code",
        "created_at",
        "updated_at",
    )


@admin.register(AIReviewProviderThrottle)
class AIReviewProviderThrottleAdmin(admin.ModelAdmin):
    list_display = ("provider", "next_allowed_at", "updated_at")
    readonly_fields = ("provider", "next_allowed_at", "updated_at")


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
