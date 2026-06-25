#!/usr/bin/env python
"""Evaluate the best classifier on the full raw gold+silver labeled corpus."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import torch
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from train_rubert_multitask import MultiHeadRuBert, read_csv, set_seed  # noqa: E402


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_gold(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            yield {
                "row_id": f"gold:{row.get('annotation_id')}",
                "label_source": "gold_raw",
                "record_id": row.get("record_id", ""),
                "text": row.get("text", ""),
                "post_text": row.get("post_text", ""),
                **{col: row.get(col, "") for col in TARGET_COLS},
            }


def iter_silver(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            yield {
                "row_id": f"silver:{row.get('record_id')}",
                "label_source": "silver_auto",
                "record_id": row.get("record_id", ""),
                "text": row.get("comment_text", ""),
                "post_text": row.get("post_text", ""),
                **{col: row.get(col, "") for col in TARGET_COLS},
            }


def row_text(row: dict[str, Any], text_mode: str) -> str:
    text = str(row.get("text", ""))
    if text_mode == "post_comment":
        return f"[POST] {row.get('post_text', '')} [COMMENT] {text}"
    return text


def batched(iterator: Iterable[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in iterator:
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def update_confusions(
    counters: dict[str, dict[str, Counter[tuple[str, str]]]],
    row: dict[str, Any],
    predictions: dict[str, str],
) -> None:
    groups = ["all", row["label_source"]]
    for group in groups:
        for col in TARGET_COLS:
            true_label = str(row.get(col, "") or "__missing__")
            pred_label = predictions[col]
            counters[group][col][(true_label, pred_label)] += 1


def matrix_for_counter(
    counter: Counter[tuple[str, str]],
    model_order: list[str],
) -> tuple[list[str], list[list[int]]]:
    true_labels = {true for true, _ in counter}
    pred_labels = {pred for _, pred in counter}
    labels = list(model_order)
    for label in sorted((true_labels | pred_labels) - set(labels)):
        labels.append(label)
    index = {label: idx for idx, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for (true, pred), count in counter.items():
        matrix[index[true]][index[pred]] += int(count)
    return labels, matrix


def normalized(matrix: list[list[int]]) -> list[list[float]]:
    out: list[list[float]] = []
    for row in matrix:
        total = sum(row)
        if total:
            out.append([value / total for value in row])
        else:
            out.append([0.0 for _ in row])
    return out


def write_group_json(
    output: Path,
    group_name: str,
    rows: int,
    counters: dict[str, Counter[tuple[str, str]]],
    label_maps: dict[str, dict[str, int]],
    metadata: dict[str, Any],
) -> None:
    matrices: dict[str, Any] = {}
    for col in TARGET_COLS:
        model_order = [label for label, _ in sorted(label_maps[col].items(), key=lambda item: item[1])]
        labels, matrix = matrix_for_counter(counters[col], model_order)
        matrices[col] = {
            "labels": labels,
            "counts": matrix,
            "row_normalized": normalized(matrix),
        }
    payload = {
        "rows": rows,
        "group": group_name,
        "matrices": matrices,
        **metadata,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate(args: argparse.Namespace) -> None:
    set_seed(42)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    best_run = Path(args.best_run_dir)
    metrics = read_json(best_run / "metrics.json")
    label_maps = metrics["label_maps"]
    inverse_maps = {
        col: {idx: label for label, idx in mapping.items()}
        for col, mapping in label_maps.items()
    }

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer_path = best_run / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(label_maps[col]) for col in TARGET_COLS},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    state = torch.load(best_run / "model.pt", map_location=device)
    model.load_state_dict(state)
    model.eval()

    counters: dict[str, dict[str, Counter[tuple[str, str]]]] = defaultdict(lambda: {col: Counter() for col in TARGET_COLS})
    group_rows = Counter()
    prediction_path = output_dir / "full_corpus_predictions.csv"
    prediction_fields = (
        ["row_id", "label_source", "record_id"]
        + [f"true_{col}" for col in TARGET_COLS]
        + [f"pred_{col}" for col in TARGET_COLS]
    )

    gold_path = Path(args.gold_csv)
    silver_path = Path(args.silver_csv)
    full_iter = iter_gold(gold_path)
    full_iter = list(full_iter) if args.materialize else full_iter
    chained = iter_gold(gold_path)
    if args.only != "gold":
        if args.only == "silver":
            chained = iter_silver(silver_path)
        elif args.only == "all":
            def combined() -> Iterable[dict[str, Any]]:
                yield from iter_gold(gold_path)
                yield from iter_silver(silver_path)
            chained = combined()

    processed = 0
    with prediction_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=prediction_fields)
        writer.writeheader()
        for batch_idx, rows in enumerate(batched(chained, args.batch_size), 1):
            texts = [row_text(row, metrics["text_mode"]) for row in rows]
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
            for col in TARGET_COLS:
                pred_ids = torch.argmax(outputs[col], dim=1).cpu().tolist()
                batch_predictions[col] = [inverse_maps[col][idx] for idx in pred_ids]

            for row_idx, row in enumerate(rows):
                preds = {col: batch_predictions[col][row_idx] for col in TARGET_COLS}
                update_confusions(counters, row, preds)
                group_rows["all"] += 1
                group_rows[row["label_source"]] += 1
                writer.writerow(
                    {
                        "row_id": row["row_id"],
                        "label_source": row["label_source"],
                        "record_id": row["record_id"],
                        **{f"true_{col}": row.get(col, "") for col in TARGET_COLS},
                        **{f"pred_{col}": preds[col] for col in TARGET_COLS},
                    }
                )
            processed += len(rows)
            if args.log_every_batches and batch_idx % args.log_every_batches == 0:
                print(f"batches={batch_idx} rows={processed}", flush=True)

    metadata = {
        "device": str(device),
        "best_run_dir": str(best_run),
        "gold_csv": str(gold_path),
        "silver_csv": str(silver_path),
        "predictions_csv": str(prediction_path),
        "note": "Full-corpus matrices compare model predictions with available labels. Silver labels are automatic teacher labels, not human gold.",
    }
    for group in ["all", "gold_raw", "silver_auto"]:
        if group_rows[group]:
            write_group_json(
                output_dir / f"confusion_matrices_{group}.json",
                group,
                group_rows[group],
                counters[group],
                label_maps,
                metadata,
            )

    summary = {
        "processed_rows": processed,
        "group_rows": dict(group_rows),
        "prediction_path": str(prediction_path),
        "json_outputs": [str(path) for path in sorted(output_dir.glob("confusion_matrices_*.json"))],
        "note": metadata["note"],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-csv", default="data/exports/teacher_student_full_export_2026-06-03_01-06/01_gold_approved_annotations.csv")
    parser.add_argument("--silver-csv", default="data/exports/teacher_student_full_export_2026-06-03_01-06/06_silver_auto_labeled_all.csv")
    parser.add_argument("--best-run-dir", default="data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4")
    parser.add_argument("--output-dir", default="data/exports/full_corpus_confusions_2026-06-03")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--log-every-batches", type=int, default=100)
    parser.add_argument("--only", choices=["all", "gold", "silver"], default="all")
    parser.add_argument("--materialize", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    evaluate(parse_args())
