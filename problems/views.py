from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import Problem, TestCase


@login_required
def problem_list(request):
    problems = Problem.objects.filter(is_active=True)
    return render(request, "problems/problem_list.html", {"problems": problems})


@login_required
def problem_detail(request, slug):
    sample_tests = TestCase.objects.filter(is_sample=True)
    problem = get_object_or_404(
        Problem.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                "test_cases",
                queryset=sample_tests,
                to_attr="sample_tests",
            )
        ),
        slug=slug,
    )
    return render(request, "problems/problem_detail.html", {"problem": problem})
