#!/usr/bin/env python
"""Evaluate the full cascade: taxonomy heads plus an OMSU rating head."""

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

from omsu_scoring import calculate_omsu_score  # noqa: E402
from train_rubert_multitask import MultiHeadRuBert, read_csv, set_seed  # noqa: E402


DEFAULT_INPUT_CSV = (
    "data/ml_experiments/omsu_score_2026-06-06/"
    "dataset_gold_silver_omsu_fixed_split.csv"
)
DEFAULT_TAXONOMY_CHECKPOINT = (
    "data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/"
    "final_w03_weighted_lr1e5_e4"
)
DEFAULT_OMSU_CHECKPOINT = (
    "data/ml_experiments/omsu_score_2026-06-06/threshold/"
    "negative_signal_capped_20k"
)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def row_text(row: dict[str, str], text_mode: str) -> str:
    text = str(row.get("text", ""))
    if text_mode == "post_comment":
        return f"[POST] {row.get('post_text', '')} [COMMENT] {text}"
    return text


def batched(rows: list[dict[str, str]], batch_size: int):
    for start in range(0, len(rows), batch_size):
        yield start, rows[start : start + batch_size]


def split_rows(rows: list[dict[str, str]], split: str) -> list[dict[str, str]]:
    return [row for row in rows if str(row.get("split", "")).strip().lower() == split]


def labels_in_order(label_map: dict[str, int]) -> list[str]:
    return [label for label, _ in sorted(label_map.items(), key=lambda item: item[1])]


def load_checkpoint(checkpoint_dir: Path, device: torch.device) -> tuple[dict[str, Any], Any, MultiHeadRuBert]:
    metrics = json.loads((checkpoint_dir / "metrics.json").read_text(encoding="utf-8"))
    tokenizer_path = checkpoint_dir / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    target_cols = metrics["target_cols"]
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(metrics["label_maps"][col]) for col in target_cols},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    model.load_state_dict(torch.load(checkpoint_dir / "model.pt", map_location=device))
    model.eval()
    return metrics, tokenizer, model


