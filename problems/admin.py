from django.contrib import admin

from .models import Problem, TestCase


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "difficulty", "points", "order", "is_active")
    list_filter = ("difficulty", "is_active")
    search_fields = ("title", "slug", "statement")
    ordering = ("order", "id")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (TestCaseInline,)


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ("problem", "order", "is_sample", "created_at")
    list_filter = ("is_sample",)
    search_fields = ("problem__title",)
    ordering = ("problem", "order", "id")
