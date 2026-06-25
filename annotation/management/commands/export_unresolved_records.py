import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from annotation.choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_SUBMITTED,
    SAMPLING_POOL_CHOICES,
    SAMPLING_POOL_JKH_CANDIDATE,
)
from annotation.models import Annotation, SourceRecord


LABEL_FIELDS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]


class Command(BaseCommand):
    help = "Export unresolved source records for offline labeling."

    def add_arguments(self, parser):
        parser.add_argument("output_path")
        parser.add_argument(
            "--pool",
            choices=[value for value, _label in SAMPLING_POOL_CHOICES],
            default=SAMPLING_POOL_JKH_CANDIDATE,
        )
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        path = Path(options["output_path"])
        path.parent.mkdir(parents=True, exist_ok=True)

        final_annotations = Annotation.objects.filter(
            record_id=OuterRef("pk"),
            status__in=[ANNOTATION_STATUS_SUBMITTED, ANNOTATION_STATUS_APPROVED],
        )
        qs = (
            SourceRecord.objects.filter(is_active=True, sampling_pool=options["pool"])
            .annotate(has_final_annotation=Exists(final_annotations))
            .filter(has_final_annotation=False)
            .order_by("-jkh_candidate_score", "id")
        )
        if options["limit"]:
            qs = qs[: options["limit"]]

        fields = [
            "offline_action",
            *LABEL_FIELDS,
            "offline_comment",
            "record_id",
            "source_url",
            "group_name",
            "sampling_pool",
            "jkh_candidate_score",
            "jkh_candidate_reason",
            "comment_text",
            "post_text",
        ]

        count = 0
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for record in qs:
                count += 1
                writer.writerow(
                    {
                        "offline_action": "",
                        **{field: "" for field in LABEL_FIELDS},
                        "offline_comment": "",
                        "record_id": record.id,
                        "source_url": record.source_url,
                        "group_name": record.group_name,
                        "sampling_pool": record.sampling_pool,
                        "jkh_candidate_score": record.jkh_candidate_score,
                        "jkh_candidate_reason": record.jkh_candidate_reason,
                        "comment_text": record.text,
                        "post_text": record.post_text,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Exported {count} unresolved records to {path}"))
