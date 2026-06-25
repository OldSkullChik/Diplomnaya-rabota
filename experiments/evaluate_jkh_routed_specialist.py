#!/usr/bin/env python
"""Evaluate a routed ЖКХ-internal specialist on full human-gold splits."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import torch
from sklearn.metrics import accuracy_score, classification_report, f1_score
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from train_rubert_multitask import MultiHeadRuBert, read_csv, set_seed  # noqa: E402


INTERNAL_COLS = ["jkh_topic", "authority_aspect", "responsible_party"]
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
DEFAULT_INPUT_CSV = "data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_only_fixed_split.csv"
DEFAULT_CASCADE_DIR = "data/ml_experiments/cascade_eval_2026-06-06_01-48"
DEFAULT_SPECIALIST_DIR = "data/ml_experiments/jkh_internal_specialist_2026-06-06/model"
DEFAULT_OUTPUT_DIR = "data/ml_experiments/jkh_internal_specialist_2026-06-06/routed_eval"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_rows(rows: list[dict[str, str]], split: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get("split") == split]


def row_key(row: dict[str, str], idx: int) -> str:
    return row.get("row_id") or row.get("record_id") or str(idx)


def row_text(row: dict[str, str], text_mode: str) -> str:
    text = str(row.get("text", ""))
    if text_mode == "post_comment":
        return f"[POST] {row.get('post_text', '')} [COMMENT] {text}"
    return text


def batched(rows: list[dict[str, str]], batch_size: int):
    for start in range(0, len(rows), batch_size):
        yield start, rows[start : start + batch_size]


def labels_for_axis(rows: list[dict[str, str]], axis: str) -> list[str]:
    return sorted({row[axis] for row in rows if row.get(axis)})


def axis_metrics(true_labels: list[str], pred_labels: list[str], labels: list[str]) -> dict[str, Any]:
    report = classification_report(
        true_labels,
        pred_labels,
        labels=labels,
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "accuracy": accuracy_score(true_labels, pred_labels),
        "macro_f1": f1_score(true_labels, pred_labels, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(true_labels, pred_labels, labels=labels, average="weighted", zero_division=0),
        "report": report,
    }


def load_cascade(cascade_dir: Path, split: str) -> dict[str, dict[str, str]]:
    path = cascade_dir / f"{split}_cascade_predictions.csv"
    rows = {}
    for idx, row in enumerate(read_csv(path)):
        key = row_key(row, idx)
        rows[key] = row
    return rows


def load_specialist(checkpoint_dir: Path, device: torch.device) -> tuple[dict[str, Any], Any, MultiHeadRuBert]:
    metrics = json.loads((checkpoint_dir / "metrics.json").read_text(encoding="utf-8"))
    tokenizer_path = checkpoint_dir / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(metrics["label_maps"][col]) for col in metrics["target_cols"]},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    model.load_state_dict(torch.load(checkpoint_dir / "model.pt", map_location=device))
    model.eval()
    return metrics, tokenizer, model


def predict_specialist(
    rows_by_split: dict[str, list[dict[str, str]]],
    checkpoint_dir: Path,
    batch_size: int,
    device: torch.device,
) -> dict[str, dict[str, dict[str, Any]]]:
    metrics, tokenizer, model = load_specialist(checkpoint_dir, device)
    inverse_maps = {
        col: {idx: label for label, idx in label_map.items()}
        for col, label_map in metrics["label_maps"].items()
    }
    out: dict[str, dict[str, dict[str, Any]]] = {}
    with torch.no_grad():
        for split, rows in rows_by_split.items():
            split_out: dict[str, dict[str, Any]] = {}
            for start, batch in batched(rows, batch_size):
                encoded = tokenizer(
                    [row_text(row, metrics["text_mode"]) for row in batch],
                    max_length=int(metrics["max_length"]),
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt",
                )
                input_ids = encoded["input_ids"].to(device)
                attention_mask = encoded["attention_mask"].to(device=device, dtype=torch.long)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                for offset, row in enumerate(batch):
                    key = row_key(row, start + offset)
                    split_out[key] = {}
                    for axis in INTERNAL_COLS:
                        probs = torch.softmax(outputs[axis][offset], dim=0).detach().cpu()
                        pred_idx = int(torch.argmax(probs).item())
                        split_out[key][f"pred_{axis}"] = inverse_maps[axis][pred_idx]
                        split_out[key][f"confidence_{axis}"] = float(probs[pred_idx].item())
            out[split] = split_out
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return out


def build_routed_predictions(
    rows_by_split: dict[str, list[dict[str, str]]],
    cascade_dir: Path,
    specialist_predictions: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    routed: dict[str, list[dict[str, Any]]] = {}
    for split, rows in rows_by_split.items():
        cascade_rows = load_cascade(cascade_dir, split)
        split_out: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            key = row_key(row, idx)
            cascade = cascade_rows[key]
            is_pred_jkh = cascade.get("final_jkh_relevance") == "yes"
            out = {
                "row_key": key,
                "record_id": row.get("record_id", ""),
                "split": split,
                "route": "jkh_internal_specialist" if is_pred_jkh else "cascade_non_jkh",
            }
            for axis in TARGET_COLS:
                out[f"true_{axis}"] = row[axis]
                out[f"pred_{axis}"] = cascade.get(f"final_{axis}", cascade.get(f"pred_{axis}", ""))
                out[f"source_{axis}"] = "cascade"

            if is_pred_jkh:
                specialist = specialist_predictions[split][key]
                for axis in INTERNAL_COLS:
                    out[f"pred_{axis}"] = specialist[f"pred_{axis}"]
                    out[f"source_{axis}"] = "jkh_internal_specialist"
                    out[f"confidence_{axis}"] = specialist[f"confidence_{axis}"]
                if out["pred_jkh_topic"] == "not_jkh":
                    out["pred_jkh_topic"] = "other_jkh"
            else:
                out["pred_jkh_topic"] = "not_jkh"
                out["pred_authority_aspect"] = "not_applicable"
                out["pred_responsible_party"] = "not_applicable"
            split_out.append(out)
        routed[split] = split_out
    return routed


def evaluate(predictions: dict[str, list[dict[str, Any]]], gold_rows: list[dict[str, str]]) -> dict[str, Any]:
    label_sets = {axis: labels_for_axis(gold_rows, axis) for axis in TARGET_COLS}
    result: dict[str, Any] = {"splits": {}}
    for split, rows in predictions.items():
        split_result: dict[str, Any] = {}
        exact = 0
        for row in rows:
            if all(row[f"true_{axis}"] == row[f"pred_{axis}"] for axis in TARGET_COLS):
                exact += 1
        split_result["all_heads_exact_match"] = exact / max(len(rows), 1)
        macro_values = []
        for axis in TARGET_COLS:
            true_labels = [row[f"true_{axis}"] for row in rows]
            pred_labels = [row[f"pred_{axis}"] for row in rows]
            metrics = axis_metrics(true_labels, pred_labels, label_sets[axis])
            split_result[axis] = metrics
            macro_values.append(metrics["macro_f1"])
        split_result["mean_macro_f1"] = sum(macro_values) / max(len(macro_values), 1)
        result["splits"][split] = split_result
    return result


def write_report(output_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Routed ЖКХ-Internal Specialist Evaluation",
        "",
        "The cascade decides whether a row is ЖКХ-related. For predicted ЖКХ rows,",
        "`jkh_topic`, `authority_aspect`, and `responsible_party` are produced by",
        "the internal specialist. Non-ЖКХ rows are forced to the consistent labels.",
        "",
        "| Split | Mean macro-F1 | Strict all-8 exact match |",
        "| --- | ---: | ---: |",
    ]
    for split in ["val", "test"]:
        payload = result["splits"][split]
        lines.append(f"| `{split}` | {payload['mean_macro_f1']:.4f} | {payload['all_heads_exact_match']:.4f} |")
    lines += [
        "",
        "## Per-Axis Test Macro-F1",
        "",
        "| Axis | Test macro-F1 | Test accuracy |",
        "| --- | ---: | ---: |",
    ]
    for axis in TARGET_COLS:
        metrics = result["splits"]["test"][axis]
        lines.append(f"| `{axis}` | {metrics['macro_f1']:.4f} | {metrics['accuracy']:.4f} |")
    (output_dir / "routed_jkh_internal_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--cascade-dir", default=DEFAULT_CASCADE_DIR)
    parser.add_argument("--specialist-dir", default=DEFAULT_SPECIALIST_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(42)
    gold_rows = [row for row in read_csv(args.input_csv) if row.get("label_source") == "gold_human"]
    rows_by_split = {"val": split_rows(gold_rows, "val"), "test": split_rows(gold_rows, "test")}
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    specialist_predictions = predict_specialist(rows_by_split, Path(args.specialist_dir), args.batch_size, device)
    routed_predictions = build_routed_predictions(rows_by_split, Path(args.cascade_dir), specialist_predictions)
    result = evaluate(routed_predictions, gold_rows)

    fields = ["row_key", "record_id", "split", "route"]
    for axis in TARGET_COLS:
        fields += [f"true_{axis}", f"pred_{axis}", f"source_{axis}", f"confidence_{axis}"]
    for split, rows in routed_predictions.items():
        write_csv(output_dir / f"{split}_routed_predictions.csv", rows, fields)
    write_json(
        output_dir / "routed_jkh_internal_evaluation.json",
        {
            "input_csv": args.input_csv,
            "cascade_dir": args.cascade_dir,
            "specialist_dir": args.specialist_dir,
            "device": str(device),
            **result,
        },
    )
    write_report(output_dir, result)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "device": str(device),
                "test_mean_macro_f1": result["splits"]["test"]["mean_macro_f1"],
                "test_exact_match": result["splits"]["test"]["all_heads_exact_match"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
