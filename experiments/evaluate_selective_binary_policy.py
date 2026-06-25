#!/usr/bin/env python
"""Evaluate a selective binary probability policy on saved predictions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def evaluate(
    rows: list[dict[str, str]],
    negative_threshold: float,
    nonnegative_threshold: float,
    positive_label: str,
    negative_label: str,
) -> dict[str, Any]:
    accepted_true: list[str] = []
    accepted_pred: list[str] = []
    undecided = 0
    for row in rows:
        probability = float(row["positive_probability"])
        if probability >= negative_threshold:
            accepted_true.append(row["true"])
            accepted_pred.append(positive_label)
        elif probability <= nonnegative_threshold:
            accepted_true.append(row["true"])
            accepted_pred.append(negative_label)
        else:
            undecided += 1
    labels = [positive_label, negative_label]
    if not accepted_true:
        raise ValueError("No accepted rows for selected thresholds.")
    report = classification_report(
        accepted_true,
        accepted_pred,
        labels=labels,
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "rows_total": len(rows),
        "rows_accepted": len(accepted_true),
        "rows_undecided": undecided,
        "coverage": len(accepted_true) / max(len(rows), 1),
        "accuracy": accuracy_score(accepted_true, accepted_pred),
        "macro_f1": f1_score(accepted_true, accepted_pred, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(accepted_true, accepted_pred, labels=labels, average="weighted", zero_division=0),
        "positive_f1": report[positive_label]["f1-score"],
        "positive_precision": report[positive_label]["precision"],
        "positive_recall": report[positive_label]["recall"],
        "positive_support": report[positive_label]["support"],
        "report": report,
        "confusion_matrix": confusion_matrix(accepted_true, accepted_pred, labels=labels).tolist(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--val-predictions", required=True)
    parser.add_argument("--test-predictions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--negative-threshold", type=float, required=True)
    parser.add_argument("--nonnegative-threshold", type=float, required=True)
    parser.add_argument("--positive-label", default="negative_omsu")
    parser.add_argument("--negative-label", default="not_negative_omsu")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "policy": {
            "negative_if_probability_at_least": args.negative_threshold,
            "not_negative_if_probability_at_most": args.nonnegative_threshold,
            "otherwise": "low_confidence",
        },
        "validation": evaluate(
            read_csv(Path(args.val_predictions)),
            args.negative_threshold,
            args.nonnegative_threshold,
            args.positive_label,
            args.negative_label,
        ),
        "test": evaluate(
            read_csv(Path(args.test_predictions)),
            args.negative_threshold,
            args.nonnegative_threshold,
            args.positive_label,
            args.negative_label,
        ),
    }
    (output_dir / "selective_binary_policy.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Selective OMSU Binary Policy",
        "",
        f"- negative if probability >= `{args.negative_threshold:.2f}`",
        f"- not negative if probability <= `{args.nonnegative_threshold:.2f}`",
        "- otherwise: `low_confidence`",
        "",
        "| Split | Coverage | Accuracy | Macro-F1 | Weighted-F1 | Negative F1 | Negative precision | Negative recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for split in ["validation", "test"]:
        item = result[split]
        lines.append(
            f"| {split} | {item['coverage']:.4f} | {item['accuracy']:.4f} | "
            f"{item['macro_f1']:.4f} | {item['weighted_f1']:.4f} | "
            f"{item['positive_f1']:.4f} | {item['positive_precision']:.4f} | "
            f"{item['positive_recall']:.4f} |"
        )
    (output_dir / "selective_binary_policy.md").write_text("\n".join(lines), encoding="utf-8")
    print(output_dir / "selective_binary_policy.md")


if __name__ == "__main__":
    main()
