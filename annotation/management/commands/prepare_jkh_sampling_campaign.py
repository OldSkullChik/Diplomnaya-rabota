import csv
import math
import random
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from annotation.choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_SUBMITTED,
    SAMPLING_POOL_CONTROL,
    SAMPLING_POOL_GENERAL,
    SAMPLING_POOL_JKH_CANDIDATE,
)
from annotation.models import Annotation, AnnotationCampaign, SourceRecord
from annotation.sampling import JKH_CAMPAIGN_KEY, score_jkh_candidate


class Command(BaseCommand):
    help = "Prepare and optionally activate a targeted ЖКХ sampling campaign for unlabelled records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write selected pools and activate the campaign.")
        parser.add_argument("--disable", action="store_true", help="Disable the targeted campaign without deleting marks.")
        parser.add_argument("--ratio", type=int, default=100, help="Number of likely ЖКХ records per control record.")
        parser.add_argument("--threshold", type=int, default=7, help="Minimum heuristic score for a likely ЖКХ candidate.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed used for the control sample.")
        parser.add_argument(
            "--preview-output",
            default="",
            help="Optional CSV path for selected candidate and control records.",
        )
        parser.add_argument("--sample-size", type=int, default=15, help="Number of candidate examples printed.")

    def handle(self, *args, **options):
        if options["apply"] and options["disable"]:
            raise CommandError("--apply and --disable cannot be combined.")
        if options["ratio"] < 1:
            raise CommandError("--ratio must be greater than zero.")
        if options["threshold"] < 1:
            raise CommandError("--threshold must be greater than zero.")

        if options["disable"]:
            campaign, _ = AnnotationCampaign.objects.get_or_create(key=JKH_CAMPAIGN_KEY)
            campaign.is_active = False
            campaign.save(update_fields=["is_active", "updated_at"])
            self.stdout.write(self.style.SUCCESS("Targeted ЖКХ sampling campaign disabled. General queue is active."))
            return

        eligible = self.available_records()
        candidate_records = []
        control_source_ids = []
        eligible_count = 0

        for record in eligible.only("id", "text", "post_text", "source_url").iterator(chunk_size=2000):
            eligible_count += 1
            score, reasons = score_jkh_candidate(record.text, record.post_text)
            if score >= options["threshold"]:
                record.sampling_pool = SAMPLING_POOL_JKH_CANDIDATE
                record.jkh_candidate_score = score
                record.jkh_candidate_reason = "; ".join(reasons)
                candidate_records.append(record)
            else:
                control_source_ids.append(record.id)

        control_count = 0
        control_ids = []
        if candidate_records:
            control_count = min(
                len(control_source_ids),
                math.ceil(len(candidate_records) / options["ratio"]),
            )
            control_ids = random.Random(options["seed"]).sample(control_source_ids, control_count)

        selected_count = len(candidate_records) + control_count
        paused_general_count = eligible_count - selected_count
        self.stdout.write(f"mode={'apply' if options['apply'] else 'dry-run'}")
        self.stdout.write(f"available_unlabelled_records={eligible_count}")
        self.stdout.write(f"likely_jkh_candidates={len(candidate_records)}")
        self.stdout.write("selection_subject=post_context_only")
        self.stdout.write(f"control_records={control_count}")
        self.stdout.write(f"paused_general_records={paused_general_count}")
        self.stdout.write(f"target_candidate_to_control_ratio={options['ratio']}:1")
        self.stdout.write(f"minimum_candidate_score={options['threshold']}")
        self.stdout.write(f"control_random_seed={options['seed']}")

        if options["preview_output"]:
            self.write_preview(Path(options["preview_output"]), candidate_records, control_ids)
            self.stdout.write(f"preview_csv={options['preview_output']}")

        self.print_candidate_sample(candidate_records, options["sample_size"], options["seed"])

        if not options["apply"]:
            self.stdout.write("Dry run only. Inspect the candidate sample/CSV, then re-run with --apply.")
            return

        with transaction.atomic():
            now = timezone.now()
            eligible.update(
                sampling_pool=SAMPLING_POOL_GENERAL,
                jkh_candidate_score=0,
                jkh_candidate_reason="",
                sampling_updated_at=now,
            )
            for record in candidate_records:
                record.sampling_updated_at = now
            SourceRecord.objects.bulk_update(
                candidate_records,
                ["sampling_pool", "jkh_candidate_score", "jkh_candidate_reason", "sampling_updated_at"],
                batch_size=1000,
            )
            SourceRecord.objects.filter(id__in=control_ids).update(
                sampling_pool=SAMPLING_POOL_CONTROL,
                jkh_candidate_score=0,
                jkh_candidate_reason=f"Random control sample, seed={options['seed']}",
                sampling_updated_at=now,
            )
            AnnotationCampaign.objects.update_or_create(
                key=JKH_CAMPAIGN_KEY,
                defaults={
                    "title": "Целевой добор ЖКХ",
                    "is_active": True,
                    "candidate_ratio": options["ratio"],
                    "candidate_count": len(candidate_records),
                    "control_count": control_count,
                    "score_threshold": options["threshold"],
                    "random_seed": options["seed"],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Campaign activated: {len(candidate_records)} likely ЖКХ candidates and "
                f"{control_count} control records are now assignable."
            )
        )

    def available_records(self):
        final_annotation = Annotation.objects.filter(
            record_id=OuterRef("pk"),
            status__in=[ANNOTATION_STATUS_SUBMITTED, ANNOTATION_STATUS_APPROVED],
        )
        return (
            SourceRecord.objects.filter(is_active=True)
            .annotate(has_final_annotation=Exists(final_annotation))
            .filter(has_final_annotation=False)
            .order_by("id")
        )

    def write_preview(self, path, candidates, control_ids):
        path.parent.mkdir(parents=True, exist_ok=True)
        controls = list(
            SourceRecord.objects.filter(id__in=control_ids).only("id", "text", "post_text", "source_url")
        )
        rows = [(SAMPLING_POOL_JKH_CANDIDATE, row) for row in candidates]
        rows.extend((SAMPLING_POOL_CONTROL, row) for row in controls)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "record_id",
                    "sampling_pool",
                    "jkh_candidate_score",
                    "jkh_candidate_reason",
                    "comment_text",
                    "post_text",
                    "source_url",
                ]
            )
            for pool, record in rows:
                writer.writerow(
                    [
                        record.id,
                        pool,
                        record.jkh_candidate_score if pool == SAMPLING_POOL_JKH_CANDIDATE else 0,
                        record.jkh_candidate_reason if pool == SAMPLING_POOL_JKH_CANDIDATE else "Random control sample",
                        record.text,
                        record.post_text,
                        record.source_url,
                    ]
                )

    def print_candidate_sample(self, candidates, sample_size, seed):
        if not candidates or sample_size <= 0:
            return
        sample = random.Random(seed).sample(candidates, min(sample_size, len(candidates)))
        self.stdout.write("candidate_random_sample:")
        for record in sample:
            comment_excerpt = " ".join(record.text.split())[:120]
            post_excerpt = " ".join(record.post_text.split())[:160]
            reason = record.jkh_candidate_reason[:120]
            self.stdout.write(
                f"  id={record.id}; score={record.jkh_candidate_score}; reason={reason}"
            )
            self.stdout.write(f"    post={post_excerpt}")
            self.stdout.write(f"    comment={comment_excerpt}")
