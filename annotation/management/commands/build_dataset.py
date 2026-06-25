import csv
import hashlib
import re
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from annotation.csv_utils import clean_cell, first_value, sniff_dialect


CANONICAL_FIELDS = [
    "text",
    "post_text",
    "data_type",
    "has_post_context",
    "group_id",
    "group_name",
    "post_id",
    "comment_id",
    "comment_url",
    "date",
    "author",
    "likes",
    "sentiment",
    "appeal_type",
    "addressee",
    "file_origin",
]

WALL_RE = re.compile(r"wall(-?\d+_\d+)")
REPLY_RE = re.compile(r"(?:reply|thread)=(\d+)")


@contextmanager
def open_dict_reader(path, encoding):
    f = path.open("r", encoding=encoding, newline="")
    try:
        sample = f.read(8192)
        f.seek(0)
        reader = csv.DictReader(f, dialect=sniff_dialect(sample))
        if not reader.fieldnames:
            raise CommandError(f"CSV header is missing: {path}")
        yield f, reader
    finally:
        f.close()


def post_id_from_url(value):
    match = WALL_RE.search(clean_cell(value))
    return match.group(1) if match else ""


def comment_id_from_url(value):
    match = REPLY_RE.search(clean_cell(value))
    return match.group(1) if match else ""


def post_url_from_id(post_id):
    return f"https://vk.com/wall{post_id}" if post_id else ""


def group_id_from_post_id(post_id):
    return post_id.split("_", 1)[0] if "_" in post_id else ""


