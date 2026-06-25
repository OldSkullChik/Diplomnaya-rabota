#!/usr/bin/env python
"""Calibrate selective taxonomy thresholds on validation and evaluate on test."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from sklearn.metrics import accuracy_score, classification_report, f1_score


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def accepted_rows(rows: list[dict[str, str]], axis: str, threshold: float) -> list[dict[str, str]]:
    return [row for row in rows if float(row.get(f"pred_{axis}_confidence", 0.0) or 0.0) >= threshold]


def evaluate_axis(rows: list[dict[str, str]], axis: str, threshold: float, labels_all: list[str]) -> dict[str, Any]:
    accepted = accepted_rows(rows, axis, threshold)
    if not accepted:
        return {
            "threshold": threshold,
            "coverage": 0.0,
            "rows_total": len(rows),
            "rows_accepted": 0,
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "macro_f1_present_labels": 0.0,
            "weighted_f1": 0.0,
            "labels_present": [],
            "labels_all": labels_all,
        }
    true_labels = [row[f"true_{axis}"] for row in accepted]
    pred_labels = [row[f"final_{axis}"] for row in accepted]
    labels_present = sorted(set(true_labels) | set(pred_labels))
    return {
        "threshold": threshold,
        "coverage": len(accepted) / max(len(rows), 1),
        "rows_total": len(rows),
        "rows_accepted": len(accepted),
        "accuracy": accuracy_score(true_labels, pred_labels),
        "macro_f1": f1_score(true_labels, pred_labels, labels=labels_all, average="macro", zero_division=0),
        "macro_f1_present_labels": f1_score(true_labels, pred_labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(true_labels, pred_labels, average="weighted", zero_division=0),
        "labels_present": labels_present,
        "labels_all": labels_all,
        "report": classification_report(
            true_labels,
            pred_labels,
            labels=labels_all,
            target_names=labels_all,
            output_dict=True,
            zero_division=0,
        ),
    }


def choose_threshold(
    val_rows: list[dict[str, str]],
    axis: str,
    min_coverage: float,
    metric: str,
    labels_all: list[str],
) -> dict[str, Any]:
    candidates = [value / 100 for value in range(0, 101)]
    scored = [evaluate_axis(val_rows, axis, threshold, labels_all) for threshold in candidates]
    eligible = [row for row in scored if row["coverage"] >= min_coverage]
    if not eligible:
        eligible = scored
    return max(
        eligible,
        key=lambda row: (
            float(row.get(metric, 0.0)),
            float(row.get("macro_f1", 0.0)),
            float(row.get("coverage", 0.0)),
        ),
    )


def write_prediction_decisions(
    path: Path,
    rows: list[dict[str, str]],
    thresholds: dict[str, float],
) -> None:
    fields = ["record_id", "split"]
    for axis in TARGET_COLS:
        fields.extend(
            [
                f"true_{axis}",
                f"final_{axis}",
                f"pred_{axis}_confidence",
                f"selective_{axis}",
                f"selective_{axis}_accepted",
            ]
        )
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = {"record_id": row.get("record_id", ""), "split": row.get("split", "")}
        for axis in TARGET_COLS:
            accepted = float(row.get(f"pred_{axis}_confidence", 0.0) or 0.0) >= thresholds[axis]
            out[f"true_{axis}"] = row[f"true_{axis}"]
            out[f"final_{axis}"] = row[f"final_{axis}"]
            out[f"pred_{axis}_confidence"] = row[f"pred_{axis}_confidence"]
            out[f"selective_{axis}"] = row[f"final_{axis}"] if accepted else "low_confidence"
            out[f"selective_{axis}_accepted"] = "1" if accepted else "0"
        out_rows.append(out)
    write_csv(path, out_rows, fields)


def write_report(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Selective Taxonomy Policy",
        "",
        f"- validation CSV: `{result['validation_csv']}`",
        f"- test CSV: `{result['test_csv']}`",
        f"- min coverage: `{result['min_coverage']}`",
        f"- threshold selection metric: `{result['selection_metric']}`",
        "",
        "| Axis | Threshold | Test coverage | Test accuracy | Test macro-F1 | Test weighted-F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for axis in TARGET_COLS:
        item = result["axes"][axis]["test"]
        lines.append(
            f"| `{axis}` | {item['threshold']:.2f} | {item['coverage']:.4f} | "
            f"{item['accuracy']:.4f} | {item['macro_f1']:.4f} | {item['weighted_f1']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"- mean test macro-F1: `{result['mean_test_macro_f1']:.4f}`",
            f"- mean test coverage: `{result['mean_test_coverage']:.4f}`",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-csv", required=True)
    parser.add_argument("--test-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-coverage", type=float, default=0.5)
    parser.add_argument("--selection-metric", choices=["macro_f1", "weighted_f1", "accuracy"], default="macro_f1")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    val_rows = read_csv(Path(args.validation_csv))
    test_rows = read_csv(Path(args.test_csv))
    labels_by_axis = {
        axis: sorted(
            {row[f"true_{axis}"] for row in [*val_rows, *test_rows]}
            | {row[f"final_{axis}"] for row in [*val_rows, *test_rows]}
        )
        for axis in TARGET_COLS
    }

    result: dict[str, Any] = {
        "validation_csv": args.validation_csv,
        "test_csv": args.test_csv,
        "min_coverage": args.min_coverage,
        "selection_metric": args.selection_metric,
        "axes": {},
    }
    thresholds: dict[str, float] = {}
    for axis in TARGET_COLS:
        selected = choose_threshold(val_rows, axis, args.min_coverage, args.selection_metric, labels_by_axis[axis])
        threshold = float(selected["threshold"])
        thresholds[axis] = threshold
        result["axes"][axis] = {
            "validation": selected,
            "test": evaluate_axis(test_rows, axis, threshold, labels_by_axis[axis]),
        }
    result["thresholds"] = thresholds
    result["mean_test_macro_f1"] = sum(result["axes"][axis]["test"]["macro_f1"] for axis in TARGET_COLS) / len(TARGET_COLS)
    result["mean_test_coverage"] = sum(result["axes"][axis]["test"]["coverage"] for axis in TARGET_COLS) / len(TARGET_COLS)
    write_json(output_dir / "selective_taxonomy_policy.json", result)
    write_report(output_dir / "selective_taxonomy_policy.md", result)
    write_prediction_decisions(output_dir / "test_selective_taxonomy_predictions.csv", test_rows, thresholds)
    print(output_dir / "selective_taxonomy_policy.md")


if __name__ == "__main__":
    main()
