#!/usr/bin/env python
"""Run a local teacher-student RuBERT sweep and summarize metrics."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


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


QUICK_CONFIGS = [
    {"name": "quick_w02_weighted", "silver_weight": 0.2, "class_weight_mode": "weighted_balanced", "epochs": 1, "lr": 2e-5},
    {"name": "quick_w03_weighted", "silver_weight": 0.3, "class_weight_mode": "weighted_balanced", "epochs": 1, "lr": 2e-5},
    {"name": "quick_w04_weighted", "silver_weight": 0.4, "class_weight_mode": "weighted_balanced", "epochs": 1, "lr": 2e-5},
    {"name": "quick_w05_weighted", "silver_weight": 0.5, "class_weight_mode": "weighted_balanced", "epochs": 1, "lr": 2e-5},
    {"name": "quick_w03_no_class_weights", "silver_weight": 0.3, "class_weight_mode": "none", "epochs": 1, "lr": 2e-5},
]


FINAL_CONFIGS = [
    {"name": "final_w03_weighted_e4", "silver_weight": 0.3, "class_weight_mode": "weighted_balanced", "epochs": 4, "lr": 2e-5},
    {"name": "final_w04_weighted_e4", "silver_weight": 0.4, "class_weight_mode": "weighted_balanced", "epochs": 4, "lr": 2e-5},
    {"name": "final_w03_weighted_lr1e5_e4", "silver_weight": 0.3, "class_weight_mode": "weighted_balanced", "epochs": 4, "lr": 1e-5},
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def mean_macro(metrics: dict[str, Any]) -> float:
    values = [
        value["macro_f1"]
        for value in metrics.values()
        if isinstance(value, dict) and "macro_f1" in value
    ]
    return sum(values) / max(len(values), 1)


def best_val_macro(metrics: dict[str, Any]) -> float:
    history = metrics.get("history", [])
    if not history:
        return 0.0
    return max(float(item.get("mean_val_macro_f1", 0.0)) for item in history)


def summarize_run(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    metrics_path = path / "metrics.json"
    if not metrics_path.exists():
        return {"name": config["name"], "status": "missing_metrics"}
    metrics = read_json(metrics_path)
    row = {
        "name": config["name"],
        "status": "ok",
        "output_dir": str(path),
        "epochs": metrics.get("epochs"),
        "silver_weight": metrics.get("silver_weight_override"),
        "class_weight_mode": metrics.get("class_weight_mode"),
        "lr": metrics.get("lr"),
        "best_val_macro_f1": best_val_macro(metrics),
        "test_mean_macro_f1": mean_macro(metrics.get("test_metrics", {})),
    }
    for field in TARGET_COLS:
        field_metrics = metrics.get("test_metrics", {}).get(field, {})
        row[f"{field}_macro_f1"] = field_metrics.get("macro_f1")
        row[f"{field}_accuracy"] = field_metrics.get("accuracy")
    return row


def write_summary(output_root: Path, rows: list[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda row: float(row.get("best_val_macro_f1") or 0.0), reverse=True)
    write_json(output_root / "sweep_summary.json", {"runs": rows})
    if rows:
        with (output_root / "sweep_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    lines = [
        "# Teacher-Student Sweep Summary",
        "",
        "| Run | Best val macro-F1 | Test mean macro-F1 | Silver weight | Class weights | LR |",
        "| --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['name']}` | {float(row.get('best_val_macro_f1') or 0):.4f} | "
            f"{float(row.get('test_mean_macro_f1') or 0):.4f} | "
            f"{row.get('silver_weight')} | `{row.get('class_weight_mode')}` | {row.get('lr')} |"
        )
    (output_root / "sweep_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_config(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(args.output_root) / config["name"]
    metrics_path = output_dir / "metrics.json"
    if metrics_path.exists() and not args.force:
        print(f"skip existing {config['name']}", flush=True)
        return summarize_run(output_dir, config)

    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "train.out.log"
    stderr_path = output_dir / "train.err.log"
    command = [
        sys.executable,
        "experiments/train_rubert_multitask.py",
        "--input-csv",
        args.input_csv,
        "--output-dir",
        str(output_dir),
        "--target-cols",
        *TARGET_COLS,
        "--text-mode",
        "post_comment",
        "--base-model",
        args.base_model,
        "--epochs",
        str(config["epochs"]),
        "--batch-size",
        str(args.batch_size),
        "--max-length",
        str(args.max_length),
        "--lr",
        str(config["lr"]),
        "--class-weight-mode",
        config["class_weight_mode"],
        "--silver-weight-override",
        str(config["silver_weight"]),
        "--cache-tokenization",
        "--tokenization-batch-size",
        str(args.tokenization_batch_size),
        "--log-every-steps",
        str(args.log_every_steps),
    ]
    if config.get("save_model", args.save_model):
        command.append("--save-model")

    print(f"run {config['name']}", flush=True)
    print(" ".join(command), flush=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(command, cwd=args.repo_root, stdout=subprocess.PIPE, stderr=stderr, text=True, encoding="utf-8", errors="replace")
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            stdout.write(line)
            stdout.flush()
        code = proc.wait()
    if code != 0:
        raise SystemExit(f"{config['name']} failed with exit code {code}; see {stderr_path}")
    return summarize_run(output_dir, config)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default="data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv")
    parser.add_argument("--output-root", default="data/ml_experiments/teacher_student_runs/sweep_2026-06-03")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--phase", choices=["quick", "final"], default="quick")
    parser.add_argument("--base-model", default="cointegrated/rubert-tiny2")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--tokenization-batch-size", type=int, default=2048)
    parser.add_argument("--log-every-steps", type=int, default=1000)
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configs = QUICK_CONFIGS if args.phase == "quick" else FINAL_CONFIGS
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / "sweep_config.json", {"phase": args.phase, "configs": configs, "args": vars(args)})

    rows = []
    for config in configs:
        rows.append(run_config(args, config))
        write_summary(output_root, rows)
    write_summary(output_root, rows)
    print(f"summary={output_root / 'sweep_summary.md'}", flush=True)


if __name__ == "__main__":
    main()
