#!/usr/bin/env python
"""Run original-taxonomy per-label class-weight presets."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TARGETS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]

INPUT_CSV = "data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv"
PRESET_DIR = Path("data/ml_experiments/individual_class_weighting_2026-06-05/presets")

CONFIGS: dict[str, dict[str, Any]] = {
    "original_baseline_repro_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": "",
    },
    "original_individual_guarded_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_guarded.json"),
    },
    "original_individual_fn_fp_ratio_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_fn_fp_ratio.json"),
    },
    "original_individual_weak_only_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_weak_only.json"),
    },
    "original_individual_authority_only_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_authority_only.json"),
    },
    "original_individual_guarded_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_guarded.json"),
        "save_model": True,
    },
    "original_individual_fn_fp_ratio_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_fn_fp_ratio.json"),
        "save_model": True,
    },
    "original_individual_weak_only_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_weak_only.json"),
        "save_model": True,
    },
    "original_individual_authority_only_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weights_json": str(PRESET_DIR / "individual_authority_only.json"),
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


def command_for_run(name: str, config: dict[str, Any], output_root: Path) -> list[str]:
    args = [
        sys.executable,
        "experiments/train_rubert_multitask.py",
        "--input-csv",
        INPUT_CSV,
        "--output-dir",
        str(output_root / name),
        "--target-cols",
        *TARGETS,
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
    if config.get("class_weights_json"):
        args += ["--class-weights-json", config["class_weights_json"]]
    if config.get("save_model"):
        args.append("--save-model")
    return args


def run_one(name: str, config: dict[str, Any], output_root: Path) -> None:
    output_dir = output_root / name
    output_dir.mkdir(parents=True, exist_ok=True)
    command = command_for_run(name, config, output_root)
    (output_dir / "command.json").write_text(json.dumps(command, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "train_stdout.log").open("w", encoding="utf-8") as stdout:
        with (output_dir / "train_stderr.log").open("w", encoding="utf-8") as stderr:
            print(f"start: {name}", flush=True)
            subprocess.run(command, check=True, stdout=stdout, stderr=stderr)
            print(f"done: {name}", flush=True)


def summarize(output_root: Path) -> None:
    rows: list[dict[str, Any]] = []
    for metrics_path in sorted(output_root.glob("*/metrics.json")):
        name = metrics_path.parent.name
        if name not in CONFIGS:
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        row: dict[str, Any] = {
            "run": name,
            "rows_train": metrics.get("rows", {}).get("train"),
            "epochs": metrics.get("epochs"),
            "best_val_macro_f1": best_val(metrics),
            "test_mean_macro_f1": metric_mean(metrics.get("test_metrics", {})),
            "class_weights_json": metrics.get("class_weights_json", ""),
        }
        for target in TARGETS:
            value = metrics.get("test_metrics", {}).get(target, {})
            row[f"{target}_macro_f1"] = value.get("macro_f1")
        rows.append(row)
    rows.sort(key=lambda row: float(row["best_val_macro_f1"]), reverse=True)
    if not rows:
        return
    fields = list(rows[0])
    for target in TARGETS:
        key = f"{target}_macro_f1"
        if key not in fields:
            fields.append(key)
    with (output_root / "individual_class_weight_sweep_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Individual Class Weight Sweep Summary",
        "",
        "| Run | Train rows | Epochs | Best val macro-F1 | Test mean macro-F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run']}` | {row['rows_train']} | {row['epochs']} | "
            f"{float(row['best_val_macro_f1']):.4f} | {float(row['test_mean_macro_f1']):.4f} |"
        )
    lines += ["", "## Per-Head Test Macro-F1", ""]
    lines.append("| Run | " + " | ".join(TARGETS) + " |")
    lines.append("| --- | " + " | ".join(["---:"] * len(TARGETS)) + " |")
    for row in rows:
        values = [
            "" if row.get(f"{target}_macro_f1") is None else f"{float(row[f'{target}_macro_f1']):.4f}"
            for target in TARGETS
        ]
        lines.append(f"| `{row['run']}` | " + " | ".join(values) + " |")
    (output_root / "individual_class_weight_sweep_summary.md").write_text("\n".join(lines), encoding="utf-8")
    (output_root / "individual_class_weight_sweep_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/ml_experiments/individual_class_weighting_2026-06-05/sweep")
    parser.add_argument("--run", action="append", choices=sorted(CONFIGS), help="Run only these configs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_names = args.run or [
        "original_baseline_repro_screen",
        "original_individual_guarded_screen",
        "original_individual_fn_fp_ratio_screen",
        "original_individual_weak_only_screen",
    ]
    for name in run_names:
        if not (output_root / name / "metrics.json").exists():
            run_one(name, CONFIGS[name], output_root)
        summarize(output_root)
    summarize(output_root)
    print(output_root / "individual_class_weight_sweep_summary.md")


if __name__ == "__main__":
    main()
