#!/usr/bin/env python
"""Analyze class distributions and candidate class weights for multitask runs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

TARGET_COLS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]


PRESETS = [
    {
        "name": "current_weighted_balanced",
        "source": "weighted_train",
        "power": 1.0,
        "max_weight": 0.0,
        "description": "Current baseline: train distribution after sample weights.",
    },
    {
        "name": "gold_cap3",
        "source": "gold_train",
        "power": 1.0,
        "max_weight": 3.0,
        "description": "Gold-only inverse frequency with cap 3.",
    },
    {
        "name": "gold_cap5",
        "source": "gold_train",
        "power": 1.0,
        "max_weight": 5.0,
        "description": "Gold-only inverse frequency with cap 5.",
    },
    {
        "name": "gold_power075_cap4",
        "source": "gold_train",
        "power": 0.75,
        "max_weight": 4.0,
        "description": "Gold-only smoothed inverse frequency with cap 4.",
    },
    {
        "name": "weighted_power075_cap4",
        "source": "weighted_train",
        "power": 0.75,
        "max_weight": 4.0,
        "description": "Weighted train distribution, smoothed and capped.",
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def row_weight(row: dict[str, str]) -> float:
    try:
        return float(row.get("sample_weight", "1") or "1")
    except ValueError:
        return 1.0


def apply_weight_overrides(rows: list[dict[str, str]], gold_weight: float | None, silver_weight: float | None) -> None:
    for row in rows:
        source = row.get("label_source", "")
        if source == "gold_human" and gold_weight is not None:
            row["sample_weight"] = f"{gold_weight:g}"
        elif source == "silver_auto" and silver_weight is not None:
            row["sample_weight"] = f"{silver_weight:g}"


def split_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    train = [row for row in rows if row.get("split") == "train"]
    val = [row for row in rows if row.get("split") == "val"]
    test = [row for row in rows if row.get("split") == "test"]
    if not train or not val or not test:
        raise ValueError("Expected fixed split columns train/val/test.")
    return train, val, test


def label_values(rows: list[dict[str, str]], target_cols: list[str]) -> dict[str, list[str]]:
    return {
        col: sorted({row[col] for row in rows if row.get(col)})
        for col in target_cols
    }


def counts(rows: list[dict[str, str]], col: str, weighted: bool = False) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in rows:
        value = row.get(col)
        if not value:
            continue
        result[value] += row_weight(row) if weighted else 1
    return result


def balanced_weights(
    source_counts: Counter[str],
    labels: list[str],
    power: float = 1.0,
    max_weight: float = 0.0,
) -> dict[str, float]:
    total = sum(source_counts.values())
    if total <= 0:
        return {label: 1.0 for label in labels}
    raw: dict[str, float] = {}
    for label in labels:
        count = max(float(source_counts.get(label, 0)), 1.0)
        weight = total / (len(labels) * count)
        if power != 1.0:
            weight = weight**power
        raw[label] = float(weight)
    weighted_mean = sum(float(source_counts.get(label, 0)) * raw[label] for label in labels) / total
    if weighted_mean > 0:
        raw = {label: float(value / weighted_mean) for label, value in raw.items()}
    if max_weight > 0:
        raw = {label: min(value, max_weight) for label, value in raw.items()}
    return raw


def preset_counts(preset: dict[str, Any], train_rows: list[dict[str, str]], col: str) -> Counter[str]:
    if preset["source"] == "gold_train":
        return counts([row for row in train_rows if row.get("label_source") == "gold_human"], col, weighted=False)
    if preset["source"] == "weighted_train":
        return counts(train_rows, col, weighted=True)
    raise ValueError(f"Unknown source: {preset['source']}")


def build(args: argparse.Namespace) -> None:
    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [row for row in read_csv(input_path) if all(row.get(col) for col in args.target_cols)]
    apply_weight_overrides(rows, args.gold_weight_override, args.silver_weight_override)
    train_rows, val_rows, test_rows = split_rows(rows)
    gold_train_rows = [row for row in train_rows if row.get("label_source") == "gold_human"]
    silver_train_rows = [row for row in train_rows if row.get("label_source") == "silver_auto"]
    labels_by_col = label_values(rows, args.target_cols)

    detail_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "input_csv": str(input_path),
        "rows": {
            "total": len(rows),
            "train": len(train_rows),
            "val": len(val_rows),
            "test": len(test_rows),
            "gold_train": len(gold_train_rows),
            "silver_train": len(silver_train_rows),
        },
        "presets": PRESETS,
        "targets": {},
    }

    for col in args.target_cols:
        labels = labels_by_col[col]
        gold_counts = counts(gold_train_rows, col)
        silver_counts = counts(silver_train_rows, col)
        weighted_train_counts = counts(train_rows, col, weighted=True)
        test_counts = counts(test_rows, col)
        summary["targets"][col] = {
            "labels": labels,
            "gold_train_counts": dict(gold_counts),
            "silver_train_counts": dict(silver_counts),
            "weighted_train_counts": dict(weighted_train_counts),
            "test_counts": dict(test_counts),
            "weights": {},
        }

        for preset in PRESETS:
            source_counts = preset_counts(preset, train_rows, col)
            weights = balanced_weights(
                source_counts,
                labels,
                power=float(preset["power"]),
                max_weight=float(preset["max_weight"]),
            )
            summary["targets"][col]["weights"][preset["name"]] = weights
            for label in labels:
                detail_rows.append(
                    {
                        "target": col,
                        "label": label,
                        "gold_train_count": gold_counts.get(label, 0),
                        "silver_train_count": silver_counts.get(label, 0),
                        "weighted_train_count": round(float(weighted_train_counts.get(label, 0)), 4),
                        "test_count": test_counts.get(label, 0),
                        "preset": preset["name"],
                        "weight": round(float(weights[label]), 6),
                    }
                )

    write_csv(
        output_dir / "class_weight_candidates.csv",
        detail_rows,
        [
            "target",
            "label",
            "gold_train_count",
            "silver_train_count",
            "weighted_train_count",
            "test_count",
            "preset",
            "weight",
        ],
    )
    (output_dir / "class_weight_candidates.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Class Weight Candidate Analysis",
        "",
        f"- Input: `{input_path}`",
        f"- Total rows: `{len(rows)}`",
        f"- Train: `{len(train_rows)}`",
        f"- Gold train: `{len(gold_train_rows)}`",
        f"- Silver train: `{len(silver_train_rows)}`",
        f"- Validation/Test: `{len(val_rows)}` / `{len(test_rows)}`",
        f"- Gold weight override: `{args.gold_weight_override}`",
        f"- Silver weight override: `{args.silver_weight_override}`",
        "",
        "## Presets",
        "",
    ]
    for preset in PRESETS:
        lines.append(f"- `{preset['name']}`: {preset['description']}")
    lines += ["", "## Per-Target Extremes", ""]
    for col in args.target_cols:
        lines.append(f"### `{col}`")
        rows_for_col = [row for row in detail_rows if row["target"] == col]
        for preset in PRESETS:
            preset_rows = [row for row in rows_for_col if row["preset"] == preset["name"]]
            preset_rows = sorted(preset_rows, key=lambda row: float(row["weight"]), reverse=True)
            strongest = ", ".join(f"`{row['label']}`={row['weight']}" for row in preset_rows[:5])
            weakest = ", ".join(f"`{row['label']}`={row['weight']}" for row in preset_rows[-3:])
            lines.append(f"- `{preset['name']}` strongest: {strongest}")
            lines.append(f"  weakest: {weakest}")
        lines.append("")
    (output_dir / "class_weight_candidates.md").write_text("\n".join(lines), encoding="utf-8")
    print(output_dir / "class_weight_candidates.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default="data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv")
    parser.add_argument("--output-dir", default="data/ml_experiments/class_weight_analysis_2026-06-05")
    parser.add_argument("--target-cols", nargs="+", default=TARGET_COLS)
    parser.add_argument("--gold-weight-override", type=float, default=None)
    parser.add_argument("--silver-weight-override", type=float, default=0.3)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
