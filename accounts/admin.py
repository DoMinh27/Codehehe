from django.contrib import admin

from .models import PlayerActivityDay


@admin.register(PlayerActivityDay)
class PlayerActivityDayAdmin(admin.ModelAdmin):
    list_display = ("user", "activity_date", "first_activity_at")
    list_filter = ("activity_date",)
    search_fields = ("user__username",)
    readonly_fields = ("user", "activity_date", "first_activity_at")
