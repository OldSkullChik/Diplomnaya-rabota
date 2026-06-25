#!/usr/bin/env python
"""Build a fixed-split dataset for internal ЖКХ taxonomy specialists.

The full taxonomy dataset is dominated by `not_jkh`/`not_applicable`. This
builder keeps only rows that are already labelled as ЖКХ-related, so a specialist
can learn the internal distinctions between ЖКХ topics, authority aspects, and
responsible parties.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TARGET_COLS = ["jkh_topic", "authority_aspect", "responsible_party"]
DEFAULT_INPUT_CSV = "data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv"
DEFAULT_OUTPUT_DIR = "data/ml_experiments/jkh_internal_specialist_2026-06-06"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_internal_jkh(row: dict[str, str]) -> bool:
    if row.get("jkh_relevance") == "yes":
        return True
    if row.get("jkh_topic") not in {"", "not_jkh"}:
        return True
    if row.get("authority_aspect") not in {"", "not_applicable"}:
        return True
    if row.get("responsible_party") not in {"", "not_applicable"}:
        return True
    return False


def valid_target_row(row: dict[str, str]) -> bool:
    return all(row.get(col) for col in TARGET_COLS) and all(
        row.get(col) not in {"not_jkh", "not_applicable"} for col in TARGET_COLS
    )


def label_counts(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    return {
        col: dict(Counter(row[col] for row in rows if row.get(col)).most_common())
        for col in TARGET_COLS
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-silver-train", type=int, default=60000)
    parser.add_argument("--silver-weight", type=float, default=0.3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    rows = read_csv(input_path)
    fieldnames = list(rows[0].keys()) if rows else []
    for field in ["jkh_internal_scope"]:
        if field not in fieldnames:
            fieldnames.append(field)

    train_gold: list[dict[str, str]] = []
    train_silver: list[dict[str, str]] = []
    val_test_gold: list[dict[str, str]] = []

    for row in rows:
        if not is_internal_jkh(row) or not valid_target_row(row):
            continue
        out = dict(row)
        out["jkh_internal_scope"] = "yes"
        if out.get("label_source") == "silver_auto":
            out["sample_weight"] = f"{args.silver_weight:g}"
        if out.get("split") == "train" and out.get("label_source") == "gold_human":
            train_gold.append(out)
        elif out.get("split") == "train" and out.get("label_source") == "silver_auto":
            train_silver.append(out)
        elif out.get("split") in {"val", "test"} and out.get("label_source") == "gold_human":
            val_test_gold.append(out)

    if args.max_silver_train and len(train_silver) > args.max_silver_train:
        train_silver = train_silver[: args.max_silver_train]

    dataset_rows = train_gold + train_silver + val_test_gold
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "dataset_jkh_internal_fixed_split.csv", dataset_rows, fieldnames)
    write_csv(output_dir / "train_gold_jkh_internal.csv", train_gold, fieldnames)
    write_csv(output_dir / "train_silver_jkh_internal.csv", train_silver, fieldnames)
    write_csv(output_dir / "gold_val_test_jkh_internal.csv", val_test_gold, fieldnames)

    summary = {
        "input_csv": str(input_path),
        "output_csv": str(output_dir / "dataset_jkh_internal_fixed_split.csv"),
        "target_cols": TARGET_COLS,
        "max_silver_train": args.max_silver_train,
        "silver_weight": args.silver_weight,
        "rows": {
            "train_gold": len(train_gold),
            "train_silver": len(train_silver),
            "val_test_gold": len(val_test_gold),
            "dataset_total": len(dataset_rows),
        },
        "label_counts": label_counts(dataset_rows),
    }
    write_json(output_dir / "dataset_jkh_internal_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
