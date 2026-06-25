#!/usr/bin/env python
"""Select the best available taxonomy model per axis and evaluate the final hybrid.

The script does not train a new model. It audits all useful checkpoints produced
during the project, chooses each taxonomy axis by human-gold validation macro-F1,
then evaluates the selected hybrid on the untouched human-gold test split.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from sklearn.metrics import accuracy_score, classification_report, f1_score
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

DEFAULT_INPUT_CSV = "data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_only_fixed_split.csv"
DEFAULT_OUTPUT_DIR = "data/ml_experiments/final_taxonomy_ensemble_2026-06-06"


@dataclass(frozen=True)
class CheckpointCandidate:
    name: str
    checkpoint_dir: Path


CHECKPOINT_CANDIDATES = [
    CheckpointCandidate(
        "original_best_all8",
        Path("data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4"),
    ),
    CheckpointCandidate(
        "no_sample_balanced_full",
        Path("data/ml_experiments/no_sample_weight_class_sweep_2026-06-05/no_sample_balanced_full"),
    ),
    CheckpointCandidate(
        "pseudo_gold_all8_e2",
        Path("data/ml_experiments/pseudo_gold_2026-06-06_v2/runs/all8_pseudogold_screen_e2"),
    ),
    CheckpointCandidate(
        "pseudo_gold_jkh_topic_specialist",
        Path("data/ml_experiments/pseudo_gold_2026-06-06_v2/runs/specialist_jkh_topic_e2"),
    ),
    CheckpointCandidate(
        "pseudo_gold_authority_specialist",
        Path("data/ml_experiments/pseudo_gold_2026-06-06_v2/runs/specialist_authority_aspect_e3"),
    ),
    CheckpointCandidate(
        "pseudo_gold_appeal_specialist",
        Path("data/ml_experiments/pseudo_gold_2026-06-06_v2/runs/specialist_appeal_type_e2"),
    ),
    CheckpointCandidate(
        "pseudo_gold_responsible_specialist",
        Path("data/ml_experiments/pseudo_gold_2026-06-06_v2/runs/specialist_responsible_party_e3"),
    ),
    CheckpointCandidate(
        "gold_jkh_topic_specialist",
        Path("data/ml_experiments/gold_specialists_2026-06-06/gold_jkh_topic_e8"),
    ),
    CheckpointCandidate(
        "gold_authority_specialist",
        Path("data/ml_experiments/gold_specialists_2026-06-06/gold_authority_aspect_e8"),
    ),
    CheckpointCandidate(
        "gold_appeal_specialist",
        Path("data/ml_experiments/gold_specialists_2026-06-06/gold_appeal_type_e8"),
    ),
    CheckpointCandidate(
        "gold_responsible_specialist",
        Path("data/ml_experiments/gold_specialists_2026-06-06/gold_responsible_party_e8"),
    ),
]

CASCADE_PREDICTIONS = {
    "val": Path("data/ml_experiments/cascade_eval_2026-06-06_01-48/val_cascade_predictions.csv"),
    "test": Path("data/ml_experiments/cascade_eval_2026-06-06_01-48/test_cascade_predictions.csv"),
}


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


def row_key(row: dict[str, str], fallback_index: int) -> str:
    return row.get("row_id") or row.get("record_id") or str(fallback_index)


def row_text(row: dict[str, str], text_mode: str) -> str:
    text = str(row.get("text", ""))
    if text_mode == "post_comment":
        return f"[POST] {row.get('post_text', '')} [COMMENT] {text}"
    return text


def batched(rows: list[dict[str, str]], batch_size: int):
    for start in range(0, len(rows), batch_size):
        yield start, rows[start : start + batch_size]


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


def predict_checkpoint(
    candidate: CheckpointCandidate,
    rows_by_split: dict[str, list[dict[str, str]]],
    output_dir: Path,
    batch_size: int,
    device: torch.device,
) -> dict[str, list[dict[str, Any]]]:
    prediction_dir = output_dir / "checkpoint_predictions" / candidate.name
    metrics_path = candidate.checkpoint_dir / "metrics.json"
    model_path = candidate.checkpoint_dir / "model.pt"
    if not metrics_path.exists() or not model_path.exists():
        return {}

    cached: dict[str, list[dict[str, Any]]] = {}
    cache_ok = True
    for split in rows_by_split:
        cache_path = prediction_dir / f"{split}.csv"
        if cache_path.exists():
            cached[split] = read_csv(cache_path)
        else:
            cache_ok = False
    if cache_ok:
        return cached

    metrics, tokenizer, model = load_checkpoint(candidate.checkpoint_dir, device)
    target_cols = metrics["target_cols"]
    inverse_maps = {
        col: {idx: label for label, idx in label_map.items()}
        for col, label_map in metrics["label_maps"].items()
    }

    all_predictions: dict[str, list[dict[str, Any]]] = {}
    with torch.no_grad():
        for split, rows in rows_by_split.items():
            split_predictions: list[dict[str, Any]] = [
                {
                    "row_key": row_key(row, idx),
                    "record_id": row.get("record_id", ""),
                    "split": split,
                }
                for idx, row in enumerate(rows)
            ]
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
                        split_predictions[start + offset][f"pred_{col}"] = inverse_maps[col][pred_idx]
                        split_predictions[start + offset][f"confidence_{col}"] = float(probs[pred_idx].item())
            all_predictions[split] = split_predictions
            fields = ["row_key", "record_id", "split"]
            for col in target_cols:
                fields += [f"pred_{col}", f"confidence_{col}"]
            write_csv(prediction_dir / f"{split}.csv", split_predictions, fields)

    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return all_predictions


def load_cascade_predictions() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for split, path in CASCADE_PREDICTIONS.items():
        if not path.exists():
            continue
        rows = []
        for idx, row in enumerate(read_csv(path)):
            out_row = {
                "row_key": row_key(row, idx),
                "record_id": row.get("record_id", ""),
                "split": split,
            }
            for col in TARGET_COLS:
                if row.get(f"final_{col}"):
                    out_row[f"pred_{col}"] = row[f"final_{col}"]
                if row.get(f"pred_{col}_confidence"):
                    out_row[f"confidence_{col}"] = row[f"pred_{col}_confidence"]
            rows.append(out_row)
        out[split] = rows
    return out


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


def evaluate_candidate(
    candidate_name: str,
    predictions: dict[str, list[dict[str, Any]]],
    rows_by_split: dict[str, list[dict[str, str]]],
    label_sets: dict[str, list[str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {"candidate": candidate_name, "splits": {}}
    for split, rows in rows_by_split.items():
        pred_by_key = {row["row_key"]: row for row in predictions.get(split, [])}
        split_result: dict[str, Any] = {}
        for axis in TARGET_COLS:
            true_labels: list[str] = []
            pred_labels: list[str] = []
            for idx, row in enumerate(rows):
                key = row_key(row, idx)
                pred = pred_by_key.get(key, {}).get(f"pred_{axis}", "")
                if not pred:
                    continue
                true_labels.append(row[axis])
                pred_labels.append(str(pred))
            if len(true_labels) == len(rows):
                split_result[axis] = axis_metrics(true_labels, pred_labels, label_sets[axis])
        result["splits"][split] = split_result
    return result


def apply_consistency(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    out = dict(row)
    rules: list[str] = []
    if out.get("pred_jkh_relevance") == "no":
        for axis, label in [
            ("jkh_topic", "not_jkh"),
            ("authority_aspect", "not_applicable"),
            ("responsible_party", "not_applicable"),
        ]:
            key = f"pred_{axis}"
            if out.get(key) != label:
                out[key] = label
                rules.append(f"jkh_no_forces_{axis}")
    if out.get("pred_jkh_relevance") == "yes" and out.get("pred_jkh_topic") == "not_jkh":
        out["pred_jkh_topic"] = "other_jkh"
        rules.append("jkh_yes_not_jkh_to_other_jkh")
    return out, rules


def build_hybrid_predictions(
    selected_sources: dict[str, str],
    all_predictions: dict[str, dict[str, list[dict[str, Any]]]],
    rows_by_split: dict[str, list[dict[str, str]]],
    apply_rules: bool,
) -> dict[str, list[dict[str, Any]]]:
    hybrid: dict[str, list[dict[str, Any]]] = {}
    indexed = {
        name: {
            split: {row["row_key"]: row for row in split_rows}
            for split, split_rows in predictions.items()
        }
        for name, predictions in all_predictions.items()
    }
    for split, rows in rows_by_split.items():
        out_rows: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            key = row_key(row, idx)
            out = {
                "row_key": key,
                "record_id": row.get("record_id", ""),
                "split": split,
            }
            for axis in TARGET_COLS:
                source = selected_sources[axis]
                source_row = indexed[source][split][key]
                out[f"true_{axis}"] = row[axis]
                out[f"pred_{axis}"] = source_row[f"pred_{axis}"]
                out[f"source_{axis}"] = source
                out[f"confidence_{axis}"] = source_row.get(f"confidence_{axis}", "")
            if apply_rules:
                out, rules = apply_consistency(out)
                out["consistency_rules"] = ";".join(rules)
            else:
                out["consistency_rules"] = ""
            out_rows.append(out)
        hybrid[split] = out_rows
    return hybrid


def evaluate_hybrid(
    predictions: dict[str, list[dict[str, Any]]],
    label_sets: dict[str, list[str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {"splits": {}}
    for split, rows in predictions.items():
        split_result: dict[str, Any] = {}
        exact = 0
        for row in rows:
            if all(row[f"true_{axis}"] == row[f"pred_{axis}"] for axis in TARGET_COLS):
                exact += 1
        split_result["all_heads_exact_match"] = exact / max(len(rows), 1)
        axis_macro_values = []
        for axis in TARGET_COLS:
            true_labels = [row[f"true_{axis}"] for row in rows]
            pred_labels = [row[f"pred_{axis}"] for row in rows]
            metrics = axis_metrics(true_labels, pred_labels, label_sets[axis])
            split_result[axis] = metrics
            axis_macro_values.append(metrics["macro_f1"])
        split_result["mean_macro_f1"] = sum(axis_macro_values) / max(len(axis_macro_values), 1)
        result["splits"][split] = split_result
    return result


def rows_for_summary(candidate_results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate, payload in sorted(candidate_results.items()):
        for axis in TARGET_COLS:
            val_metric = payload.get("splits", {}).get("val", {}).get(axis, {})
            test_metric = payload.get("splits", {}).get("test", {}).get(axis, {})
            if not val_metric:
                continue
            rows.append(
                {
                    "candidate": candidate,
                    "axis": axis,
                    "val_macro_f1": val_metric.get("macro_f1"),
                    "test_macro_f1": test_metric.get("macro_f1"),
                    "val_accuracy": val_metric.get("accuracy"),
                    "test_accuracy": test_metric.get("accuracy"),
                }
            )
    return rows


def write_report(
    output_dir: Path,
    selected_sources: dict[str, str],
    candidate_results: dict[str, Any],
    hybrid_raw: dict[str, Any],
    hybrid_rules: dict[str, Any],
) -> None:
    lines = [
        "# Final Taxonomy Ensemble Evaluation",
        "",
        "Evaluation is performed on fixed human-gold validation/test splits.",
        "Pseudo-gold and silver rows are never used for validation/test.",
        "",
        "## Selected Sources",
        "",
        "| Axis | Selected source by validation macro-F1 | Val macro-F1 | Test macro-F1 |",
        "| --- | --- | ---: | ---: |",
    ]
    for axis in TARGET_COLS:
        source = selected_sources[axis]
        val_f1 = candidate_results[source]["splits"]["val"][axis]["macro_f1"]
        test_f1 = candidate_results[source]["splits"]["test"][axis]["macro_f1"]
        lines.append(f"| `{axis}` | `{source}` | {val_f1:.4f} | {test_f1:.4f} |")

    lines += [
        "",
        "## Hybrid Result",
        "",
        "| Variant | Split | Mean macro-F1 | Strict all-8 exact match |",
        "| --- | --- | ---: | ---: |",
    ]
    for name, payload in [("raw", hybrid_raw), ("with_consistency_rules", hybrid_rules)]:
        for split in ["val", "test"]:
            split_payload = payload["splits"][split]
            lines.append(
                f"| `{name}` | `{split}` | {split_payload['mean_macro_f1']:.4f} | "
                f"{split_payload['all_heads_exact_match']:.4f} |"
            )

    lines += [
        "",
        "## Per-Axis Test Macro-F1 With Consistency Rules",
        "",
        "| Axis | Test macro-F1 | Test accuracy |",
        "| --- | ---: | ---: |",
    ]
    for axis in TARGET_COLS:
        metrics = hybrid_rules["splits"]["test"][axis]
        lines.append(f"| `{axis}` | {metrics['macro_f1']:.4f} | {metrics['accuracy']:.4f} |")

    (output_dir / "final_taxonomy_ensemble_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(42)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gold_rows = [row for row in read_csv(args.input_csv) if row.get("label_source") == "gold_human"]
    rows_by_split = {"val": split_rows(gold_rows, "val"), "test": split_rows(gold_rows, "test")}
    label_sets = {axis: labels_for_axis(gold_rows, axis) for axis in TARGET_COLS}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    all_predictions: dict[str, dict[str, list[dict[str, Any]]]] = {
        "cascade_consistency": load_cascade_predictions()
    }
    for candidate in CHECKPOINT_CANDIDATES:
        predictions = predict_checkpoint(candidate, rows_by_split, output_dir, args.batch_size, device)
        if predictions:
            all_predictions[candidate.name] = predictions

    candidate_results = {
        name: evaluate_candidate(name, predictions, rows_by_split, label_sets)
        for name, predictions in all_predictions.items()
    }

    selected_sources: dict[str, str] = {}
    for axis in TARGET_COLS:
        available = [
            (name, result["splits"].get("val", {}).get(axis, {}).get("macro_f1", -1.0))
            for name, result in candidate_results.items()
        ]
        available = [(name, value) for name, value in available if value >= 0]
        if not available:
            raise SystemExit(f"No predictions available for axis {axis}")
        selected_sources[axis] = max(available, key=lambda item: item[1])[0]

    hybrid_raw_predictions = build_hybrid_predictions(selected_sources, all_predictions, rows_by_split, apply_rules=False)
    hybrid_rules_predictions = build_hybrid_predictions(selected_sources, all_predictions, rows_by_split, apply_rules=True)
    hybrid_raw = evaluate_hybrid(hybrid_raw_predictions, label_sets)
    hybrid_rules = evaluate_hybrid(hybrid_rules_predictions, label_sets)

    fields = ["row_key", "record_id", "split", "consistency_rules"]
    for axis in TARGET_COLS:
        fields += [f"true_{axis}", f"pred_{axis}", f"source_{axis}", f"confidence_{axis}"]
    for split, rows in hybrid_rules_predictions.items():
        write_csv(output_dir / f"{split}_final_hybrid_predictions.csv", rows, fields)

    write_csv(
        output_dir / "candidate_axis_summary.csv",
        rows_for_summary(candidate_results),
        ["candidate", "axis", "val_macro_f1", "test_macro_f1", "val_accuracy", "test_accuracy"],
    )
    write_json(
        output_dir / "final_taxonomy_ensemble_evaluation.json",
        {
            "input_csv": args.input_csv,
            "device": str(device),
            "selected_sources": selected_sources,
            "candidate_results": candidate_results,
            "hybrid_raw": hybrid_raw,
            "hybrid_with_consistency_rules": hybrid_rules,
        },
    )
    write_report(output_dir, selected_sources, candidate_results, hybrid_raw, hybrid_rules)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "device": str(device),
                "selected_sources": selected_sources,
                "test_mean_macro_f1_raw": hybrid_raw["splits"]["test"]["mean_macro_f1"],
                "test_mean_macro_f1_with_rules": hybrid_rules["splits"]["test"]["mean_macro_f1"],
                "test_exact_match_with_rules": hybrid_rules["splits"]["test"]["all_heads_exact_match"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
