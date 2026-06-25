import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from annotation.csv_utils import first_value, sniff_dialect
from annotation.models import SourceRecord


TEXT_FIELDS = [
    "text",
    "comment",
    "comment_text",
    "Текст комментария",
    "ТЕКСТ",
    "post_text",
]

POST_TEXT_FIELDS = [
    "post_text",
    "Текст поста",
    "ТЕКСТ ПОСТА",
]

SOURCE_URL_FIELDS = [
    "comment_url",
    "post_url",
    "Ссылка на комментарий",
    "ССЫЛКА НА ПОСТ",
    "Ссылка на пост",
]

GROUP_NAME_FIELDS = [
    "group_name",
    "НАЗВАНИЕ ВЛАДЕЛЬЦА",
    "НАЗВАНИЕ ИСТОЧНИКА",
]

EXTERNAL_ID_FIELDS = [
    "comment_url",
    "Ссылка на комментарий",
    "comment_id",
    "post_url",
    "ССЫЛКА НА ПОСТ",
    "Ссылка на пост",
    "post_id",
]

DATA_TYPE_FIELDS = [
    "data_type",
    "type",
]

class Command(BaseCommand):
    help = "Import source records from a CSV file into the annotation queue."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--encoding", default="utf-8-sig")
        parser.add_argument("--source-name", default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument(
            "--data-type",
            default="",
            help="Optional comma-separated data_type filter, for example: comment.",
        )
        parser.add_argument(
            "--require-post-context",
            action="store_true",
            help="Import only rows where post_text is present.",
        )

    def handle(self, *args, **options):
        path = Path(options["csv_path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        created = 0
        skipped = 0
        limit = options["limit"]
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1")
        allowed_data_types = {
            item.strip().lower()
            for item in options["data_type"].split(",")
            if item.strip()
        }
        pending = []
        seen_hashes = set()

        def flush_pending():
            nonlocal created, skipped, pending
            if not pending:
                return
            hashes = [record.source_hash for record in pending]
            existing_hashes = set(
                SourceRecord.objects.filter(source_hash__in=hashes).values_list("source_hash", flat=True)
            )
            new_records = [record for record in pending if record.source_hash not in existing_hashes]
            if not options["dry_run"]:
                SourceRecord.objects.bulk_create(new_records, ignore_conflicts=True, batch_size=batch_size)
            created += len(new_records)
            skipped += len(pending) - len(new_records)
            pending = []

        with path.open("r", encoding=options["encoding"], newline="") as f:
            sample = f.read(8192)
            f.seek(0)
            reader = csv.DictReader(f, dialect=sniff_dialect(sample))
            if not reader.fieldnames:
                raise CommandError(f"CSV header is missing: {path}")

            for index, row in enumerate(reader, start=1):
                if limit and index > limit:
                    break

                data_type = first_value(row, DATA_TYPE_FIELDS).lower()
                if allowed_data_types and data_type not in allowed_data_types:
                    skipped += 1
                    continue

                text = first_value(row, TEXT_FIELDS)
                post_text = first_value(row, POST_TEXT_FIELDS)
                if text == post_text:
                    post_text = ""
                if options["require_post_context"] and not post_text:
                    skipped += 1
                    continue
                if len(text) < 3:
                    skipped += 1
                    continue

                external_id = first_value(row, EXTERNAL_ID_FIELDS) or f"{path.name}:{index}"
                source_hash = SourceRecord.build_hash(text=text, post_text=post_text, external_id=str(external_id))
                if source_hash in seen_hashes:
                    skipped += 1
                    continue
                seen_hashes.add(source_hash)

                pending.append(
                    SourceRecord(
                        source_hash=source_hash,
                        text=text,
                        post_text=post_text,
                        source_name=options["source_name"] or path.name,
                        source_url=first_value(row, SOURCE_URL_FIELDS),
                        group_name=first_value(row, GROUP_NAME_FIELDS),
                        external_id=str(external_id),
                    )
                )
                if len(pending) >= batch_size:
                    flush_pending()

        flush_pending()

        prefix = "Would import" if options["dry_run"] else "Imported"
        self.stdout.write(self.style.SUCCESS(f"{prefix}: {created}; skipped: {skipped}"))
