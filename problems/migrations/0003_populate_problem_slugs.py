from django.db import migrations
from django.utils.text import slugify


def populate_problem_slugs(apps, schema_editor):
    problem_model = apps.get_model("problems", "Problem")
    used_slugs = set()

    for problem in problem_model.objects.order_by("pk"):
        base_slug = slugify(problem.title) or f"problem-{problem.pk}"
        base_slug = base_slug[:220]
        slug = base_slug
        suffix = 2

        while slug in used_slugs:
            suffix_text = f"-{suffix}"
            slug = f"{base_slug[: 220 - len(suffix_text)]}{suffix_text}"
            suffix += 1

        problem.slug = slug
        problem.save(update_fields=["slug"])
        used_slugs.add(slug)


def clear_problem_slugs(apps, schema_editor):
    problem_model = apps.get_model("problems", "Problem")
    problem_model.objects.update(slug=None)


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0002_add_problem_slug_nullable"),
    ]

    operations = [
        migrations.RunPython(populate_problem_slugs, clear_problem_slugs),
    ]
