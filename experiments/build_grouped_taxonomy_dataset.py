#!/usr/bin/env python
"""Build a grouped-taxonomy version of the teacher-student dataset."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


GROUPED_TARGET_COLS = [
    "jkh_relevance_grouped",
    "jkh_topic_grouped",
    "authority_aspect_grouped",
    "sentiment_grouped",
    "appeal_type_grouped",
    "responsible_party_grouped",
    "sarcasm_grouped",
    "quality_grouped",
]


MAPPINGS = {
    "jkh_relevance": {
        "yes": "yes",
        "no": "no_or_unsure",
        "unsure": "no_or_unsure",
    },
    "jkh_topic": {
        "not_jkh": "not_jkh",
        "cold_water_sewerage": "utilities_water_heat",
        "heating_hot_water": "utilities_water_heat",
        "house_common_property": "housing_management",
        "management_company": "housing_management",
        "yard_area": "yard_improvement",
        "waste_cleaning": "waste_cleaning",
        "payments_tariffs": "payments_tariffs",
        "public_authorities": "public_authorities",
        "other_jkh": "other_jkh",
    },
    "authority_aspect": {
        "not_applicable": "not_applicable",
        "poor_quality": "service_problem",
        "slow_response": "service_problem",
        "no_action": "service_problem",
        "communication": "communication",
        "supervision": "governance_control",
        "tariff_policy": "governance_control",
        "positive_feedback": "positive_feedback",
        "other": "other",
    },
    "sentiment": {
        "negative": "negative",
        "neutral": "neutral",
        "positive": "positive",
        "mixed": "mixed",
    },
    "appeal_type": {
        "complaint": "problem_appeal",
        "demand": "problem_appeal",
        "request": "problem_appeal",
        "question": "question",
        "info": "info",
        "opinion": "opinion",
        "suggestion": "constructive_positive",
        "gratitude": "constructive_positive",
        "other": "other",
    },
    "responsible_party": {
        "not_applicable": "not_applicable",
        "local_administration": "public_authority",
        "housing_inspection": "public_authority",
        "specific_person": "public_authority",
        "management_company": "utility_or_management",
        "resource_provider": "utility_or_management",
        "waste_operator": "utility_or_management",
        "residents": "residents",
        "unknown": "unknown",
    },
    "sarcasm": {
        "yes": "yes",
        "no": "no",
        "unsure": "unsure",
    },
    "quality": {
        "normal": "normal",
        "spam": "spam",
        "difficult": "problematic_or_duplicate",
        "duplicate": "problematic_or_duplicate",
        "no_context": "problematic_or_duplicate",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def map_value(field: str, value: str) -> str:
    mapping = MAPPINGS[field]
    if value not in mapping:
        raise ValueError(f"No grouped mapping for {field}={value!r}")
    return mapping[value]


def build(args: argparse.Namespace) -> None:
    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(input_path)

    grouped_rows: list[dict[str, str]] = []
    distributions: dict[str, Counter[str]] = defaultdict(Counter)
    old_to_new: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        out = dict(row)
        for field in MAPPINGS:
            grouped_field = f"{field}_grouped"
            grouped = map_value(field, row.get(field, ""))
            out[grouped_field] = grouped
            distributions[grouped_field][grouped] += 1
            old_to_new[field][f"{row.get(field, '')} -> {grouped}"] += 1
        grouped_rows.append(out)

    fieldnames = list(grouped_rows[0].keys()) if grouped_rows else []
    dataset_path = output_dir / "dataset_gold_silver_grouped_fixed_split.csv"
    write_csv(dataset_path, grouped_rows, fieldnames)

    for split in ("train", "val", "test"):
        split_rows = [row for row in grouped_rows if row.get("split") == split]
        write_csv(output_dir / f"{split}_grouped.csv", split_rows, fieldnames)

    summary: dict[str, Any] = {
        "input_csv": str(input_path),
        "dataset_csv": str(dataset_path),
        "rows": len(grouped_rows),
        "grouped_target_cols": GROUPED_TARGET_COLS,
        "mappings": MAPPINGS,
        "distributions": {field: dict(counter.most_common()) for field, counter in distributions.items()},
        "old_to_grouped": {field: dict(counter.most_common()) for field, counter in old_to_new.items()},
    }
    (output_dir / "grouped_taxonomy_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Grouped Taxonomy Dataset",
        "",
        f"- Input: `{input_path}`",
        f"- Output: `{dataset_path}`",
        f"- Rows: `{len(grouped_rows)}`",
        "",
        "## Grouped Target Columns",
        "",
    ]
    for field in GROUPED_TARGET_COLS:
        lines.append(f"- `{field}`")
    lines += ["", "## Distributions", ""]
    for field in GROUPED_TARGET_COLS:
        lines.append(f"### `{field}`")
        for label, count in distributions[field].most_common():
            lines.append(f"- `{label}`: `{count}`")
        lines.append("")
    (output_dir / "grouped_taxonomy_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(dataset_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default="data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv")
    parser.add_argument("--output-dir", default="data/ml_experiments/teacher_student_grouped_2026-06-04")
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
