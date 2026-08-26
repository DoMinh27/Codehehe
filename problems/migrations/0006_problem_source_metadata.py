from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0005_problem_reference_solution"),
    ]

    operations = [
        migrations.AddField(
            model_name="problem",
            name="primary_topic",
            field=models.CharField(
                choices=[
                    ("OTHER", "Khác"),
                    ("BASICS", "Python cơ bản"),
                    ("ARITHMETIC", "Số học"),
                    ("STRINGS", "Chuỗi"),
                    ("LISTS", "Danh sách"),
                    ("HASHING", "Bảng băm"),
                    ("SEARCH", "Tìm kiếm"),
                    ("SIMULATION", "Mô phỏng"),
                    ("MATRIX", "Ma trận"),
                    ("STACK", "Ngăn xếp"),
                    ("DYNAMIC_PROGRAMMING", "Quy hoạch động"),
                ],
                db_index=True,
                default="OTHER",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="problem",
            name="source_license",
            field=models.CharField(
                default="CodeHehe original",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="problem",
            name="source_name",
            field=models.CharField(default="CodeHehe", max_length=100),
        ),
        migrations.AddField(
            model_name="problem",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("ORIGINAL", "CodeHehe tự xây"),
                    ("ADAPTED", "Chuyển thể"),
                ],
                db_index=True,
                default="ORIGINAL",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="problem",
            name="source_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
