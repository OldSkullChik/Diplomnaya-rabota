#!/usr/bin/env python
"""Calibrate a binary classifier threshold on validation and report test F1."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from train_rubert_multitask import MultiHeadRuBert, read_csv, set_seed  # noqa: E402


def row_text(row: dict[str, str], text_mode: str) -> str:
    text = str(row.get("text", ""))
    if text_mode == "post_comment":
        return f"[POST] {row.get('post_text', '')} [COMMENT] {text}"
    return text


def batched(rows: list[dict[str, str]], batch_size: int):
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def split_rows(rows: list[dict[str, str]], split: str) -> list[dict[str, str]]:
    return [row for row in rows if str(row.get("split", "")).strip().lower() == split]


def predict_probabilities(
    rows: list[dict[str, str]],
    model: MultiHeadRuBert,
    tokenizer,
    metrics: dict[str, Any],
    target_col: str,
    positive_label: str,
    device: torch.device,
    batch_size: int,
) -> list[dict[str, Any]]:
    label_map = metrics["label_maps"][target_col]
    inverse_map = {idx: label for label, idx in label_map.items()}
    positive_idx = label_map[positive_label]
    outputs: list[dict[str, Any]] = []
    for batch in batched(rows, batch_size):
        encoded = tokenizer(
            [row_text(row, metrics["text_mode"]) for row in batch],
            max_length=int(metrics["max_length"]),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded["attention_mask"].to(device=device, dtype=torch.long)
        with torch.no_grad():
            logits = model(input_ids=input_ids, attention_mask=attention_mask)[target_col]
            probabilities = torch.softmax(logits, dim=1).detach().cpu()
        for row, probs in zip(batch, probabilities):
            argmax_idx = int(torch.argmax(probs).item())
            outputs.append(
                {
                    "record_id": row.get("record_id", ""),
                    "true": row[target_col],
                    "argmax_pred": inverse_map[argmax_idx],
                    "positive_probability": float(probs[positive_idx].item()),
                }
            )
    return outputs


def evaluate_at_threshold(rows: list[dict[str, Any]], threshold: float, positive_label: str, negative_label: str) -> dict[str, Any]:
    true_labels = [row["true"] for row in rows]
    pred_labels = [
        positive_label if float(row["positive_probability"]) >= threshold else negative_label
        for row in rows
    ]
    labels = [positive_label, negative_label]
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(true_labels, pred_labels),
        "macro_f1": f1_score(true_labels, pred_labels, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(true_labels, pred_labels, labels=labels, average="weighted", zero_division=0),
        "positive_f1": f1_score(true_labels, pred_labels, labels=[positive_label], average="macro", zero_division=0),
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


def write_prediction_csv(path: Path, rows: list[dict[str, Any]], threshold: float, positive_label: str, negative_label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["record_id", "true", "argmax_pred", "positive_probability", "threshold_pred"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["threshold_pred"] = (
                positive_label if float(row["positive_probability"]) >= threshold else negative_label
            )
            writer.writerow(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--target-col", required=True)
    parser.add_argument("--positive-label", required=True)
    parser.add_argument("--negative-label", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--metric", choices=["macro_f1", "positive_f1", "weighted_f1"], default="macro_f1")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(42)
    checkpoint_dir = Path(args.checkpoint_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = json.loads((checkpoint_dir / "metrics.json").read_text(encoding="utf-8"))
    rows = [row for row in read_csv(args.input_csv) if row.get(args.target_col)]
    val_rows = split_rows(rows, "val")
    test_rows = split_rows(rows, "test")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer_path = checkpoint_dir / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(metrics["label_maps"][col]) for col in metrics["target_cols"]},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    model.load_state_dict(torch.load(checkpoint_dir / "model.pt", map_location=device))
    model.eval()

    val_predictions = predict_probabilities(
        val_rows, model, tokenizer, metrics, args.target_col, args.positive_label, device, args.batch_size
    )
    test_predictions = predict_probabilities(
        test_rows, model, tokenizer, metrics, args.target_col, args.positive_label, device, args.batch_size
    )

    candidates = [round(value / 100, 2) for value in range(5, 96)]
    val_scores = [
        evaluate_at_threshold(val_predictions, threshold, args.positive_label, args.negative_label)
        for threshold in candidates
    ]
    best_val = max(val_scores, key=lambda row: (float(row[args.metric]), float(row["macro_f1"])))
    test_score = evaluate_at_threshold(
        test_predictions,
        float(best_val["threshold"]),
        args.positive_label,
        args.negative_label,
    )
    result = {
        "checkpoint_dir": args.checkpoint_dir,
        "input_csv": args.input_csv,
        "target_col": args.target_col,
        "positive_label": args.positive_label,
        "negative_label": args.negative_label,
        "selection_metric": args.metric,
        "device": str(device),
        "best_validation": best_val,
        "test_at_best_validation_threshold": test_score,
        "validation_curve": [
            {
                "threshold": row["threshold"],
                "accuracy": row["accuracy"],
                "macro_f1": row["macro_f1"],
                "weighted_f1": row["weighted_f1"],
                "positive_f1": row["positive_f1"],
            }
            for row in val_scores
        ],
    }
    (output_dir / "binary_threshold_evaluation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_prediction_csv(
        output_dir / "val_threshold_predictions.csv",
        val_predictions,
        float(best_val["threshold"]),
        args.positive_label,
        args.negative_label,
    )
    write_prediction_csv(
        output_dir / "test_threshold_predictions.csv",
        test_predictions,
        float(best_val["threshold"]),
        args.positive_label,
        args.negative_label,
    )

    lines = [
        "# Binary Threshold Evaluation",
        "",
        f"- checkpoint: `{args.checkpoint_dir}`",
        f"- target: `{args.target_col}`",
        f"- selected by validation `{args.metric}`",
        f"- threshold: `{float(best_val['threshold']):.2f}`",
        "",
        "## Validation",
        "",
        f"- accuracy: `{best_val['accuracy']:.4f}`",
        f"- macro-F1: `{best_val['macro_f1']:.4f}`",
        f"- weighted-F1: `{best_val['weighted_f1']:.4f}`",
        f"- positive F1: `{best_val['positive_f1']:.4f}`",
        "",
        "## Test",
        "",
        f"- accuracy: `{test_score['accuracy']:.4f}`",
        f"- macro-F1: `{test_score['macro_f1']:.4f}`",
        f"- weighted-F1: `{test_score['weighted_f1']:.4f}`",
        f"- positive F1: `{test_score['positive_f1']:.4f}`",
        f"- confusion matrix: `{test_score['confusion_matrix']}`",
    ]
    (output_dir / "binary_threshold_evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    print(output_dir / "binary_threshold_evaluation.md")


if __name__ == "__main__":
    main()
