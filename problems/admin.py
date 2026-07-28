from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Problem, TestCase


class TestCaseInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors) or not self.instance.is_active:
            return
        has_hidden_test = any(
            form.cleaned_data
            and not form.cleaned_data.get("DELETE", False)
            and not form.cleaned_data.get("is_sample", False)
            for form in self.forms
        )
        if not has_hidden_test:
            raise ValidationError(
                "Bài đang hoạt động phải có ít nhất một hidden test."
            )


class TestCaseInline(admin.TabularInline):
    model = TestCase
    formset = TestCaseInlineFormSet
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
