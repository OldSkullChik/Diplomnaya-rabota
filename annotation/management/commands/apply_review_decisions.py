import csv
from collections import Counter
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from annotation.models import Annotation
from annotation.views import apply_review_action


ACTION_ALIASES = {
    "approve": "approve",
    "accept": "approve",
    "yes": "approve",
    "ok": "approve",
    "+": "approve",
    "принять": "approve",
    "да": "approve",
    "reject": "reject",
    "decline": "reject",
    "no": "reject",
    "-": "reject",
    "брак": "reject",
    "отклонить": "reject",
    "нет": "reject",
    "deleted_confirm": "deleted_confirm",
    "deleted_yes": "deleted_confirm",
    "deleted_ok": "deleted_confirm",
    "post_deleted_yes": "deleted_confirm",
    "удален_да": "deleted_confirm",
    "deleted_reject": "deleted_reject",
    "deleted_no": "deleted_reject",
    "post_deleted_no": "deleted_reject",
    "удален_нет": "deleted_reject",
    "skip": "skip",
    "": "skip",
}


class Command(BaseCommand):
    help = "Apply review decisions from a CSV exported by export_pending_annotations."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument(
            "--reviewer",
            default="oldskull",
            help="Username recorded as the reviewer. Default: oldskull.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and summarize decisions without applying them.",
        )

    def handle(self, *args, **options):
        path = Path(options["csv_path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        reviewer = self.get_reviewer(options["reviewer"])
        counters = Counter()
        decisions = []

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise CommandError(f"CSV header is missing: {path}")
            required = {"annotation_id", "review_action"}
            missing = required - set(reader.fieldnames)
            if missing:
                raise CommandError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

            for row_number, row in enumerate(reader, start=2):
                annotation_id = (row.get("annotation_id") or "").strip()
                if not annotation_id:
                    counters["skipped_missing_id"] += 1
                    continue
                action = self.normalize_action(row.get("review_action"))
                if action == "skip":
                    counters["skipped_blank"] += 1
                    continue
                decisions.append((row_number, int(annotation_id), action, row.get("review_comment", "").strip()))
                counters[action] += 1

        self.stdout.write(f"mode={'dry-run' if options['dry_run'] else 'apply'}")
        self.stdout.write(f"reviewer={reviewer.username}")
        self.stdout.write(f"decisions={len(decisions)}")
        for action, count in counters.items():
            self.stdout.write(f"{action}: {count}")

        if not decisions:
            return
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run only. Re-run without --dry-run to apply decisions."))
            return

        applied = 0
        failed = 0
        with transaction.atomic():
            for row_number, annotation_id, action, comment in decisions:
                try:
                    annotation = Annotation.objects.select_related("record", "student").get(id=annotation_id)
                except Annotation.DoesNotExist:
                    failed += 1
                    self.stderr.write(f"row {row_number}: annotation not found: {annotation_id}")
                    continue
                success, message = apply_review_action(annotation, reviewer, action, comment)
                if success:
                    applied += 1
                else:
                    failed += 1
                    self.stderr.write(f"row {row_number}: {annotation_id}: {message}")

        self.stdout.write(self.style.SUCCESS(f"Applied: {applied}; failed: {failed}"))

    def get_reviewer(self, username):
        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"Reviewer user does not exist: {username}") from exc

    def normalize_action(self, value):
        action = (value or "").strip().lower()
        try:
            return ACTION_ALIASES[action]
        except KeyError as exc:
            raise CommandError(f"Unknown review_action: {value!r}") from exc
