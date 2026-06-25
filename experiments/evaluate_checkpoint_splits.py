#!/usr/bin/env python
"""Evaluate a saved multitask checkpoint on fixed validation/test splits."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from sklearn.metrics import classification_report, confusion_matrix
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from train_rubert_multitask import MultiHeadRuBert, read_csv, set_seed  # noqa: E402


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def labels_in_order(label_map: dict[str, int]) -> list[str]:
    return [label for label, _ in sorted(label_map.items(), key=lambda item: item[1])]


def per_class_stats(true_labels: list[str], pred_labels: list[str], labels: list[str]) -> dict[str, dict[str, Any]]:
    matrix = confusion_matrix(true_labels, pred_labels, labels=labels)
    report = classification_report(
        true_labels,
        pred_labels,
        labels=labels,
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    stats: dict[str, dict[str, Any]] = {}
    total = int(matrix.sum())
    for idx, label in enumerate(labels):
        tp = int(matrix[idx, idx])
        fn = int(matrix[idx, :].sum() - tp)
        fp = int(matrix[:, idx].sum() - tp)
        tn = total - tp - fn - fp
        label_report = report.get(label, {})
        stats[label] = {
            "support": int(label_report.get("support", 0)),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": float(label_report.get("precision", 0.0)),
            "recall": float(label_report.get("recall", 0.0)),
            "f1": float(label_report.get("f1-score", 0.0)),
        }
    return stats


def evaluate_split(
    rows: list[dict[str, str]],
    model: MultiHeadRuBert,
    tokenizer,
    metrics: dict[str, Any],
    target_cols: list[str],
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    label_maps = metrics["label_maps"]
    inverse_maps = {
        col: {idx: label for label, idx in label_map.items()}
        for col, label_map in label_maps.items()
    }
    true_by_col = {col: [] for col in target_cols}
    pred_by_col = {col: [] for col in target_cols}
    prediction_rows: list[dict[str, str]] = []

    for batch in batched(rows, batch_size):
        texts = [row_text(row, metrics["text_mode"]) for row in batch]
        encoded = tokenizer(
            texts,
            max_length=int(metrics["max_length"]),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded["attention_mask"].to(device=device, dtype=torch.long)
        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        batch_predictions: dict[str, list[str]] = {}
        for col in target_cols:
            pred_ids = torch.argmax(outputs[col], dim=1).cpu().tolist()
            batch_predictions[col] = [inverse_maps[col][idx] for idx in pred_ids]

        for idx, row in enumerate(batch):
            out = {
                "row_id": row.get("row_id", ""),
                "record_id": row.get("record_id", ""),
                "label_source": row.get("label_source", ""),
                "split": row.get("split", ""),
            }
            for col in target_cols:
                true_label = row[col]
                pred_label = batch_predictions[col][idx]
                true_by_col[col].append(true_label)
                pred_by_col[col].append(pred_label)
                out[f"true_{col}"] = true_label
                out[f"pred_{col}"] = pred_label
            prediction_rows.append(out)

    reports: dict[str, Any] = {}
    for col in target_cols:
        labels = labels_in_order(label_maps[col])
        stats = per_class_stats(true_by_col[col], pred_by_col[col], labels)
        reports[col] = {
            "labels": labels,
            "per_class": stats,
            "macro_f1": sum(value["f1"] for value in stats.values()) / max(len(stats), 1),
            "accuracy": sum(
                1 for true_label, pred_label in zip(true_by_col[col], pred_by_col[col]) if true_label == pred_label
            )
            / max(len(true_by_col[col]), 1),
        }
    return reports, prediction_rows


def write_predictions(path: Path, rows: list[dict[str, str]], target_cols: list[str]) -> None:
    fields = ["row_id", "record_id", "label_source", "split"]
    for col in target_cols:
        fields += [f"true_{col}", f"pred_{col}"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(42)
    checkpoint_dir = Path(args.checkpoint_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = json.loads((checkpoint_dir / "metrics.json").read_text(encoding="utf-8"))
    target_cols = metrics["target_cols"]
    rows = [row for row in read_csv(args.input_csv) if all(row.get(col) for col in target_cols)]
    val_rows = split_rows(rows, "val")
    test_rows = split_rows(rows, "test")
    if not val_rows or not test_rows:
        raise SystemExit("Expected fixed val/test splits.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer_path = checkpoint_dir / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(metrics["label_maps"][col]) for col in target_cols},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    state = torch.load(checkpoint_dir / "model.pt", map_location=device)
    model.load_state_dict(state)
    model.eval()

    result: dict[str, Any] = {
        "input_csv": args.input_csv,
        "checkpoint_dir": args.checkpoint_dir,
        "device": str(device),
        "target_cols": target_cols,
        "rows": {"val": len(val_rows), "test": len(test_rows)},
        "splits": {},
    }
    all_prediction_rows: list[dict[str, str]] = []
    for split_name, split_data in [("val", val_rows), ("test", test_rows)]:
        reports, prediction_rows = evaluate_split(
            split_data,
            model,
            tokenizer,
            metrics,
            target_cols,
            device,
            args.batch_size,
        )
        result["splits"][split_name] = reports
        all_prediction_rows.extend(prediction_rows)
        write_predictions(output_dir / f"{split_name}_predictions.csv", prediction_rows, target_cols)

    write_json(output_dir / "split_class_reports.json", result)
    headline = {
        split: {
            col: round(payload["macro_f1"], 4)
            for col, payload in result["splits"][split].items()
        }
        for split in result["splits"]
    }
    print(json.dumps({"device": str(device), "rows": result["rows"], "macro_f1": headline}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