def dedupe_hash(row):
    payload = "\n".join(
        [
            clean_cell(row.get("comment_url")) or clean_cell(row.get("post_id")),
            clean_cell(row.get("text")),
            clean_cell(row.get("post_text")),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalized_row(**values):
    row = {field: "" for field in CANONICAL_FIELDS}
    for key, value in values.items():
        row[key] = clean_cell(value)
    row["has_post_context"] = "True" if row["post_text"] else "False"
    return row


class Command(BaseCommand):
    help = "Build one canonical dataset CSV from raw Normalizaciya and Barkov exports."

    def add_arguments(self, parser):
        parser.add_argument("raw_dir")
        parser.add_argument("--output", default="data/processed/dataset_combined.csv")
        parser.add_argument("--missing-output", default="data/processed/missing_post_context.csv")
        parser.add_argument("--encoding", default="utf-8-sig")
        parser.add_argument("--limit", type=int, default=0, help="Stop after writing this many canonical rows.")

    def handle(self, *args, **options):
        raw_dir = Path(options["raw_dir"])
        if not raw_dir.exists():
            raise CommandError(f"Raw directory not found: {raw_dir}")
        if not raw_dir.is_dir():
            raise CommandError(f"Raw path is not a directory: {raw_dir}")

        output_path = Path(options["output"])
        missing_path = Path(options["missing_output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        missing_path.parent.mkdir(parents=True, exist_ok=True)

        csv_files = sorted(raw_dir.glob("*.csv"))
        base_files = [path for path in csv_files if path.name == "dataset.csv"]
        posts_parsed_files = [path for path in csv_files if path.name == "posts_parsed.csv"]
        wallpost_files = [path for path in csv_files if "wallposts" in path.name.lower()]
        comment_files = [path for path in csv_files if "comments" in path.name.lower()]

        post_lookup = {}
        stats = {
            "post_contexts": 0,
            "written": 0,
            "duplicates": 0,
            "skipped_empty": 0,
            "missing_context": 0,
            "base_rows": 0,
            "wallpost_rows": 0,
            "comment_rows": 0,
        }

        for path in posts_parsed_files:
            self.load_posts_parsed(path, options["encoding"], post_lookup, stats)
        for path in wallpost_files:
            self.load_wallpost_contexts(path, options["encoding"], post_lookup, stats)

        seen = set()
        with output_path.open("w", encoding="utf-8-sig", newline="") as out_f, missing_path.open(
            "w", encoding="utf-8-sig", newline=""
        ) as missing_f:
            writer = csv.DictWriter(out_f, fieldnames=CANONICAL_FIELDS)
            writer.writeheader()
            missing_writer = csv.DictWriter(
                missing_f,
                fieldnames=["file_origin", "post_url", "comment_url", "text"],
            )
            missing_writer.writeheader()

            for path in base_files:
                self.write_base_dataset(path, options["encoding"], post_lookup, writer, seen, stats, options["limit"])
            for path in wallpost_files:
                self.write_wallposts(path, options["encoding"], writer, seen, stats, options["limit"])
            for path in comment_files:
                self.write_comments(
                    path,
                    options["encoding"],
                    post_lookup,
                    writer,
                    missing_writer,
                    seen,
                    stats,
                    options["limit"],
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Built dataset: "
                f"{output_path}; written={stats['written']}; duplicates={stats['duplicates']}; "
                f"skipped_empty={stats['skipped_empty']}; missing_context={stats['missing_context']}; "
                f"post_contexts={len(post_lookup)}"
            )
        )

    def should_stop(self, stats, limit):
        return bool(limit and stats["written"] >= limit)

    def write_row(self, writer, row, seen, stats, limit):
        if self.should_stop(stats, limit):
            return
        if len(row["text"]) < 3:
            stats["skipped_empty"] += 1
            return
        row_hash = dedupe_hash(row)
        if row_hash in seen:
            stats["duplicates"] += 1
            return
        seen.add(row_hash)
        writer.writerow(row)
        stats["written"] += 1

    def remember_post_context(self, post_lookup, post_id, post_url, post_text):
        post_text = clean_cell(post_text)
        if not post_text:
            return False
        keys = {clean_cell(post_id), clean_cell(post_url), post_url_from_id(clean_cell(post_id))}
        wrote = False
        for key in keys:
            if key and key not in post_lookup:
                post_lookup[key] = post_text
                wrote = True
        return wrote

    def get_post_context(self, post_lookup, post_id="", post_url=""):
        keys = [clean_cell(post_id), clean_cell(post_url), post_url_from_id(clean_cell(post_id))]
        for key in keys:
            if key and post_lookup.get(key):
                return post_lookup[key]
        return ""

    def load_posts_parsed(self, path, encoding, post_lookup, stats):
        with open_dict_reader(path, encoding) as (f, reader):
            for row in reader:
                post_id = first_value(row, ["post_id"])
                post_url = first_value(row, ["post_url"]) or post_url_from_id(post_id)
                post_text = first_value(row, ["post_text", "ТЕКСТ"])
                if self.remember_post_context(post_lookup, post_id, post_url, post_text):
                    stats["post_contexts"] += 1

    def load_wallpost_contexts(self, path, encoding, post_lookup, stats):
        with open_dict_reader(path, encoding) as (f, reader):
            for row in reader:
                post_url = first_value(row, ["ССЫЛКА НА ПОСТ", "Ссылка на пост", "post_url"])
                post_id = post_id_from_url(post_url) or first_value(row, ["post_id"])
                post_text = first_value(row, ["ТЕКСТ", "post_text", "text"])
                if self.remember_post_context(post_lookup, post_id, post_url, post_text):
                    stats["post_contexts"] += 1

    def write_base_dataset(self, path, encoding, post_lookup, writer, seen, stats, limit):
        with open_dict_reader(path, encoding) as (f, reader):
            for row in reader:
                if self.should_stop(stats, limit):
                    return
                post_id = first_value(row, ["post_id"])
                comment_url = first_value(row, ["comment_url"])
                post_url = post_url_from_id(post_id) or first_value(row, ["post_url"])
                post_text = first_value(row, ["post_text"]) or self.get_post_context(post_lookup, post_id, post_url)
                canonical = normalized_row(
                    text=first_value(row, ["text"]),
                    post_text=post_text,
                    data_type=first_value(row, ["data_type"]) or "comment",
                    group_id=first_value(row, ["group_id"]) or group_id_from_post_id(post_id),
                    group_name=first_value(row, ["group_name"]),
                    post_id=post_id,
                    comment_id=first_value(row, ["comment_id"]) or comment_id_from_url(comment_url),
                    comment_url=comment_url,
                    date=first_value(row, ["date"]),
                    author=first_value(row, ["author"]),
                    likes=first_value(row, ["likes"]),
                    sentiment=first_value(row, ["sentiment"]),
                    appeal_type=first_value(row, ["appeal_type"]),
                    addressee=first_value(row, ["addressee"]),
                    file_origin=first_value(row, ["file_origin"]) or path.name,
                )
                self.write_row(writer, canonical, seen, stats, limit)
                stats["base_rows"] += 1

    def write_wallposts(self, path, encoding, writer, seen, stats, limit):
        with open_dict_reader(path, encoding) as (f, reader):
            for row in reader:
                if self.should_stop(stats, limit):
                    return
                post_url = first_value(row, ["ССЫЛКА НА ПОСТ", "Ссылка на пост", "post_url"])
                post_id = post_id_from_url(post_url) or first_value(row, ["post_id"])
                text = first_value(row, ["ТЕКСТ", "text", "post_text"])
                canonical = normalized_row(
                    text=text,
                    post_text="",
                    data_type="post",
                    group_id=group_id_from_post_id(post_id),
                    group_name=first_value(row, ["НАЗВАНИЕ ВЛАДЕЛЬЦА", "НАЗВАНИЕ ИСТОЧНИКА", "group_name"]),
                    post_id=post_id,
                    comment_id="",
                    comment_url=post_url,
                    date=first_value(row, ["ДАТА ПУБЛИКАЦИИ", "date"]),
                    author=first_value(row, ["АВТОР ЗАПИСИ", "author"]),
                    likes=first_value(row, ["ЛАЙКОВ", "likes"]),
                    file_origin=path.name,
                )
                self.write_row(writer, canonical, seen, stats, limit)
                stats["wallpost_rows"] += 1

    def write_comments(self, path, encoding, post_lookup, writer, missing_writer, seen, stats, limit):
        with open_dict_reader(path, encoding) as (f, reader):
            for row in reader:
                if self.should_stop(stats, limit):
                    return
                comment_url = first_value(row, ["Ссылка на комментарий", "comment_url"])
                post_url = first_value(row, ["Ссылка на пост", "post_url"])
                post_id = post_id_from_url(post_url) or post_id_from_url(comment_url) or first_value(row, ["post_id"])
                post_url = post_url or post_url_from_id(post_id)
                text = first_value(row, ["Текст комментария", "text", "comment"])
                if len(text) < 3:
                    stats["skipped_empty"] += 1
                    continue
                post_text = self.get_post_context(post_lookup, post_id, post_url)
                canonical = normalized_row(
                    text=text,
                    post_text=post_text,
                    data_type="comment",
                    group_id=group_id_from_post_id(post_id),
                    post_id=post_id,
                    comment_id=comment_id_from_url(comment_url),
                    comment_url=comment_url,
                    date=first_value(row, ["Дата и время", "date"]),
                    author=first_value(row, ["Имя и фамилия автора", "author"]),
                    likes=first_value(row, ["Число лайков к комментарию", "likes"]),
                    file_origin=path.name,
                )
                row_hash = dedupe_hash(canonical)
                if row_hash in seen:
                    stats["duplicates"] += 1
                    continue
                if not post_text:
                    stats["missing_context"] += 1
                    missing_writer.writerow(
                        {
                            "file_origin": path.name,
                            "post_url": post_url,
                            "comment_url": comment_url,
                            "text": text,
                        }
                    )
                seen.add(row_hash)
                writer.writerow(canonical)
                stats["written"] += 1
                stats["comment_rows"] += 1
