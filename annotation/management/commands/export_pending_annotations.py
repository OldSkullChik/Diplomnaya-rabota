import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from annotation.choices import ANNOTATION_STATUS_SUBMITTED
from annotation.models import Annotation


class Command(BaseCommand):
    help = "Export submitted annotations for offline review."

    def add_arguments(self, parser):
        parser.add_argument("output_path")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        path = Path(options["output_path"])
        path.parent.mkdir(parents=True, exist_ok=True)

        qs = (
            Annotation.objects.filter(status=ANNOTATION_STATUS_SUBMITTED)
            .select_related("record", "student")
            .order_by("submitted_at", "id")
        )
        if options["limit"]:
            qs = qs[: options["limit"]]

        fields = [
            "review_action",
            "review_comment",
            "annotation_id",
            "student",
            "student_name",
            "submitted_at",
            "record_id",
            "source_url",
            "group_name",
            "is_deleted_post_report",
            "comment_text",
            "post_text",
            "jkh_relevance",
            "jkh_topic",
            "authority_aspect",
            "sentiment",
            "appeal_type",
            "responsible_party",
            "sarcasm",
            "quality",
            "student_comment",
        ]

        count = 0
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for item in qs:
                count += 1
                writer.writerow(
                    {
                        "review_action": "",
                        "review_comment": "",
                        "annotation_id": item.id,
                        "student": item.student.username,
                        "student_name": item.student.get_full_name(),
                        "submitted_at": item.submitted_at.isoformat(),
                        "record_id": item.record_id,
                        "source_url": item.record.source_url,
                        "group_name": item.record.group_name,
                        "is_deleted_post_report": item.is_deleted_post_report,
                        "comment_text": item.record.text,
                        "post_text": item.record.post_text,
                        "jkh_relevance": item.get_jkh_relevance_display(),
                        "jkh_topic": item.get_jkh_topic_display(),
                        "authority_aspect": item.get_authority_aspect_display(),
                        "sentiment": item.get_sentiment_display(),
                        "appeal_type": item.get_appeal_type_display(),
                        "responsible_party": item.get_responsible_party_display(),
                        "sarcasm": item.get_sarcasm_display(),
                        "quality": item.get_quality_display(),
                        "student_comment": item.student_comment,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Exported {count} pending annotations to {path}"))
