from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone

from .models import AccountEmail, PendingRegistration, PlayerActivityDay


@admin.register(PlayerActivityDay)
class PlayerActivityDayAdmin(admin.ModelAdmin):
    list_display = ("user", "activity_date", "first_activity_at")
    list_filter = ("activity_date",)
    search_fields = ("user__username",)
    readonly_fields = ("user", "activity_date", "first_activity_at")


@admin.register(AccountEmail)
class AccountEmailAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "verified", "verified_at", "updated_at")
    list_filter = ("verified_at",)
    search_fields = ("email", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("verified_at", "created_at", "updated_at")

    @admin.display(boolean=True, description="Đã xác minh")
    def verified(self, obj):
        return obj.is_verified

    def save_model(self, request, obj, form, change):
        obj.email = AccountEmail.normalize(obj.email)
        obj.verified_at = timezone.now()
        super().save_model(request, obj, form, change)
        user = obj.user
        user.email = obj.email
        user.is_active = True
        user.save(update_fields=["email", "is_active"])

    def delete_model(self, request, obj):
        user = obj.user
        super().delete_model(request, obj)
        user.email = ""
        user.save(update_fields=["email"])

    def delete_queryset(self, request, queryset):
        user_ids = list(queryset.values_list("user_id", flat=True))
        super().delete_queryset(request, queryset)
        User.objects.filter(pk__in=user_ids).update(email="")


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "created_at", "expires_at", "retained_until")
    search_fields = ("username", "email")
    readonly_fields = ("id", "username", "email", "created_at", "expires_at", "retained_until")
    fields = readonly_fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer("password_hash", "token_nonce")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.unregister(User)


@admin.register(User)
class CodeHeheUserAdmin(UserAdmin):
    readonly_fields = (*UserAdmin.readonly_fields, "email")
