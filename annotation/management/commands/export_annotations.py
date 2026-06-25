import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from annotation.choices import ANNOTATION_STATUS_APPROVED
from annotation.models import Annotation


class Command(BaseCommand):
    help = "Export reviewed annotations to CSV."

    def add_arguments(self, parser):
        parser.add_argument("output_path")
        parser.add_argument("--all", action="store_true", help="Export all annotations, not only approved ones.")

    def handle(self, *args, **options):
        path = Path(options["output_path"])
        path.parent.mkdir(parents=True, exist_ok=True)

        qs = Annotation.objects.select_related("record", "student", "reviewed_by").order_by("id")
        if not options["all"]:
            qs = qs.filter(status=ANNOTATION_STATUS_APPROVED)

        fields = [
            "annotation_id",
            "record_id",
            "student",
            "status",
            "text",
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
            "review_comment",
            "reviewed_by",
        ]

        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for item in qs:
                writer.writerow(
                    {
                        "annotation_id": item.id,
                        "record_id": item.record_id,
                        "student": item.student.username,
                        "status": item.status,
                        "text": item.record.text,
                        "post_text": item.record.post_text,
                        "jkh_relevance": item.jkh_relevance,
                        "jkh_topic": item.jkh_topic,
                        "authority_aspect": item.authority_aspect,
                        "sentiment": item.sentiment,
                        "appeal_type": item.appeal_type,
                        "responsible_party": item.responsible_party,
                        "sarcasm": item.sarcasm,
                        "quality": item.quality,
                        "student_comment": item.student_comment,
                        "review_comment": item.review_comment,
                        "reviewed_by": item.reviewed_by.username if item.reviewed_by else "",
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Exported {qs.count()} annotations to {path}"))

