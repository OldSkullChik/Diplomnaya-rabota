#!/usr/bin/env python
"""Prepare gold/silver datasets for teacher-assisted RuBERT training."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path


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

OUTPUT_FIELDS = [
    "record_id",
    "text",
    "post_text",
    *LABEL_FIELDS,
    "label_source",
    "sample_weight",
    "split",
]

OFFLINE_REVIEW_MARKERS = (
    "Offline teacher label:",
    "Offline verified label.",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def complete_labels(row: dict[str, str]) -> bool:
    return all(clean(row.get(field)) for field in LABEL_FIELDS)


def is_training_ready(row: dict[str, str]) -> bool:
    if not complete_labels(row):
        return False
    if clean(row.get("quality")) == "no_context":
        return False
    if clean(row.get("text")) == "" and clean(row.get("comment_text")) == "":
        return False
    return True


def looks_like_offline_silver(row: dict[str, str]) -> bool:
    review_comment = clean(row.get("review_comment"))
    return any(review_comment.startswith(marker) for marker in OFFLINE_REVIEW_MARKERS)


def from_approved_export(row: dict[str, str], source: str, weight: float) -> dict[str, str]:
    result = {
        "record_id": clean(row.get("record_id")),
        "text": clean(row.get("text")),
        "post_text": clean(row.get("post_text")),
        "label_source": source,
        "sample_weight": f"{weight:g}",
        "split": "",
    }
    for field in LABEL_FIELDS:
        result[field] = clean(row.get(field))
    return result


def from_offline_export(row: dict[str, str], weight: float) -> dict[str, str]:
    result = {
        "record_id": clean(row.get("record_id")),
        "text": clean(row.get("comment_text")),
        "post_text": clean(row.get("post_text")),
        "label_source": "silver_auto",
        "sample_weight": f"{weight:g}",
        "split": "train",
    }
    for field in LABEL_FIELDS:
        result[field] = clean(row.get(field))
    return result


def dedupe_by_record(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped = []
    for row in rows:
        record_id = clean(row.get("record_id"))
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        deduped.append(row)
    return deduped


def split_gold(rows: list[dict[str, str]], seed: int, val_size: float, test_size: float) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    shuffled = rows[:]
    random.Random(seed).shuffle(shuffled)
    n = len(shuffled)
    n_test = max(1, round(n * test_size))
    n_val = max(1, round(n * val_size))
    test = shuffled[:n_test]
    val = shuffled[n_test : n_test + n_val]
    train = shuffled[n_test + n_val :]
    for row in train:
        row["split"] = "train"
    for row in val:
        row["split"] = "val"
    for row in test:
        row["split"] = "test"
    return train, val, test


def distribution(rows: list[dict[str, str]], fields: list[str]) -> dict[str, dict[str, int]]:
    return {field: dict(Counter(row[field] for row in rows).most_common()) for field in fields}


def write_summary(path: Path, summary: dict) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Teacher-student dataset summary",
        "",
        f"Seed: `{summary['seed']}`",
        f"Gold weight: `{summary['weights']['gold']}`",
        f"Silver weight: `{summary['weights']['silver']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Gold Distributions", ""]
    for field, values in summary["gold_distribution"].items():
        lines.append(f"- `{field}`: {values}")
    lines += ["", "## Silver Distributions", ""]
    for field, values in summary["silver_distribution"].items():
        lines.append(f"- `{field}`: {values}")
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-approved", required=True, help="CSV exported by manage.py export_annotations.")
    parser.add_argument("--silver-labels", nargs="+", required=True, help="Offline automatically labeled CSV files.")
    parser.add_argument("--output-dir", default="data/ml_experiments/teacher_student")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gold-weight", type=float, default=1.0)
    parser.add_argument("--silver-weight", type=float, default=0.4)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--test-size", type=float, default=0.15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    gold_rows: list[dict[str, str]] = []
    silver_from_approved = 0
    for row in read_csv(Path(args.gold_approved)):
        if clean(row.get("status")) and clean(row.get("status")) != "approved":
            continue
        if not is_training_ready(row):
            continue
        if looks_like_offline_silver(row):
            silver_from_approved += 1
            continue
        gold_rows.append(from_approved_export(row, "gold_human", args.gold_weight))

    silver_rows: list[dict[str, str]] = []
    for raw_path in args.silver_labels:
        for row in read_csv(Path(raw_path)):
            if clean(row.get("offline_action")) != "approve":
                continue
            if not is_training_ready(row):
                continue
            silver_rows.append(from_offline_export(row, args.silver_weight))

    gold_rows = dedupe_by_record(gold_rows)
    gold_record_ids = {row["record_id"] for row in gold_rows}
    silver_rows = dedupe_by_record([row for row in silver_rows if row["record_id"] not in gold_record_ids])

    if len(gold_rows) < 30:
        raise SystemExit(f"Too few gold rows for fixed train/val/test split: {len(gold_rows)}")
    if not silver_rows:
        raise SystemExit("No usable silver rows found.")

    gold_train, gold_val, gold_test = split_gold(gold_rows, args.seed, args.val_size, args.test_size)
    train_gold_only = gold_train[:]
    train_gold_silver = gold_train + silver_rows
    full_gold_only = gold_train + gold_val + gold_test
    full_gold_silver = train_gold_silver + gold_val + gold_test

    write_csv(output_dir / "gold_train.csv", gold_train)
    write_csv(output_dir / "gold_val.csv", gold_val)
    write_csv(output_dir / "gold_test.csv", gold_test)
    write_csv(output_dir / "silver_train.csv", silver_rows)
    write_csv(output_dir / "train_gold_only.csv", train_gold_only)
    write_csv(output_dir / "train_gold_silver.csv", train_gold_silver)
    write_csv(output_dir / "dataset_gold_only_fixed_split.csv", full_gold_only)
    write_csv(output_dir / "dataset_gold_silver_fixed_split.csv", full_gold_silver)

    summary = {
        "seed": args.seed,
        "inputs": {
            "gold_approved": args.gold_approved,
            "silver_labels": args.silver_labels,
        },
        "weights": {
            "gold": args.gold_weight,
            "silver": args.silver_weight,
        },
        "counts": {
            "gold_total": len(gold_rows),
            "gold_train": len(gold_train),
            "gold_val": len(gold_val),
            "gold_test": len(gold_test),
            "silver_train": len(silver_rows),
            "silver_seen_in_approved_export_skipped": silver_from_approved,
            "train_gold_only": len(train_gold_only),
            "train_gold_silver": len(train_gold_silver),
            "dataset_gold_only_fixed_split": len(full_gold_only),
            "dataset_gold_silver_fixed_split": len(full_gold_silver),
        },
        "gold_distribution": distribution(gold_rows, LABEL_FIELDS),
        "silver_distribution": distribution(silver_rows, LABEL_FIELDS),
    }
    write_summary(output_dir / "summary.json", summary)
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    print(f"Prepared teacher-student datasets in {output_dir}")


if __name__ == "__main__":
    main()
