#!/usr/bin/env python
"""Run class-weight balancing presets for the teacher-student classifier."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ORIGINAL_TARGETS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]

GROUPED_TARGETS = [
    "jkh_relevance_grouped",
    "jkh_topic_grouped",
    "authority_aspect_grouped",
    "sentiment_grouped",
    "appeal_type_grouped",
    "responsible_party_grouped",
    "sarcasm_grouped",
    "quality_grouped",
]

ORIGINAL_INPUT = "data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv"
GROUPED_INPUT = "data/ml_experiments/teacher_student_grouped_2026-06-04/dataset_gold_silver_grouped_fixed_split.csv"

ORIGINAL_WEAK_HEADS = {
    "jkh_relevance": 0.9,
    "jkh_topic": 1.2,
    "authority_aspect": 1.6,
    "sentiment": 1.0,
    "appeal_type": 1.4,
    "responsible_party": 1.8,
    "sarcasm": 0.9,
    "quality": 0.9,
}

GROUPED_WEAK_HEADS = {
    "jkh_relevance_grouped": 0.9,
    "jkh_topic_grouped": 1.2,
    "authority_aspect_grouped": 1.5,
    "sentiment_grouped": 1.0,
    "appeal_type_grouped": 1.35,
    "responsible_party_grouped": 1.6,
    "sarcasm_grouped": 0.9,
    "quality_grouped": 0.9,
}


CONFIGS: dict[str, dict[str, Any]] = {
    "original_current_weighted_screen": {
        "group": "screen_extra",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0,
    },
    "original_current_weighted_headboost_screen": {
        "group": "screen_extra",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0,
        "head_loss_weights": ORIGINAL_WEAK_HEADS,
    },
    "original_weighted_power075_cap4_screen": {
        "group": "screen",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
    },
    "original_weighted_power075_cap4_headboost_screen": {
        "group": "screen_extra",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "head_loss_weights": ORIGINAL_WEAK_HEADS,
    },
    "original_gold_cap3_screen": {
        "group": "screen",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 3,
    },
    "original_gold_cap5_screen": {
        "group": "screen",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 5,
    },
    "original_gold_power075_cap4_screen": {
        "group": "screen",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
    },
    "original_gold_power075_cap4_headboost_screen": {
        "group": "screen",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "head_loss_weights": ORIGINAL_WEAK_HEADS,
    },
    "grouped_gold_power075_cap4_headboost_screen": {
        "group": "screen",
        "input_csv": GROUPED_INPUT,
        "target_cols": GROUPED_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "head_loss_weights": GROUPED_WEAK_HEADS,
    },
    "grouped_current_weighted_screen": {
        "group": "screen_extra",
        "input_csv": GROUPED_INPUT,
        "target_cols": GROUPED_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0,
    },
    "grouped_weighted_power075_cap4_screen": {
        "group": "screen_extra",
        "input_csv": GROUPED_INPUT,
        "target_cols": GROUPED_TARGETS,
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
    },
    "original_gold_power075_cap4_full": {
        "group": "final",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "save_model": True,
    },
    "original_weighted_power075_cap4_full": {
        "group": "final",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "save_model": True,
    },
    "original_gold_power075_cap4_headboost_full": {
        "group": "final",
        "input_csv": ORIGINAL_INPUT,
        "target_cols": ORIGINAL_TARGETS,
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "head_loss_weights": ORIGINAL_WEAK_HEADS,
        "save_model": True,
    },
    "grouped_gold_power075_cap4_headboost_full": {
        "group": "final",
        "input_csv": GROUPED_INPUT,
        "target_cols": GROUPED_TARGETS,
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "head_loss_weights": GROUPED_WEAK_HEADS,
        "save_model": True,
    },
    "grouped_weighted_power075_cap4_full": {
        "group": "final",
        "input_csv": GROUPED_INPUT,
        "target_cols": GROUPED_TARGETS,
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4,
        "save_model": True,
    },
}


def metric_mean(test_metrics: dict[str, Any]) -> float:
    values = [
        value["macro_f1"]
        for value in test_metrics.values()
        if isinstance(value, dict) and "macro_f1" in value
    ]
    return sum(values) / max(len(values), 1)


def best_val(metrics: dict[str, Any]) -> float:
    return max((float(row.get("mean_val_macro_f1", 0)) for row in metrics.get("history", [])), default=0.0)


def write_head_weights(output_root: Path, name: str, weights: dict[str, float] | None) -> str:
    if not weights:
        return ""
    path = output_root / f"{name}_head_weights.json"
    path.write_text(json.dumps(weights, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def command_for_run(name: str, config: dict[str, Any], output_root: Path) -> list[str]:
    output_dir = output_root / name
    args = [
        sys.executable,
        "experiments/train_rubert_multitask.py",
        "--input-csv",
        config["input_csv"],
        "--output-dir",
        str(output_dir),
        "--target-cols",
        *config["target_cols"],
        "--text-mode",
        "post_comment",
        "--base-model",
        "cointegrated/rubert-tiny2",
        "--epochs",
        str(config["epochs"]),
        "--batch-size",
        "32",
        "--max-length",
        "256",
        "--lr",
        "1e-5",
        "--class-weight-mode",
        config["class_weight_mode"],
        "--class-weight-power",
        str(config["class_weight_power"]),
        "--class-weight-max",
        str(config["class_weight_max"]),
        "--silver-weight-override",
        "0.3",
        "--cache-tokenization",
        "--tokenization-batch-size",
        "2048",
        "--log-every-steps",
        "1000",
    ]
    if config.get("max_train_rows"):
        args += ["--max-train-rows", str(config["max_train_rows"])]
    head_weights_path = write_head_weights(output_root, name, config.get("head_loss_weights"))
    if head_weights_path:
        args += ["--head-loss-weights", head_weights_path]
    if config.get("save_model"):
        args.append("--save-model")
    return args


def summarize(output_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_cols: list[str] = []
    for metrics_path in sorted(output_root.glob("*/metrics.json")):
        if metrics_path.parent.name not in CONFIGS:
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        run_targets = metrics.get("target_cols", [])
        for target in run_targets:
            if target not in target_cols:
                target_cols.append(target)
        row: dict[str, Any] = {
            "run": metrics_path.parent.name,
            "best_val_macro_f1": best_val(metrics),
            "test_mean_macro_f1": metric_mean(metrics.get("test_metrics", {})),
            "rows_train": metrics.get("rows", {}).get("train"),
            "epochs": metrics.get("epochs"),
            "class_weight_mode": metrics.get("class_weight_mode"),
            "class_weight_power": metrics.get("class_weight_power"),
            "class_weight_max": metrics.get("class_weight_max"),
            "head_loss_weights": json.dumps(metrics.get("head_loss_weights", {}), ensure_ascii=False),
        }
        for target in run_targets:
            value = metrics.get("test_metrics", {}).get(target, {})
            row[f"{target}_macro_f1"] = value.get("macro_f1")
            row[f"{target}_accuracy"] = value.get("accuracy")
        rows.append(row)

    rows.sort(key=lambda row: float(row["best_val_macro_f1"]), reverse=True)
    if not rows:
        return rows

    keys = list(rows[0].keys())
    for target in target_cols:
        for suffix in ("macro_f1", "accuracy"):
            key = f"{target}_{suffix}"
            if key not in keys:
                keys.append(key)
    with (output_root / "class_weight_sweep_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Class Weight Sweep Summary",
        "",
        "| Run | Train rows | Epochs | Best val macro-F1 | Test mean macro-F1 | Weight mode | Power | Max |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run']}` | {row['rows_train']} | {row['epochs']} | "
            f"{float(row['best_val_macro_f1']):.4f} | {float(row['test_mean_macro_f1']):.4f} | "
            f"`{row['class_weight_mode']}` | {float(row['class_weight_power']):.2f} | "
            f"{float(row['class_weight_max']):.1f} |"
        )
    lines += ["", "## Per-Head Macro-F1", ""]
    lines.append("| Run | " + " | ".join(target_cols) + " |")
    lines.append("| --- | " + " | ".join(["---:"] * len(target_cols)) + " |")
    for row in rows:
        values = [
            f"{float(row[f'{target}_macro_f1']):.4f}" if row.get(f"{target}_macro_f1") is not None else ""
            for target in target_cols
        ]
        lines.append(f"| `{row['run']}` | " + " | ".join(values) + " |")
    (output_root / "class_weight_sweep_summary.md").write_text("\n".join(lines), encoding="utf-8")
    (output_root / "class_weight_sweep_summary.json").write_text(
        json.dumps({"runs": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def run_config(name: str, config: dict[str, Any], output_root: Path, force: bool) -> None:
    output_dir = output_root / name
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "metrics.json").exists() and not force:
        print(f"skip existing: {name}", flush=True)
        return
    command = command_for_run(name, config, output_root)
    (output_dir / "command.json").write_text(
        json.dumps(command, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"start: {name}", flush=True)
    with (output_dir / "train_stdout.log").open("w", encoding="utf-8") as out, (
        output_dir / "train_stderr.log"
    ).open("w", encoding="utf-8") as err:
        completed = subprocess.run(command, stdout=out, stderr=err, text=True)
    if completed.returncode != 0:
        raise SystemExit(f"run failed ({completed.returncode}): {name}")
    print(f"done: {name}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/ml_experiments/class_weight_sweep_2026-06-05")
    parser.add_argument("--group", choices=["screen", "screen_extra", "final", "all"], default="screen")
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    selected = args.run or [
        name
        for name, config in CONFIGS.items()
        if args.group == "all" or config["group"] == args.group
    ]
    for name in selected:
        if name not in CONFIGS:
            raise SystemExit(f"Unknown run config: {name}")
        run_config(name, CONFIGS[name], output_root, force=args.force)
        summarize(output_root)
    print(output_root / "class_weight_sweep_summary.md")


if __name__ == "__main__":
    main()
