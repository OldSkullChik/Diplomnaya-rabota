#!/usr/bin/env python
"""Train and compare direct OMSU score classification heads."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


INPUT_CSV = "data/ml_experiments/omsu_score_2026-06-06/dataset_gold_silver_omsu_fixed_split.csv"

BASE_AXES = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]


CONFIGS: dict[str, dict[str, Any]] = {
    "negative_signal_none_screen": {
        "target_cols": ["omsu_negative_signal"],
        "epochs": 2,
        "max_train_rows": 40000,
        "class_weight_mode": "none",
    },
    "negative_signal_weighted_screen": {
        "target_cols": ["omsu_negative_signal"],
        "epochs": 2,
        "max_train_rows": 40000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0.0,
    },
    "negative_signal_capped_screen": {
        "target_cols": ["omsu_negative_signal"],
        "epochs": 2,
        "max_train_rows": 40000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
    },
    "impact_class_weighted_screen": {
        "target_cols": ["omsu_impact_class"],
        "epochs": 2,
        "max_train_rows": 40000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0.0,
    },
    "impact_class_capped_screen": {
        "target_cols": ["omsu_impact_class"],
        "epochs": 2,
        "max_train_rows": 40000,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
    },
    "negative_signal_weighted_full": {
        "target_cols": ["omsu_negative_signal"],
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0.0,
        "save_model": True,
    },
    "negative_signal_capped_full": {
        "target_cols": ["omsu_negative_signal"],
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 0.75,
        "class_weight_max": 4.0,
        "save_model": True,
    },
    "axes_plus_negative_signal_full": {
        "target_cols": [*BASE_AXES, "omsu_negative_signal"],
        "epochs": 4,
        "max_train_rows": 0,
        "class_weight_mode": "weighted_balanced",
        "class_weight_power": 1.0,
        "class_weight_max": 0.0,
        "save_model": True,
    },
}


def mean_macro(metrics: dict[str, Any]) -> float:
    values = [
        metric["macro_f1"]
        for metric in metrics.values()
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
        *config["target_cols"],
        "--text-mode",
        "post_comment",
        "--base-model",
        "cointegrated/rubert-tiny2",
        "--epochs",
        str(config["epochs"]),
        "--batch-size",
        str(config.get("batch_size", 16)),
        "--max-length",
        str(config.get("max_length", 192)),
        "--lr",
        "1e-5",
        "--class-weight-mode",
        str(config["class_weight_mode"]),
        "--class-weight-power",
        str(config.get("class_weight_power", 1.0)),
        "--class-weight-max",
        str(config.get("class_weight_max", 0.0)),
        "--silver-weight-override",
        "0.3",
        "--log-every-steps",
        "1000",
    ]
    if config.get("cache_tokenization"):
        command += ["--cache-tokenization", "--tokenization-batch-size", str(config.get("tokenization_batch_size", 2048))]
    if config.get("max_train_rows"):
        command += ["--max-train-rows", str(config["max_train_rows"])]
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
            "target_cols": ",".join(metrics.get("target_cols", [])),
            "rows_train": metrics.get("rows", {}).get("train"),
            "epochs": metrics.get("epochs"),
            "class_weight_mode": metrics.get("class_weight_mode"),
            "class_weight_power": metrics.get("class_weight_power"),
            "class_weight_max": metrics.get("class_weight_max"),
            "best_val_macro_f1": best_val(metrics),
            "test_mean_macro_f1": mean_macro(metrics.get("test_metrics", {})),
        }
        for target in metrics.get("target_cols", []):
            metric = metrics.get("test_metrics", {}).get(target, {})
            row[f"{target}_macro_f1"] = metric.get("macro_f1")
            row[f"{target}_weighted_f1"] = metric.get("weighted_f1")
            row[f"{target}_accuracy"] = metric.get("accuracy")
        rows.append(row)
    rows.sort(key=lambda row: float(row.get("best_val_macro_f1") or 0.0), reverse=True)
    if not rows:
        return

    fields = list(rows[0])
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with (output_root / "omsu_score_sweep_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# OMSU Score Sweep Summary",
        "",
        "| Run | Targets | Train rows | Best val macro-F1 | Test mean macro-F1 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['run']}` | `{row['target_cols']}` | {row['rows_train']} | "
            f"{float(row['best_val_macro_f1']):.4f} | {float(row['test_mean_macro_f1']):.4f} |"
        )
    lines += ["", "## OMSU Test Metrics", ""]
    lines.append("| Run | Target | Accuracy | Macro-F1 | Weighted-F1 |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for row in rows:
        for target in ("omsu_negative_signal", "omsu_impact_class"):
            if row.get(f"{target}_macro_f1") is None:
                continue
            lines.append(
                f"| `{row['run']}` | `{target}` | "
                f"{float(row[f'{target}_accuracy']):.4f} | "
                f"{float(row[f'{target}_macro_f1']):.4f} | "
                f"{float(row[f'{target}_weighted_f1']):.4f} |"
            )
    (output_root / "omsu_score_sweep_summary.md").write_text("\n".join(lines), encoding="utf-8")
    (output_root / "omsu_score_sweep_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/ml_experiments/omsu_score_2026-06-06/sweep")
    parser.add_argument("--run", action="append", choices=sorted(CONFIGS), help="Run only selected configs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_names = args.run or [
        "negative_signal_none_screen",
        "negative_signal_weighted_screen",
        "negative_signal_capped_screen",
        "impact_class_weighted_screen",
        "impact_class_capped_screen",
    ]
    for name in run_names:
        if not (output_root / name / "metrics.json").exists():
            run_one(name, CONFIGS[name], output_root)
        summarize(output_root)
    summarize(output_root)
    print(output_root / "omsu_score_sweep_summary.md")


if __name__ == "__main__":
    main()
