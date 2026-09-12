from django.contrib import admin

from social.models import (
    DirectMatchInvitation,
    FriendRequest,
    Friendship,
    UserBlock,
    UserPresence,
)


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FriendRequest)
class FriendRequestAdmin(ReadOnlyAuditAdmin):
    list_display = ("id", "requester", "user_low", "user_high", "status", "expires_at")
    list_filter = ("status", "created_at", "expires_at")
    search_fields = ("requester__username", "user_low__username", "user_high__username")
    list_select_related = ("requester", "user_low", "user_high")


@admin.register(Friendship)
class FriendshipAdmin(ReadOnlyAuditAdmin):
    list_display = ("id", "user_low", "user_high", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user_low__username", "user_high__username")
    list_select_related = ("user_low", "user_high")


@admin.register(UserBlock)
class UserBlockAdmin(ReadOnlyAuditAdmin):
    list_display = ("id", "blocker", "blocked", "created_at")
    list_filter = ("created_at",)
    search_fields = ("blocker__username", "blocked__username")
    list_select_related = ("blocker", "blocked")


@admin.register(UserPresence)
class UserPresenceAdmin(ReadOnlyAuditAdmin):
    list_display = ("user", "last_seen_at", "show_presence_to_friends", "updated_at")
    list_filter = ("show_presence_to_friends", "last_seen_at")
    search_fields = ("user__username",)
    list_select_related = ("user",)


@admin.register(DirectMatchInvitation)
class DirectMatchInvitationAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "id",
        "inviter",
        "invitee",
        "status",
        "expires_at",
        "new_match",
    )
    list_filter = ("status", "created_at", "expires_at")
    search_fields = (
        "inviter__username",
        "invitee__username",
        "new_match__room_code",
    )
    list_select_related = ("inviter", "invitee", "new_match")
