#!/usr/bin/env python
"""Evaluate derived OMSU score/classes from true and predicted taxonomy labels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from omsu_scoring import calculate_omsu_score


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def eval_labels(true_labels: list[str], pred_labels: list[str], labels: list[str]) -> dict[str, Any]:
    return {
        "labels": labels,
        "accuracy": accuracy_score(true_labels, pred_labels),
        "macro_f1": f1_score(true_labels, pred_labels, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(true_labels, pred_labels, labels=labels, average="weighted", zero_division=0),
        "report": classification_report(
            true_labels,
            pred_labels,
            labels=labels,
            target_names=labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(true_labels, pred_labels, labels=labels).tolist(),
    }


def evaluate_file(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = read_csv(path)
    true_impact: list[str] = []
    pred_impact: list[str] = []
    true_negative: list[str] = []
    pred_negative: list[str] = []
    output_rows: list[dict[str, Any]] = []

    for row in rows:
        true_score = calculate_omsu_score(row, prefix="true_")
        pred_score = calculate_omsu_score(row, prefix="pred_")
        true_impact.append(true_score.impact_class)
        pred_impact.append(pred_score.impact_class)
        true_negative.append(true_score.negative_signal)
        pred_negative.append(pred_score.negative_signal)
        output_rows.append(
            {
                "record_id": row.get("record_id", ""),
                "split": row.get("split", ""),
                "true_omsu_score": true_score.score,
                "pred_omsu_score": pred_score.score,
                "score_abs_error": abs(true_score.score - pred_score.score),
                "true_omsu_impact_class": true_score.impact_class,
                "pred_omsu_impact_class": pred_score.impact_class,
                "true_omsu_negative_signal": true_score.negative_signal,
                "pred_omsu_negative_signal": pred_score.negative_signal,
                "true_reason": true_score.reason,
                "pred_reason": pred_score.reason,
            }
        )

    impact_labels = ["strong_negative", "negative", "neutral_or_no_impact", "positive"]
    negative_labels = ["negative_omsu", "not_negative_omsu"]
    score_errors = [row["score_abs_error"] for row in output_rows]
    result = {
        "input_csv": str(path),
        "rows": len(rows),
        "omsu_impact_class": eval_labels(true_impact, pred_impact, impact_labels),
        "omsu_negative_signal": eval_labels(true_negative, pred_negative, negative_labels),
        "score_abs_error": {
            "mean": sum(score_errors) / max(len(score_errors), 1),
            "max": max(score_errors) if score_errors else 0,
            "within_10": sum(1 for value in score_errors if value <= 10) / max(len(score_errors), 1),
            "within_20": sum(1 for value in score_errors if value <= 20) / max(len(score_errors), 1),
        },
    }
    return result, output_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-csv", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"files": {}}
    for prediction_csv in args.prediction_csv:
        path = Path(prediction_csv)
        result, rows = evaluate_file(path)
        key = path.stem
        summary["files"][key] = result
        write_csv(
            output_dir / f"{key}_omsu_scores.csv",
            rows,
            [
                "record_id",
                "split",
                "true_omsu_score",
                "pred_omsu_score",
                "score_abs_error",
                "true_omsu_impact_class",
                "pred_omsu_impact_class",
                "true_omsu_negative_signal",
                "pred_omsu_negative_signal",
                "true_reason",
                "pred_reason",
            ],
        )

    (output_dir / "omsu_score_evaluation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# OMSU Score Evaluation", ""]
    for key, result in summary["files"].items():
        impact = result["omsu_impact_class"]
        negative = result["omsu_negative_signal"]
        errors = result["score_abs_error"]
        lines += [
            f"## `{key}`",
            "",
            f"- rows: `{result['rows']}`",
            f"- impact-class macro-F1: `{impact['macro_f1']:.4f}`",
            f"- impact-class weighted-F1: `{impact['weighted_f1']:.4f}`",
            f"- negative-signal macro-F1: `{negative['macro_f1']:.4f}`",
            f"- negative-signal weighted-F1: `{negative['weighted_f1']:.4f}`",
            f"- score mean absolute error: `{errors['mean']:.2f}`",
            f"- score within 10 points: `{errors['within_10']:.4f}`",
            f"- score within 20 points: `{errors['within_20']:.4f}`",
            "",
        ]
    (output_dir / "omsu_score_evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    print(output_dir / "omsu_score_evaluation.md")


if __name__ == "__main__":
    main()
