#!/usr/bin/env python
"""Run class-weight tests with gold/silver sample weights forced to 1.0."""

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

CONFIGS: dict[str, dict[str, Any]] = {
    "no_sample_none_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "none",
    },
    "no_sample_balanced_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0.0,
    },
    "no_sample_balanced_power075_cap4_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
    },
    "no_sample_balanced_power05_cap6_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "balanced",
        "class_weight_power": 0.50,
        "class_weight_max": 6.0,
    },
    "no_sample_gold_power075_cap4_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
    },
    "no_sample_gold_power05_cap6_screen": {
        "epochs": 2,
        "max_train_rows": 80000,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.50,
        "class_weight_max": 6.0,
    },
    "no_sample_balanced_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0.0,
        "save_model": True,
    },
    "no_sample_balanced_power075_cap4_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
        "save_model": True,
    },
    "no_sample_gold_power075_cap4_full": {
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "gold_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
        "save_model": True,
    },
}


def mean_macro(test_metrics: dict[str, Any]) -> float:
    values = [
        metric["macro_f1"]
        for metric in test_metrics.values()
        if isinstance(metric, dict) and "macro_f1" in metric
    ]
    return sum(values) / max(len(values), 1)


def best_val(metrics: dict[str, Any]) -> float:
    return max((float(row.get("mean_val_macro_f1", 0.0)) for row in metrics.get("history", [])), default=0.0)


def command_for_run(name: str, config: dict[str, Any], output_root: Path) -> list[str]:
    command = [
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
        str(config["class_weight_mode"]),
        "--class-weight-power",
        str(config.get("class_weight_power", 1.0)),
        "--class-weight-max",
        str(config.get("class_weight_max", 0.0)),
        "--gold-weight-override",
        "1.0",
        "--silver-weight-override",
        "1.0",
        "--cache-tokenization",
        "--tokenization-batch-size",
        "2048",
        "--log-every-steps",
        "1000",
    ]
    if config.get("max_train_rows"):
        command += ["--max-train-rows", str(config["max_train_rows"])]
    if config.get("class_weights_json"):
        command += ["--class-weights-json", str(config["class_weights_json"])]
    if config.get("save_model"):
        command.append("--save-model")
    return command


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
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        row: dict[str, Any] = {
            "run": metrics_path.parent.name,
            "rows_train": metrics.get("rows", {}).get("train"),
            "epochs": metrics.get("epochs"),
            "class_weight_mode": metrics.get("class_weight_mode"),
            "class_weight_power": metrics.get("class_weight_power"),
            "class_weight_max": metrics.get("class_weight_max"),
            "gold_weight_override": metrics.get("gold_weight_override"),
            "silver_weight_override": metrics.get("silver_weight_override"),
            "best_val_macro_f1": best_val(metrics),
            "test_mean_macro_f1": mean_macro(metrics.get("test_metrics", {})),
        }
        for target in TARGETS:
            metric = metrics.get("test_metrics", {}).get(target, {})
            row[f"{target}_macro_f1"] = metric.get("macro_f1")
        rows.append(row)
    rows.sort(key=lambda row: float(row.get("best_val_macro_f1") or 0.0), reverse=True)
    if not rows:
        return

    fields = list(rows[0])
    for target in TARGETS:
        key = f"{target}_macro_f1"
        if key not in fields:
            fields.append(key)
    with (output_root / "no_sample_weight_class_sweep_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# No Sample-Weight Class Sweep",
        "",
        "All runs force `gold_weight_override=1.0` and `silver_weight_override=1.0`.",
        "",
        "| Run | Train rows | Epochs | Class weights | Best val macro-F1 | Test mean macro-F1 |",
        "| --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        preset = (
            f"{row['class_weight_mode']}, power={row['class_weight_power']}, "
            f"cap={row['class_weight_max']}"
        )
        lines.append(
            f"| `{row['run']}` | {row['rows_train']} | {row['epochs']} | {preset} | "
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
    (output_root / "no_sample_weight_class_sweep_summary.md").write_text("\n".join(lines), encoding="utf-8")
    (output_root / "no_sample_weight_class_sweep_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/ml_experiments/no_sample_weight_class_sweep_2026-06-05")
    parser.add_argument("--run", action="append", choices=sorted(CONFIGS), help="Run only selected configs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_names = args.run or [
        "no_sample_none_screen",
        "no_sample_balanced_screen",
        "no_sample_balanced_power075_cap4_screen",
        "no_sample_balanced_power05_cap6_screen",
        "no_sample_gold_power075_cap4_screen",
        "no_sample_gold_power05_cap6_screen",
    ]
    for name in run_names:
        if not (output_root / name / "metrics.json").exists():
            run_one(name, CONFIGS[name], output_root)
        summarize(output_root)
    summarize(output_root)
    print(output_root / "no_sample_weight_class_sweep_summary.md")


if __name__ == "__main__":
    main()
