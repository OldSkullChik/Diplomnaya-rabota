from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("annotation", "0003_annotation_is_deleted_post_report_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnnotationCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(default="jkh_enrichment", max_length=60, unique=True)),
                ("title", models.CharField(default="Целевой добор ЖКХ", max_length=160)),
                ("is_active", models.BooleanField(default=False)),
                ("candidate_ratio", models.PositiveIntegerField(default=100)),
                ("candidate_count", models.PositiveIntegerField(default=0)),
                ("control_count", models.PositiveIntegerField(default=0)),
                ("score_threshold", models.PositiveSmallIntegerField(default=7)),
                ("random_seed", models.PositiveIntegerField(default=42)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["key"],
            },
        ),
        migrations.AddField(
            model_name="sourcerecord",
            name="jkh_candidate_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="sourcerecord",
            name="jkh_candidate_score",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="sourcerecord",
            name="sampling_pool",
            field=models.CharField(
                choices=[
                    ("general", "Общий пул"),
                    ("jkh_candidate", "Кандидат ЖКХ"),
                    ("control", "Контрольная выборка"),
                ],
                db_index=True,
                default="general",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="sourcerecord",
            name="sampling_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
