#!/usr/bin/env python
"""Build a high-confidence diamond layer from automatic silver labels.

Diamond rows are still not human gold. They are selected silver rows that pass
extra checks: label consistency, model agreement, confidence scoring, and
balanced selection pressure so non-JKH records do not dominate the trusted layer.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from train_rubert_multitask import (  # noqa: E402
    MultiHeadRuBert,
    TextMultiTaskDataset,
    read_csv,
    set_seed,
)


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

CORE_COLS = ["jkh_relevance", "jkh_topic", "quality"]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def label_maps_from_metrics(metrics: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {col: {str(k): int(v) for k, v in mapping.items()} for col, mapping in metrics["label_maps"].items()}


def inverse_maps(label_maps: dict[str, dict[str, int]]) -> dict[str, dict[int, str]]:
    return {col: {idx: label for label, idx in mapping.items()} for col, mapping in label_maps.items()}


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("record_id", "")).strip()


def load_audited_ids(paths: list[str]) -> set[str]:
    ids: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rid = row_id(row)
                action = str(row.get("offline_action", "")).strip()
                if rid and action in {"approve", "deleted_confirm"}:
                    ids.add(rid)
    return ids


def logic_issues(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    relevance = row.get("jkh_relevance", "")
    topic = row.get("jkh_topic", "")
    aspect = row.get("authority_aspect", "")
    party = row.get("responsible_party", "")
    quality = row.get("quality", "")

    if relevance == "no":
        if topic != "not_jkh":
            issues.append("non_jkh_topic_not_normalized")
        if aspect != "not_applicable":
            issues.append("non_jkh_authority_not_normalized")
        if party != "not_applicable":
            issues.append("non_jkh_party_not_normalized")
    if relevance == "yes" and topic == "not_jkh":
        issues.append("jkh_yes_but_topic_not_jkh")
    if quality in {"spam", "duplicate"} and relevance == "yes" and topic != "not_jkh":
        issues.append("low_quality_with_specific_jkh_topic")
    return issues


def stable_weight(score: float, agree_heads: int, audited: bool, args: argparse.Namespace) -> float:
    if audited:
        return args.audited_diamond_weight
    if score >= 0.82 and agree_heads >= 7:
        return args.high_diamond_weight
    if score >= 0.72 and agree_heads >= 6:
        return args.mid_diamond_weight
    return args.low_diamond_weight


def model_score_rows(args: argparse.Namespace, silver_rows: list[dict[str, Any]], metrics: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    score_path = output_dir / "silver_model_scores.csv"
    if score_path.exists() and not args.force_score:
        print(f"reuse_scores={score_path}", flush=True)
        return read_csv(score_path)

    set_seed(args.seed)
    label_maps = label_maps_from_metrics(metrics)
    inv = inverse_maps(label_maps)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    tokenizer_path = Path(args.best_run_dir) / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    dataset = TextMultiTaskDataset(
        silver_rows,
        TARGET_COLS,
        label_maps,
        tokenizer,
        int(metrics["max_length"]),
        metrics["text_mode"],
        cache_tokenization=args.cache_tokenization,
        tokenization_batch_size=args.tokenization_batch_size,
    )
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
    )
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(label_maps[col]) for col in TARGET_COLS},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    state = torch.load(Path(args.best_run_dir) / "model.pt", map_location=device)
    model.load_state_dict(state)
    model.eval()

    score_fields = [
        "record_id",
        "diamond_score",
        "agree_heads",
        "core_agree",
        "core_min_silver_prob",
        "mean_silver_prob",
        "logic_ok",
        "logic_issues",
    ]
    for col in TARGET_COLS:
        score_fields.extend([f"{col}_silver", f"{col}_pred", f"{col}_silver_prob", f"{col}_pred_prob", f"{col}_agree"])

    output_dir.mkdir(parents=True, exist_ok=True)
    scored: list[dict[str, Any]] = []
    with score_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=score_fields)
        writer.writeheader()
        cursor = 0
        with torch.no_grad():
            for batch_index, batch in enumerate(loader, start=1):
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device=device, dtype=torch.long)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                batch_size = input_ids.shape[0]
                per_col: dict[str, dict[str, list[Any]]] = {}
                for col in TARGET_COLS:
                    probs = torch.softmax(outputs[col], dim=1)
                    pred_prob, pred_idx = torch.max(probs, dim=1)
                    silver_idx = batch[col].to(device)
                    silver_prob = probs[torch.arange(batch_size, device=device), silver_idx]
                    pred_idx_cpu = pred_idx.detach().cpu().tolist()
                    silver_idx_cpu = silver_idx.detach().cpu().tolist()
                    per_col[col] = {
                        "pred_label": [inv[col][idx] for idx in pred_idx_cpu],
                        "silver_label": [inv[col][idx] for idx in silver_idx_cpu],
                        "pred_prob": pred_prob.detach().cpu().tolist(),
                        "silver_prob": silver_prob.detach().cpu().tolist(),
                    }

                for local_i in range(batch_size):
                    source = silver_rows[cursor + local_i]
                    agree_heads = 0
                    silver_probs: list[float] = []
                    core_probs: list[float] = []
                    row_out: dict[str, Any] = {"record_id": row_id(source)}
                    for col in TARGET_COLS:
                        silver_label = per_col[col]["silver_label"][local_i]
                        pred_label = per_col[col]["pred_label"][local_i]
                        silver_prob = float(per_col[col]["silver_prob"][local_i])
                        pred_prob = float(per_col[col]["pred_prob"][local_i])
                        agree = silver_label == pred_label
                        agree_heads += int(agree)
                        silver_probs.append(silver_prob)
                        if col in CORE_COLS:
                            core_probs.append(silver_prob)
                        row_out[f"{col}_silver"] = silver_label
                        row_out[f"{col}_pred"] = pred_label
                        row_out[f"{col}_silver_prob"] = f"{silver_prob:.6f}"
                        row_out[f"{col}_pred_prob"] = f"{pred_prob:.6f}"
                        row_out[f"{col}_agree"] = "1" if agree else "0"

                    issues = logic_issues(source)
                    mean_silver_prob = sum(silver_probs) / len(silver_probs)
                    core_min = min(core_probs)
                    core_agree = all(row_out[f"{col}_agree"] == "1" for col in CORE_COLS)
                    score = (0.46 * mean_silver_prob) + (0.25 * (agree_heads / len(TARGET_COLS))) + (0.22 * core_min) + (0.07 if not issues else 0.0)
                    row_out.update(
                        {
                            "diamond_score": f"{score:.6f}",
                            "agree_heads": str(agree_heads),
                            "core_agree": "1" if core_agree else "0",
                            "core_min_silver_prob": f"{core_min:.6f}",
                            "mean_silver_prob": f"{mean_silver_prob:.6f}",
                            "logic_ok": "1" if not issues else "0",
                            "logic_issues": ";".join(issues),
                        }
                    )
                    writer.writerow(row_out)
                    scored.append(row_out)
                cursor += batch_size
                if args.log_every_batches and batch_index % args.log_every_batches == 0:
                    print(f"scored_batches={batch_index}/{len(loader)} rows={cursor}", flush=True)
    print(f"scores_written={score_path}", flush=True)
    return scored


def as_float(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key, 0) or 0)
    except ValueError:
        return 0.0


def as_int(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key, 0) or 0))
    except ValueError:
        return 0


def high_confidence_candidate(score: dict[str, Any], row: dict[str, Any], args: argparse.Namespace) -> bool:
    if score.get("logic_ok") != "1":
        return False
    if score.get("core_agree") != "1":
        return False
    if as_int(score, "agree_heads") < args.min_agree_heads:
        return False
    if as_float(score, "core_min_silver_prob") < args.min_core_silver_prob:
        return False
    if as_float(score, "mean_silver_prob") < args.min_mean_silver_prob:
        return False
    if row.get("quality") in {"spam", "duplicate"}:
        return False
    return True


def select_diamond(
    args: argparse.Namespace,
    silver_rows: list[dict[str, Any]],
    scored_rows: list[dict[str, Any]],
    audited_ids: set[str],
) -> tuple[set[str], dict[str, str], dict[str, float], list[dict[str, Any]]]:
    by_id = {row_id(row): row for row in silver_rows}
    scored_by_id = {row["record_id"]: row for row in scored_rows}
    target = int(len(silver_rows) * args.target_share)
    non_jkh_cap = int(target * args.max_non_jkh_share)

    forced: list[tuple[str, float]] = []
    candidates_yes: list[tuple[str, float]] = []
    candidates_no: list[tuple[str, float]] = []
    rejected: list[dict[str, Any]] = []

    for rid, row in by_id.items():
        score = scored_by_id.get(rid)
        if not score:
            continue
        audited = rid in audited_ids
        logic_ok = score.get("logic_ok") == "1"
        score_value = as_float(score, "diamond_score")
        if audited and logic_ok and row.get("quality") not in {"spam", "duplicate"}:
            forced.append((rid, score_value + 0.25))
            continue
        if high_confidence_candidate(score, row, args):
            if row.get("jkh_relevance") == "yes":
                candidates_yes.append((rid, score_value))
            else:
                candidates_no.append((rid, score_value))
        else:
            rejected.append(
                {
                    "record_id": rid,
                    "reason": "logic_or_agreement_or_confidence",
                    "diamond_score": f"{score_value:.6f}",
                    "agree_heads": score.get("agree_heads", ""),
                    "core_min_silver_prob": score.get("core_min_silver_prob", ""),
                    "mean_silver_prob": score.get("mean_silver_prob", ""),
                    "logic_issues": score.get("logic_issues", ""),
                    "jkh_relevance": row.get("jkh_relevance", ""),
                    "jkh_topic": row.get("jkh_topic", ""),
                }
            )

    selected: set[str] = set()
    reasons: dict[str, str] = {}
    weights: dict[str, float] = {}

    for rid, score_value in sorted(forced, key=lambda item: item[1], reverse=True):
        selected.add(rid)
        reasons[rid] = "audited_override"
        score = scored_by_id[rid]
        weights[rid] = stable_weight(as_float(score, "diamond_score"), as_int(score, "agree_heads"), True, args)

    non_jkh_selected = sum(1 for rid in selected if by_id[rid].get("jkh_relevance") != "yes")

    for rid, score_value in sorted(candidates_yes, key=lambda item: item[1], reverse=True):
        if len(selected) >= target:
            break
        selected.add(rid)
        reasons[rid] = "model_agrees_core_high_confidence_jkh"
        score = scored_by_id[rid]
        weights[rid] = stable_weight(as_float(score, "diamond_score"), as_int(score, "agree_heads"), False, args)

    for rid, score_value in sorted(candidates_no, key=lambda item: item[1], reverse=True):
        if len(selected) >= target:
            break
        if non_jkh_selected >= non_jkh_cap:
            break
        selected.add(rid)
        non_jkh_selected += 1
        reasons[rid] = "model_agrees_core_high_confidence_non_jkh"
        score = scored_by_id[rid]
        weights[rid] = stable_weight(as_float(score, "diamond_score"), as_int(score, "agree_heads"), False, args)

    return selected, reasons, weights, rejected


def summarize_distribution(rows: list[dict[str, Any]], cols: list[str]) -> dict[str, dict[str, int]]:
    return {col: dict(Counter(row.get(col, "") for row in rows).most_common()) for col in cols}


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = json.loads((Path(args.best_run_dir) / "metrics.json").read_text(encoding="utf-8"))
    rows = read_csv(args.input_csv)
    gold_rows = [row for row in rows if row.get("label_source") == "gold_human"]
    silver_rows = [row for row in rows if row.get("label_source") == "silver_auto" and row.get("split") == "train"]
    if not silver_rows:
        raise SystemExit("No silver train rows found.")

    audited_ids = load_audited_ids(args.audited_override_files)
    print(f"gold_rows={len(gold_rows)} silver_rows={len(silver_rows)} audited_ids={len(audited_ids)}", flush=True)
    scored_rows = model_score_rows(args, silver_rows, metrics, output_dir)
    selected, reasons, weights, rejected = select_diamond(args, silver_rows, scored_rows, audited_ids)
    scored_by_id = {row["record_id"]: row for row in scored_rows}

    diamond_rows: list[dict[str, Any]] = []
    remainder_rows: list[dict[str, Any]] = []
    combined_rows: list[dict[str, Any]] = []

    for row in rows:
        out = dict(row)
        rid = row_id(row)
        if row.get("label_source") == "gold_human":
            out["sample_weight"] = f"{args.gold_weight:g}"
            out["diamond_reason"] = ""
            out["diamond_score"] = ""
            out["model_agree_heads"] = ""
            combined_rows.append(out)
            continue
        if row.get("label_source") == "silver_auto" and row.get("split") == "train":
            score = scored_by_id.get(rid, {})
            out["diamond_score"] = score.get("diamond_score", "")
            out["model_agree_heads"] = score.get("agree_heads", "")
            out["core_min_silver_prob"] = score.get("core_min_silver_prob", "")
            out["mean_silver_prob"] = score.get("mean_silver_prob", "")
            out["logic_issues"] = score.get("logic_issues", "")
            if rid in selected:
                out["label_source"] = "diamond_auto"
                out["sample_weight"] = f"{weights.get(rid, args.mid_diamond_weight):g}"
                out["diamond_reason"] = reasons.get(rid, "diamond_selected")
                diamond_rows.append(out)
            else:
                out["label_source"] = "silver_auto"
                out["sample_weight"] = f"{args.remainder_silver_weight:g}"
                out["diamond_reason"] = "not_diamond_remainder"
                remainder_rows.append(out)
            combined_rows.append(out)
            continue
        combined_rows.append(out)

    extra_fields = ["diamond_reason", "diamond_score", "model_agree_heads", "core_min_silver_prob", "mean_silver_prob", "logic_issues"]
    fieldnames = list(rows[0].keys())
    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    write_csv(output_dir / "diamond_train.csv", diamond_rows, fieldnames)
    write_csv(output_dir / "silver_remainder_train.csv", remainder_rows, fieldnames)
    write_csv(output_dir / "dataset_gold_diamond_silver_fixed_split.csv", combined_rows, fieldnames)

    audit_sample = sorted(
        [
            {
                **{key: row.get(key, "") for key in ["record_id", "jkh_relevance", "jkh_topic", "quality", "diamond_reason", "diamond_score", "model_agree_heads", "core_min_silver_prob", "mean_silver_prob", "logic_issues"]},
                "text": row.get("text", "")[:600],
                "post_text": row.get("post_text", "")[:600],
            }
            for row in remainder_rows
        ],
        key=lambda item: float(item.get("diamond_score") or 0),
        reverse=True,
    )[: args.audit_sample_size]
    audit_fields = [
        "record_id",
        "jkh_relevance",
        "jkh_topic",
        "quality",
        "diamond_reason",
        "diamond_score",
        "model_agree_heads",
        "core_min_silver_prob",
        "mean_silver_prob",
        "logic_issues",
        "text",
        "post_text",
    ]
    write_csv(output_dir / "diamond_rejected_borderline_sample.csv", audit_sample, audit_fields)

    selected_scores = [as_float(scored_by_id[row_id(row)], "diamond_score") for row in diamond_rows if row_id(row) in scored_by_id]
    summary = {
        "input_csv": args.input_csv,
        "best_run_dir": args.best_run_dir,
        "target_share": args.target_share,
        "gold_rows": len(gold_rows),
        "silver_rows": len(silver_rows),
        "diamond_rows": len(diamond_rows),
        "silver_remainder_rows": len(remainder_rows),
        "diamond_share_of_silver": len(diamond_rows) / max(len(silver_rows), 1),
        "audited_override_ids": len(audited_ids),
        "diamond_weights": dict(Counter(row.get("sample_weight", "") for row in diamond_rows).most_common()),
        "combined_sample_weight_distribution": dict(Counter(row.get("sample_weight", "") for row in combined_rows).most_common()),
        "diamond_reason_distribution": dict(Counter(row.get("diamond_reason", "") for row in diamond_rows).most_common()),
        "diamond_label_distribution": summarize_distribution(diamond_rows, TARGET_COLS),
        "remainder_label_distribution": summarize_distribution(remainder_rows, TARGET_COLS),
        "score_stats": {
            "min": min(selected_scores) if selected_scores else None,
            "mean": sum(selected_scores) / len(selected_scores) if selected_scores else None,
            "max": max(selected_scores) if selected_scores else None,
        },
        "thresholds": {
            "min_agree_heads": args.min_agree_heads,
            "min_core_silver_prob": args.min_core_silver_prob,
            "min_mean_silver_prob": args.min_mean_silver_prob,
            "max_non_jkh_share": args.max_non_jkh_share,
        },
        "outputs": {
            "diamond_train": str(output_dir / "diamond_train.csv"),
            "silver_remainder_train": str(output_dir / "silver_remainder_train.csv"),
            "combined_dataset": str(output_dir / "dataset_gold_diamond_silver_fixed_split.csv"),
            "scores": str(output_dir / "silver_model_scores.csv"),
            "borderline_sample": str(output_dir / "diamond_rejected_borderline_sample.csv"),
        },
    }
    write_json(output_dir / "summary.json", summary)
    write_markdown(output_dir / "summary.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Diamond Dataset Summary",
        "",
        f"- Input CSV: `{summary['input_csv']}`",
        f"- Best model: `{summary['best_run_dir']}`",
        f"- Gold rows: `{summary['gold_rows']}`",
        f"- Silver rows: `{summary['silver_rows']}`",
        f"- Diamond rows: `{summary['diamond_rows']}` ({summary['diamond_share_of_silver']:.2%} of silver)",
        f"- Silver remainder rows: `{summary['silver_remainder_rows']}`",
        "",
        "## Weights",
        "",
    ]
    for weight, count in summary["combined_sample_weight_distribution"].items():
        lines.append(f"- `{weight}`: `{count}` rows")
    lines.extend(["", "## Diamond reasons", ""])
    for reason, count in summary["diamond_reason_distribution"].items():
        lines.append(f"- `{reason}`: `{count}` rows")
    lines.extend(["", "## Key outputs", ""])
    for name, value in summary["outputs"].items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default="data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv")
    parser.add_argument("--best-run-dir", default="data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4")
    parser.add_argument("--output-dir", default="data/ml_experiments/diamond_dataset_2026-06-03")
    parser.add_argument(
        "--audited-override-files",
        nargs="*",
        default=[
            "data/exports/offline_jkh_labels_2026-06-02_15-07/unresolved_jkh_candidates_labeled.csv",
            "data/exports/offline_jkh_labels_all_2026-06-03_00-33/unresolved_jkh_candidates_labeled.csv",
        ],
    )
    parser.add_argument("--target-share", type=float, default=0.65)
    parser.add_argument("--max-non-jkh-share", type=float, default=0.58)
    parser.add_argument("--min-agree-heads", type=int, default=5)
    parser.add_argument("--min-core-silver-prob", type=float, default=0.34)
    parser.add_argument("--min-mean-silver-prob", type=float, default=0.36)
    parser.add_argument("--gold-weight", type=float, default=1.0)
    parser.add_argument("--audited-diamond-weight", type=float, default=0.75)
    parser.add_argument("--high-diamond-weight", type=float, default=0.70)
    parser.add_argument("--mid-diamond-weight", type=float, default=0.65)
    parser.add_argument("--low-diamond-weight", type=float, default=0.60)
    parser.add_argument("--remainder-silver-weight", type=float, default=0.20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache-tokenization", action="store_true")
    parser.add_argument("--tokenization-batch-size", type=int, default=2048)
    parser.add_argument("--log-every-batches", type=int, default=100)
    parser.add_argument("--audit-sample-size", type=int, default=500)
    parser.add_argument("--force-score", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