def predict_heads(
    rows: list[dict[str, str]],
    checkpoint_dir: Path,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics, tokenizer, model = load_checkpoint(checkpoint_dir, device)
    target_cols = metrics["target_cols"]
    inverse_maps = {
        col: {idx: label for label, idx in label_map.items()}
        for col, label_map in metrics["label_maps"].items()
    }
    predictions: list[dict[str, Any]] = [
        {
            "_row_pos": idx,
            "row_id": row.get("row_id", ""),
            "record_id": row.get("record_id", ""),
            "label_source": row.get("label_source", ""),
            "split": row.get("split", ""),
        }
        for idx, row in enumerate(rows)
    ]

    with torch.no_grad():
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
            for col in target_cols:
                probabilities = torch.softmax(outputs[col], dim=1).detach().cpu()
                for offset, probs in enumerate(probabilities):
                    pred_idx = int(torch.argmax(probs).item())
                    predictions[start + offset][f"pred_{col}"] = inverse_maps[col][pred_idx]
                    predictions[start + offset][f"pred_{col}_confidence"] = float(probs[pred_idx].item())

    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return metrics, predictions


def predict_binary_probability(
    rows: list[dict[str, str]],
    checkpoint_dir: Path,
    target_col: str,
    positive_label: str,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics, tokenizer, model = load_checkpoint(checkpoint_dir, device)
    if target_col not in metrics["target_cols"]:
        raise ValueError(f"{target_col} is not present in checkpoint target columns.")
    label_map = metrics["label_maps"][target_col]
    inverse_map = {idx: label for label, idx in label_map.items()}
    positive_idx = label_map[positive_label]
    predictions: list[dict[str, Any]] = [
        {
            "_row_pos": idx,
            "argmax_pred": "",
            "positive_probability": 0.0,
        }
        for idx, _row in enumerate(rows)
    ]

    with torch.no_grad():
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
            probabilities = torch.softmax(
                model(input_ids=input_ids, attention_mask=attention_mask)[target_col],
                dim=1,
            ).detach().cpu()
            for offset, probs in enumerate(probabilities):
                pred_idx = int(torch.argmax(probs).item())
                predictions[start + offset]["argmax_pred"] = inverse_map[pred_idx]
                predictions[start + offset]["positive_probability"] = float(probs[positive_idx].item())

    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return metrics, predictions


def class_metrics(true_labels: list[str], pred_labels: list[str], labels: list[str]) -> dict[str, Any]:
    return {
        "accuracy": accuracy_score(true_labels, pred_labels),
        "macro_f1": f1_score(true_labels, pred_labels, average="macro", zero_division=0),
        "macro_f1_all_labels": f1_score(true_labels, pred_labels, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(true_labels, pred_labels, labels=labels, average="weighted", zero_division=0),
        "report": classification_report(
            true_labels,
            pred_labels,
            labels=labels,
            target_names=labels,
            output_dict=True,
            zero_division=0,
        ),
    }


def omsu_decision(probability: float, negative_threshold: float, nonnegative_threshold: float) -> tuple[str, str, float]:
    if probability >= negative_threshold:
        return "negative_omsu", "high_negative", 1.0
    if probability <= nonnegative_threshold:
        return "not_negative_omsu", "high_not_negative", 1.0
    return "low_confidence", "low_confidence", 0.0


def evaluate_selective(
    rows: list[dict[str, Any]],
    positive_label: str,
    negative_label: str,
) -> dict[str, Any]:
    accepted = [row for row in rows if row["omsu_decision"] != "low_confidence"]
    labels = [positive_label, negative_label]
    if not accepted:
        return {
            "rows_total": len(rows),
            "rows_accepted": 0,
            "rows_low_confidence": len(rows),
            "coverage": 0.0,
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "negative_f1": 0.0,
            "negative_precision": 0.0,
            "negative_recall": 0.0,
        }
    true_labels = [row["true_omsu_negative_signal"] for row in accepted]
    pred_labels = [row["omsu_decision"] for row in accepted]
    report = classification_report(
        true_labels,
        pred_labels,
        labels=labels,
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "rows_total": len(rows),
        "rows_accepted": len(accepted),
        "rows_low_confidence": len(rows) - len(accepted),
        "coverage": len(accepted) / max(len(rows), 1),
        "accuracy": accuracy_score(true_labels, pred_labels),
        "macro_f1": f1_score(true_labels, pred_labels, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(true_labels, pred_labels, labels=labels, average="weighted", zero_division=0),
        "negative_f1": report[positive_label]["f1-score"],
        "negative_precision": report[positive_label]["precision"],
        "negative_recall": report[positive_label]["recall"],
        "negative_support": report[positive_label]["support"],
        "report": report,
    }


def apply_taxonomy_consistency_rules(pred_taxonomy_row: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    adjusted = dict(pred_taxonomy_row)
    rules: list[str] = []
    if adjusted.get("jkh_relevance") == "no":
        if adjusted.get("jkh_topic") != "not_jkh":
            adjusted["jkh_topic"] = "not_jkh"
            rules.append("jkh_relevance=no -> jkh_topic=not_jkh")
        if adjusted.get("authority_aspect") != "not_applicable":
            adjusted["authority_aspect"] = "not_applicable"
            rules.append("jkh_relevance=no -> authority_aspect=not_applicable")
        if adjusted.get("responsible_party") != "not_applicable":
            adjusted["responsible_party"] = "not_applicable"
            rules.append("jkh_relevance=no -> responsible_party=not_applicable")
    return adjusted, rules


def build_cascade_rows(
    source_rows: list[dict[str, str]],
    taxonomy_predictions: list[dict[str, Any]],
    omsu_predictions: list[dict[str, Any]],
    taxonomy_cols: list[str],
    negative_threshold: float,
    nonnegative_threshold: float,
    apply_consistency_rules: bool,
) -> list[dict[str, Any]]:
    output_rows: list[dict[str, Any]] = []
    for source, taxonomy_pred, omsu_pred in zip(source_rows, taxonomy_predictions, omsu_predictions):
        raw_pred_taxonomy_row = {col: taxonomy_pred[f"pred_{col}"] for col in taxonomy_cols}
        if apply_consistency_rules:
            pred_taxonomy_row, postprocess_rules = apply_taxonomy_consistency_rules(raw_pred_taxonomy_row)
        else:
            pred_taxonomy_row = raw_pred_taxonomy_row
            postprocess_rules = []
        true_score = calculate_omsu_score(source)
        pred_score = calculate_omsu_score(pred_taxonomy_row)
        probability = float(omsu_pred["positive_probability"])
        decision, band, rating_weight = omsu_decision(
            probability,
            negative_threshold,
            nonnegative_threshold,
        )
        out: dict[str, Any] = {
            "row_id": source.get("row_id", ""),
            "record_id": source.get("record_id", ""),
            "label_source": source.get("label_source", ""),
            "split": source.get("split", ""),
            "text": source.get("text", ""),
            "post_text": source.get("post_text", ""),
            "true_omsu_score": true_score.score,
            "pred_omsu_score": pred_score.score,
            "true_omsu_impact_class": true_score.impact_class,
            "pred_omsu_impact_class": pred_score.impact_class,
            "true_omsu_negative_signal": source.get("omsu_negative_signal", true_score.negative_signal),
            "argmax_omsu_negative_signal": omsu_pred["argmax_pred"],
            "omsu_negative_probability": probability,
            "omsu_decision": decision,
            "omsu_confidence_band": band,
            "omsu_rating_weight": rating_weight,
            "pred_omsu_score_reason": pred_score.reason,
            "taxonomy_postprocess_rules": "; ".join(postprocess_rules),
        }
        for col in taxonomy_cols:
            out[f"true_{col}"] = source.get(col, "")
            out[f"pred_{col}"] = taxonomy_pred[f"pred_{col}"]
            out[f"final_{col}"] = pred_taxonomy_row[col]
            out[f"pred_{col}_confidence"] = taxonomy_pred[f"pred_{col}_confidence"]
        output_rows.append(out)
    return output_rows


def evaluate_split(
    rows: list[dict[str, Any]],
    taxonomy_metrics: dict[str, Any],
    taxonomy_cols: list[str],
    positive_label: str,
    negative_label: str,
    threshold: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rows": len(rows),
        "taxonomy": {},
        "omsu": {},
    }
    exact_matches = 0
    for row in rows:
        if all(row[f"true_{col}"] == row[f"final_{col}"] for col in taxonomy_cols):
            exact_matches += 1
    result["taxonomy"]["all_heads_exact_match"] = exact_matches / max(len(rows), 1)

    for col in taxonomy_cols:
        labels = labels_in_order(taxonomy_metrics["label_maps"][col])
        result["taxonomy"][col] = class_metrics(
            [row[f"true_{col}"] for row in rows],
            [row[f"final_{col}"] for row in rows],
            labels,
        )

    labels = [positive_label, negative_label]
    true_omsu = [row["true_omsu_negative_signal"] for row in rows]
    result["omsu"]["argmax"] = class_metrics(
        true_omsu,
        [row["argmax_omsu_negative_signal"] for row in rows],
        labels,
    )
    result["omsu"][f"threshold_{threshold:.2f}"] = class_metrics(
        true_omsu,
        [
            positive_label if float(row["omsu_negative_probability"]) >= threshold else negative_label
            for row in rows
        ],
        labels,
    )
    result["omsu"]["selective"] = evaluate_selective(rows, positive_label, negative_label)

    abs_errors = [abs(int(row["true_omsu_score"]) - int(row["pred_omsu_score"])) for row in rows]
    result["omsu"]["score_from_predicted_axes"] = {
        "mean_absolute_error": sum(abs_errors) / max(len(abs_errors), 1),
        "within_10": sum(1 for value in abs_errors if value <= 10) / max(len(abs_errors), 1),
        "within_20": sum(1 for value in abs_errors if value <= 20) / max(len(abs_errors), 1),
    }
    return result


def write_report(path: Path, result: dict[str, Any], taxonomy_cols: list[str], threshold: float) -> None:
    lines = [
        "# Cascade Evaluation",
        "",
        f"- input: `{result['input_csv']}`",
        f"- taxonomy checkpoint: `{result['taxonomy_checkpoint']}`",
        f"- OMSU checkpoint: `{result['omsu_checkpoint']}`",
        f"- device: `{result['device']}`",
        f"- taxonomy consistency rules: `{result['consistency_rules_enabled']}`",
        f"- selective policy: `negative >= {result['negative_threshold']:.2f}`, "
        f"`not_negative <= {result['nonnegative_threshold']:.2f}`, otherwise `low_confidence`",
        "",
    ]
    for split in ["val", "test"]:
        split_result = result["splits"][split]
        selective = split_result["omsu"]["selective"]
        threshold_metric = split_result["omsu"][f"threshold_{threshold:.2f}"]
        lines += [
            f"## {split}",
            "",
            "### Taxonomy Heads",
            "",
            "| Axis | Accuracy | Macro-F1 | Weighted-F1 |",
            "| --- | ---: | ---: | ---: |",
        ]
        for col in taxonomy_cols:
            item = split_result["taxonomy"][col]
            lines.append(
                f"| `{col}` | {item['accuracy']:.4f} | {item['macro_f1']:.4f} | {item['weighted_f1']:.4f} |"
            )
        lines += [
            "",
            f"- all 8 heads exact match: `{split_result['taxonomy']['all_heads_exact_match']:.4f}`",
            "",
            "### OMSU Layer",
            "",
            "| Mode | Coverage | Accuracy | Macro-F1 | Weighted-F1 | Negative F1 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            (
                f"| argmax | 1.0000 | {split_result['omsu']['argmax']['accuracy']:.4f} | "
                f"{split_result['omsu']['argmax']['macro_f1']:.4f} | "
                f"{split_result['omsu']['argmax']['weighted_f1']:.4f} | "
                f"{split_result['omsu']['argmax']['report']['negative_omsu']['f1-score']:.4f} |"
            ),
            (
                f"| threshold {threshold:.2f} | 1.0000 | {threshold_metric['accuracy']:.4f} | "
                f"{threshold_metric['macro_f1']:.4f} | {threshold_metric['weighted_f1']:.4f} | "
                f"{threshold_metric['report']['negative_omsu']['f1-score']:.4f} |"
            ),
            (
                f"| selective | {selective['coverage']:.4f} | {selective['accuracy']:.4f} | "
                f"{selective['macro_f1']:.4f} | {selective['weighted_f1']:.4f} | "
                f"{selective['negative_f1']:.4f} |"
            ),
            "",
            "### Numeric Score From Predicted Axes",
            "",
            f"- mean absolute error: `{split_result['omsu']['score_from_predicted_axes']['mean_absolute_error']:.2f}`",
            f"- within 10 points: `{split_result['omsu']['score_from_predicted_axes']['within_10']:.4f}`",
            f"- within 20 points: `{split_result['omsu']['score_from_predicted_axes']['within_20']:.4f}`",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--taxonomy-checkpoint", default=DEFAULT_TAXONOMY_CHECKPOINT)
    parser.add_argument("--omsu-checkpoint", default=DEFAULT_OMSU_CHECKPOINT)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--omsu-batch-size", type=int, default=64)
    parser.add_argument("--positive-label", default="negative_omsu")
    parser.add_argument("--negative-label", default="not_negative_omsu")
    parser.add_argument("--negative-threshold", type=float, default=0.85)
    parser.add_argument("--nonnegative-threshold", type=float, default=0.15)
    parser.add_argument("--single-threshold", type=float, default=0.69)
    parser.add_argument(
        "--no-consistency-rules",
        action="store_true",
        help="Disable deterministic taxonomy consistency rules.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(42)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_csv(args.input_csv)
    rows = [row for row in rows if row.get("split") in {"val", "test"}]
    if not rows:
        raise SystemExit("No validation/test rows found.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    taxonomy_metrics, taxonomy_predictions = predict_heads(
        rows,
        Path(args.taxonomy_checkpoint),
        device,
        args.batch_size,
    )
    taxonomy_cols = taxonomy_metrics["target_cols"]
    _omsu_metrics, omsu_predictions = predict_binary_probability(
        rows,
        Path(args.omsu_checkpoint),
        "omsu_negative_signal",
        args.positive_label,
        device,
        args.omsu_batch_size,
    )

    cascade_rows = build_cascade_rows(
        rows,
        taxonomy_predictions,
        omsu_predictions,
        taxonomy_cols,
        args.negative_threshold,
        args.nonnegative_threshold,
        not args.no_consistency_rules,
    )

    fieldnames = [
        "row_id",
        "record_id",
        "label_source",
        "split",
        "true_omsu_score",
        "pred_omsu_score",
        "true_omsu_impact_class",
        "pred_omsu_impact_class",
        "true_omsu_negative_signal",
        "argmax_omsu_negative_signal",
        "omsu_negative_probability",
        "omsu_decision",
        "omsu_confidence_band",
        "omsu_rating_weight",
        "pred_omsu_score_reason",
        "taxonomy_postprocess_rules",
    ]
    for col in taxonomy_cols:
        fieldnames += [f"true_{col}", f"pred_{col}", f"final_{col}", f"pred_{col}_confidence"]
    fieldnames += ["post_text", "text"]

    result = {
        "input_csv": args.input_csv,
        "taxonomy_checkpoint": args.taxonomy_checkpoint,
        "omsu_checkpoint": args.omsu_checkpoint,
        "device": str(device),
        "negative_threshold": args.negative_threshold,
        "nonnegative_threshold": args.nonnegative_threshold,
        "single_threshold": args.single_threshold,
        "consistency_rules_enabled": not args.no_consistency_rules,
        "target_cols": taxonomy_cols,
        "splits": {},
    }

    for split in ["val", "test"]:
        split_rows_out = [row for row in cascade_rows if row["split"] == split]
        write_csv(output_dir / f"{split}_cascade_predictions.csv", split_rows_out, fieldnames)
        result["splits"][split] = evaluate_split(
            split_rows_out,
            taxonomy_metrics,
            taxonomy_cols,
            args.positive_label,
            args.negative_label,
            args.single_threshold,
        )

    write_json(output_dir / "cascade_evaluation.json", result)
    write_report(output_dir / "cascade_evaluation.md", result, taxonomy_cols, args.single_threshold)
    print(output_dir / "cascade_evaluation.md")


if __name__ == "__main__":
    main()
