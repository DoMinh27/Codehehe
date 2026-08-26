from django.db import models


class Problem(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    class PrimaryTopic(models.TextChoices):
        OTHER = "OTHER", "Khác"
        BASICS = "BASICS", "Python cơ bản"
        ARITHMETIC = "ARITHMETIC", "Số học"
        STRINGS = "STRINGS", "Chuỗi"
        LISTS = "LISTS", "Danh sách"
        HASHING = "HASHING", "Bảng băm"
        SEARCH = "SEARCH", "Tìm kiếm"
        SIMULATION = "SIMULATION", "Mô phỏng"
        MATRIX = "MATRIX", "Ma trận"
        STACK = "STACK", "Ngăn xếp"
        DYNAMIC_PROGRAMMING = "DYNAMIC_PROGRAMMING", "Quy hoạch động"

    class SourceType(models.TextChoices):
        ORIGINAL = "ORIGINAL", "CodeHehe tự xây"
        ADAPTED = "ADAPTED", "Chuyển thể"

    slug = models.SlugField(max_length=220, unique=True)
    title = models.CharField(max_length=200)
    statement = models.TextField()
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        db_index=True,
    )
    points = models.PositiveIntegerField()
    starter_code = models.TextField(blank=True)
    reference_solution = models.TextField(blank=True)
    primary_topic = models.CharField(
        max_length=30,
        choices=PrimaryTopic.choices,
        default=PrimaryTopic.OTHER,
        db_index=True,
    )
    source_type = models.CharField(
        max_length=10,
        choices=SourceType.choices,
        default=SourceType.ORIGINAL,
        db_index=True,
    )
    source_name = models.CharField(max_length=100, default="CodeHehe")
    source_url = models.URLField(max_length=500, blank=True)
    source_license = models.CharField(
        max_length=100,
        default="CodeHehe original",
    )
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(points__gte=1),
                name="problem_points_gte_1",
            ),
        ]

    def __str__(self):
        return self.title


class TestCase(models.Model):
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    input_data = models.TextField(blank=True)
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(
                fields=["problem", "is_sample", "order"],
                name="testcase_lookup_idx",
            ),
        ]

    def __str__(self):
        visibility = "sample" if self.is_sample else "hidden"
        return f"{self.problem.title} - {visibility} #{self.order}"
