import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


POST_RE = re.compile(r"wall(-?\d+_\d+)")
REPLY_RE = re.compile(r"(?:\?|&)reply=(\d+)")


def post_id_from_url(value):
    match = POST_RE.search(value or "")
    return match.group(1) if match else ""


def comment_id_from_url(value):
    match = REPLY_RE.search(value or "")
    return match.group(1) if match else ""


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise CommandError(f"CSV header is missing: {path}")
        return list(reader), reader.fieldnames


def preferred_text(text):
    return ("[id" in text, len(text))


class Command(BaseCommand):
    help = "Build a relational context bundle for offline pending-annotation review."

    def add_arguments(self, parser):
        parser.add_argument("pending_export")
        parser.add_argument("canonical_dataset")
        parser.add_argument("output_dir")

    def handle(self, *args, **options):
        pending_path = Path(options["pending_export"])
        dataset_path = Path(options["canonical_dataset"])
        output_dir = Path(options["output_dir"])
        if not pending_path.exists():
            raise CommandError(f"Pending export not found: {pending_path}")
        if not dataset_path.exists():
            raise CommandError(f"Canonical dataset not found: {dataset_path}")

        pending_rows, pending_fields = read_csv(pending_path)
        missing_pending_fields = {"annotation_id", "source_url"} - set(pending_fields)
        if missing_pending_fields:
            raise CommandError(f"Pending export is missing fields: {', '.join(sorted(missing_pending_fields))}")

        target_annotations = defaultdict(list)
        needed_posts = set()
        for row in pending_rows:
            source_url = row.get("source_url", "")
            post_id = post_id_from_url(source_url)
            if not post_id:
                raise CommandError(f"Could not parse post id from source_url for annotation {row['annotation_id']}")
            needed_posts.add(post_id)
            target_annotations[source_url].append(row["annotation_id"])

        with dataset_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise CommandError(f"CSV header is missing: {dataset_path}")
            missing_dataset_fields = {"data_type", "post_id", "comment_url", "text"} - set(reader.fieldnames)
            if missing_dataset_fields:
                raise CommandError(f"Canonical dataset is missing fields: {', '.join(sorted(missing_dataset_fields))}")
            source_context_rows = 0
            context_by_key = {}
            for row in reader:
                if row.get("data_type") != "comment" or row.get("post_id") not in needed_posts:
                    continue
                source_context_rows += 1
                key = (row.get("post_id", ""), row.get("comment_url", "") or row.get("text", ""))
                if key not in context_by_key:
                    context_by_key[key] = {**row, "_variants": [row.get("text", "")]}
                    continue
                stored = context_by_key[key]
                if row.get("text", "") not in stored["_variants"]:
                    stored["_variants"].append(row.get("text", ""))
                if preferred_text(row.get("text", "")) > preferred_text(stored.get("text", "")):
                    stored["text"] = row.get("text", "")
            context_rows = list(context_by_key.values())

        counts_by_post = Counter(row["post_id"] for row in context_rows)
        found_targets = {row["comment_url"] for row in context_rows if row["comment_url"] in target_annotations}
        missing_targets = sorted(set(target_annotations) - found_targets)
        if missing_targets:
            raise CommandError(
                f"Context dataset does not include {len(missing_targets)} target comment URLs; "
                f"first missing URL: {missing_targets[0]}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        index_path = output_dir / "pending_context_index.csv"
        comments_path = output_dir / "pending_post_comments_context.csv"
        summary_path = output_dir / "pending_context_summary.txt"

        index_fields = [
            "post_id",
            "target_comment_id",
            "context_comment_count",
            "target_found_in_context",
            "context_scope",
            *pending_fields,
        ]
        with index_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=index_fields)
            writer.writeheader()
            for row in pending_rows:
                source_url = row["source_url"]
                post_id = post_id_from_url(source_url)
                writer.writerow(
                    {
                        "post_id": post_id,
                        "target_comment_id": comment_id_from_url(source_url),
                        "context_comment_count": counts_by_post[post_id],
                        "target_found_in_context": source_url in found_targets,
                        "context_scope": "all_comments_under_same_post_no_reply_tree",
                        **row,
                    }
                )

        comments_fields = [
            "post_id",
            "context_order",
            "is_pending_target",
            "target_annotation_ids",
            "comment_id",
            "comment_url",
            "date",
            "author",
            "text",
            "variant_count",
            "text_variants",
            "post_text",
            "group_name",
            "file_origin",
        ]
        context_rows.sort(key=lambda row: (row.get("post_id", ""), row.get("date", ""), row.get("comment_id", "")))
        context_order = Counter()
        with comments_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=comments_fields)
            writer.writeheader()
            for row in context_rows:
                post_id = row["post_id"]
                context_order[post_id] += 1
                target_ids = target_annotations.get(row["comment_url"], [])
                writer.writerow(
                    {
                        "post_id": post_id,
                        "context_order": context_order[post_id],
                        "is_pending_target": bool(target_ids),
                        "target_annotation_ids": "|".join(target_ids),
                        "comment_id": row.get("comment_id", ""),
                        "comment_url": row["comment_url"],
                        "date": row.get("date", ""),
                        "author": row.get("author", ""),
                        "text": row["text"],
                        "variant_count": len(row["_variants"]),
                        "text_variants": "\n--- VARIANT ---\n".join(row["_variants"]),
                        "post_text": row.get("post_text", ""),
                        "group_name": row.get("group_name", ""),
                        "file_origin": row.get("file_origin", ""),
                    }
                )

        summary = "\n".join(
            [
                f"pending_annotations={len(pending_rows)}",
                f"unique_target_comments={len(target_annotations)}",
                f"distinct_posts={len(needed_posts)}",
                f"source_context_rows={source_context_rows}",
                f"unique_context_comments={len(context_rows)}",
                f"merged_alternate_rows={source_context_rows - len(context_rows)}",
                "missing_target_comments=0",
                "context_scope=all_comments_under_same_post_no_reply_tree",
                "warning=Source archives contain no parent/thread links; context is the full discussion under each post.",
                f"index={index_path}",
                f"comments={comments_path}",
                "",
            ]
        )
        summary_path.write_text(summary, encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Built pending review context bundle in {output_dir}"))
        self.stdout.write(
            f"pending={len(pending_rows)}; target_comments={len(target_annotations)}; "
            f"posts={len(needed_posts)}; source_context_rows={source_context_rows}; "
            f"unique_context_comments={len(context_rows)}"
        )
        self.stdout.write(
            self.style.WARNING(
                "Source archives contain no parent/thread links; exported context is all comments under each post."
            )
        )
