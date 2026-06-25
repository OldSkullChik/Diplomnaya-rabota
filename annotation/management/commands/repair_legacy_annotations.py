from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from annotation.choices import ANNOTATION_STATUS_APPROVED, ANNOTATION_STATUS_SUBMITTED, SCORE_KIND_AWARD
from annotation.models import Annotation, ScoreEvent


LEGACY_NON_JKH_FIX = {
    "jkh_topic": "not_jkh",
    "authority_aspect": "not_applicable",
    "responsible_party": "not_applicable",
}

DEFAULT_REVIEW_COMMENT = (
    "Автопринято: запись была размечена до обновления правил. "
    "Для ответа 'не относится к ЖКХ' зависимые поля нормализованы без штрафа студенту."
)


class Command(BaseCommand):
    help = "Normalize and approve legacy submitted annotations invalidated by newer non-JKH rules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reviewer",
            default="oldskull",
            help="Username recorded as the reviewer and score-event creator. Default: oldskull.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes. Without this flag the command only prints a dry-run report.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional maximum number of annotations to process.",
        )

    def handle(self, *args, **options):
        reviewer = self.get_reviewer(options["reviewer"])
        qs = self.get_queryset().select_related("student", "record").order_by("submitted_at", "id")
        if options["limit"]:
            qs = qs[: options["limit"]]

        items = list(qs)
        self.stdout.write(f"mode={'apply' if options['apply'] else 'dry-run'}")
        self.stdout.write(f"reviewer={reviewer.username}")
        self.stdout.write(f"legacy_annotations={len(items)}")

        if not items:
            return

        by_student = Counter(item.student.username for item in items)
        self.stdout.write("by_student:")
        for username, count in by_student.most_common():
            self.stdout.write(f"  {username}: {count}")

        self.stdout.write("annotation_ids:")
        self.stdout.write("  " + ", ".join(str(item.id) for item in items[:100]))
        if len(items) > 100:
            self.stdout.write(f"  ... and {len(items) - 100} more")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run only. Re-run with --apply to write changes."))
            return

        now = timezone.now()
        with transaction.atomic():
            for annotation in items:
                for field, value in LEGACY_NON_JKH_FIX.items():
                    setattr(annotation, field, value)
                annotation.status = ANNOTATION_STATUS_APPROVED
                annotation.reviewed_by = reviewer
                annotation.reviewed_at = now
                annotation.review_comment = DEFAULT_REVIEW_COMMENT
                annotation.record.clear_reservation()
                annotation.record.save(update_fields=["reserved_by", "reserved_until"])
                annotation.save(
                    update_fields=[
                        "jkh_topic",
                        "authority_aspect",
                        "responsible_party",
                        "status",
                        "reviewed_by",
                        "reviewed_at",
                        "review_comment",
                        "updated_at",
                    ]
                )
                ScoreEvent.objects.create(
                    student=annotation.student,
                    annotation=annotation,
                    created_by=reviewer,
                    kind=SCORE_KIND_AWARD,
                    points=1,
                    reason=DEFAULT_REVIEW_COMMENT,
                )

        self.stdout.write(self.style.SUCCESS(f"Applied: {len(items)} annotations approved and awarded +1."))

    def get_reviewer(self, username):
        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"Reviewer user does not exist: {username}") from exc

    def get_queryset(self):
        mismatch = Q()
        for field, expected_value in LEGACY_NON_JKH_FIX.items():
            mismatch |= ~Q(**{field: expected_value})
        return Annotation.objects.filter(
            mismatch,
            status=ANNOTATION_STATUS_SUBMITTED,
            is_deleted_post_report=False,
            jkh_relevance="no",
        )
