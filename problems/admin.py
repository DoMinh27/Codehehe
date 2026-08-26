from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.forms.models import BaseInlineFormSet

from .models import Problem, TestCase


class ProblemAdminForm(ModelForm):
    class Meta:
        model = Problem
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("is_active")
            and not cleaned_data.get("reference_solution", "").strip()
        ):
            self.add_error(
                "reference_solution",
                "Bài đang hoạt động phải có lời giải chuẩn.",
            )
        if cleaned_data.get("source_type") == Problem.SourceType.ADAPTED:
            for field_name, message in (
                ("source_name", "Bài chuyển thể phải ghi tên nguồn."),
                ("source_url", "Bài chuyển thể phải có URL nguồn."),
                ("source_license", "Bài chuyển thể phải ghi giấy phép."),
            ):
                value = cleaned_data.get(field_name, "")
                if not str(value).strip():
                    self.add_error(field_name, message)
        return cleaned_data


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
    form = ProblemAdminForm
    list_display = (
        "title",
        "slug",
        "difficulty",
        "primary_topic",
        "source_type",
        "source_license",
        "points",
        "order",
        "is_active",
    )
    list_filter = (
        "difficulty",
        "primary_topic",
        "source_type",
        "source_license",
        "is_active",
    )
    search_fields = ("title", "slug", "statement", "source_name", "source_url")
    ordering = ("order", "id")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (TestCaseInline,)


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ("problem", "order", "is_sample", "created_at")
    list_filter = ("is_sample",)
    search_fields = ("problem__title",)
    ordering = ("problem", "order", "id")
