import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from annotation.choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_SUBMITTED,
    APPEAL_TYPE_CHOICES,
    AUTHORITY_ASPECT_CHOICES,
    JKH_TOPIC_CHOICES,
    QUALITY_CHOICES,
    RELEVANCE_CHOICES,
    RESPONSIBLE_PARTY_CHOICES,
    SCORE_KIND_AWARD,
    SARCASM_CHOICES,
    SENTIMENT_CHOICES,
)
from annotation.models import Annotation, ScoreEvent, SourceRecord


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

CHOICES_BY_FIELD = {
    "jkh_relevance": RELEVANCE_CHOICES,
    "jkh_topic": JKH_TOPIC_CHOICES,
    "authority_aspect": AUTHORITY_ASPECT_CHOICES,
    "sentiment": SENTIMENT_CHOICES,
    "appeal_type": APPEAL_TYPE_CHOICES,
    "responsible_party": RESPONSIBLE_PARTY_CHOICES,
    "sarcasm": SARCASM_CHOICES,
    "quality": QUALITY_CHOICES,
}

DEFAULT_DELETED_LABELS = {
    "jkh_relevance": "no",
    "jkh_topic": "not_jkh",
    "authority_aspect": "not_applicable",
    "sentiment": "neutral",
    "appeal_type": "other",
    "responsible_party": "not_applicable",
    "sarcasm": "no",
    "quality": "no_context",
}

FINAL_STATUSES = [ANNOTATION_STATUS_SUBMITTED, ANNOTATION_STATUS_APPROVED]


class Command(BaseCommand):
    help = "Apply offline labels for raw SourceRecord rows as approved annotations."

    def add_arguments(self, parser):
        parser.add_argument("input_path")
        parser.add_argument("--reviewer", required=True)
        parser.add_argument("--student", default="offline_teacher")
        parser.add_argument("--create-student", action="store_true")
        parser.add_argument(
            "--award-points",
            action="store_true",
            help="Create +1 score events for ordinary approved offline labels.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["input_path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        User = get_user_model()
        reviewer = self.get_existing_user(User, options["reviewer"], "reviewer")
        student = self.get_or_create_student(User, options["student"], options["create_student"])

        rows = list(self.read_rows(path))
        results = {"approve": 0, "deleted_confirm": 0, "skip": 0, "score_events": 0, "failed": 0}
        failures = []

        with transaction.atomic():
            for line_number, row in rows:
                try:
                    action = row.get("offline_action", "").strip()
                    if not action or action == "skip":
                        results["skip"] += 1
                        continue
                    if action not in {"approve", "deleted_confirm"}:
                        raise ValueError(f"unknown offline_action={action!r}")
                    record = self.get_record(row)
                    if self.has_final_annotation(record):
                        raise ValueError(f"record {record.id} already has submitted/approved annotation")
                    if Annotation.objects.filter(record=record, student=student).exists():
                        raise ValueError(f"record {record.id} already has annotation from {student.username}")

                    labels = (
                        DEFAULT_DELETED_LABELS.copy()
                        if action == "deleted_confirm"
                        else self.validate_labels(row)
                    )
                    self.validate_consistency(labels)

                    if not options["dry_run"]:
                        now = timezone.now()
                        record.clear_reservation()
                        if action == "deleted_confirm":
                            record.is_active = False
                            record.save(update_fields=["is_active", "reserved_by", "reserved_until"])
                        else:
                            record.save(update_fields=["reserved_by", "reserved_until"])
                        annotation = Annotation.objects.create(
                            record=record,
                            student=student,
                            status=ANNOTATION_STATUS_APPROVED,
                            reviewed_by=reviewer,
                            reviewed_at=now,
                            review_comment=row.get("offline_comment", "").strip() or "Offline verified label.",
                            is_deleted_post_report=(action == "deleted_confirm"),
                            **labels,
                        )
                        if action == "approve" and options["award_points"]:
                            ScoreEvent.objects.create(
                                student=student,
                                annotation=annotation,
                                created_by=reviewer,
                                kind=SCORE_KIND_AWARD,
                                points=1,
                                reason=annotation.review_comment,
                            )
                    if action == "approve" and options["award_points"]:
                        results["score_events"] += 1
                    results[action] += 1
                except Exception as exc:  # noqa: BLE001 - report all row-level validation problems
                    results["failed"] += 1
                    failures.append(f"line {line_number}: {exc}")

            if options["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(f"mode={'dry-run' if options['dry_run'] else 'apply'}")
        self.stdout.write(f"reviewer={reviewer.username}")
        self.stdout.write(f"student={student.username}")
        self.stdout.write(f"rows={len(rows)}")
        self.stdout.write(f"award_points={options['award_points']}")
        for key in ["approve", "deleted_confirm", "skip", "score_events", "failed"]:
            self.stdout.write(f"{key}: {results[key]}")
        if failures:
            self.stdout.write("failures:")
            for item in failures[:30]:
                self.stdout.write(f"  {item}")
            if len(failures) > 30:
                self.stdout.write(f"  ... {len(failures) - 30} more")
        if results["failed"]:
            raise CommandError(f"Failed rows: {results['failed']}")
        if options["dry_run"]:
            self.stdout.write("Dry run only. Re-run without --dry-run to apply labels.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Applied offline labels: {results['approve'] + results['deleted_confirm']}"))

    def get_existing_user(self, User, username, role):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"{role} user not found: {username}") from exc

    def get_or_create_student(self, User, username, create):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            if not create:
                raise CommandError(f"student user not found: {username}") from exc
            user = User.objects.create_user(username=username)
            user.set_unusable_password()
            user.save(update_fields=["password"])
            return user

    def read_rows(self, path):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=2):
                yield index, row

    def get_record(self, row):
        raw_id = row.get("record_id", "").strip()
        if not raw_id:
            raise ValueError("record_id is empty")
        try:
            return SourceRecord.objects.get(id=int(raw_id), is_active=True)
        except (ValueError, SourceRecord.DoesNotExist) as exc:
            raise ValueError(f"active record not found: {raw_id}") from exc

    def has_final_annotation(self, record):
        return Annotation.objects.filter(record=record, status__in=FINAL_STATUSES).exists()

    def validate_labels(self, row):
        labels = {}
        for field in LABEL_FIELDS:
            value = row.get(field, "").strip()
            if not value:
                raise ValueError(f"{field} is empty")
            allowed = {choice_value for choice_value, _label in CHOICES_BY_FIELD[field]}
            if value not in allowed:
                raise ValueError(f"{field}={value!r} is not one of {sorted(allowed)}")
            labels[field] = value
        return labels

    def validate_consistency(self, labels):
        relevance = labels["jkh_relevance"]
        topic = labels["jkh_topic"]
        if relevance == "no" and topic != "not_jkh":
            raise ValueError("jkh_topic must be not_jkh when jkh_relevance is no")
        if relevance == "yes" and topic == "not_jkh":
            raise ValueError("jkh_topic cannot be not_jkh when jkh_relevance is yes")
