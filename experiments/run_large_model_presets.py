#!/usr/bin/env python
"""Run memory-aware larger-model presets for the teacher-student dataset."""

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

PRESETS = [
    {
        "name": "rubert_base_frozen_heads_smoke",
        "base_model": "DeepPavlov/rubert-base-cased",
        "epochs": 1,
        "batch_size": 8,
        "grad_accum_steps": 2,
        "max_length": 192,
        "lr": 3e-4,
        "silver_weight": 0.3,
        "class_weight_mode": "weighted_balanced",
        "freeze_encoder": True,
        "unfreeze_last_n_layers": 0,
        "gradient_checkpointing": False,
        "max_train_rows": 12000,
    },
    {
        "name": "rubert_base_last2_smoke",
        "base_model": "DeepPavlov/rubert-base-cased",
        "epochs": 1,
        "batch_size": 2,
        "grad_accum_steps": 16,
        "max_length": 192,
        "lr": 2e-5,
        "silver_weight": 0.3,
        "class_weight_mode": "weighted_balanced",
        "freeze_encoder": True,
        "unfreeze_last_n_layers": 2,
        "gradient_checkpointing": True,
        "max_train_rows": 12000,
    },
    {
        "name": "rubert_base_last4_smoke",
        "base_model": "DeepPavlov/rubert-base-cased",
        "epochs": 1,
        "batch_size": 1,
        "grad_accum_steps": 32,
        "max_length": 192,
        "lr": 1e-5,
        "silver_weight": 0.3,
        "class_weight_mode": "weighted_balanced",
        "freeze_encoder": True,
        "unfreeze_last_n_layers": 4,
        "gradient_checkpointing": True,
        "max_train_rows": 12000,
    },
    {
        "name": "rubert_base_last2_full_quick",
        "base_model": "DeepPavlov/rubert-base-cased",
        "epochs": 1,
        "batch_size": 2,
        "grad_accum_steps": 16,
        "max_length": 192,
        "lr": 2e-5,
        "silver_weight": 0.3,
        "class_weight_mode": "weighted_balanced",
        "freeze_encoder": True,
        "unfreeze_last_n_layers": 2,
        "gradient_checkpointing": True,
        "max_train_rows": 60000,
    },
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
    return max((float(item.get("mean_val_macro_f1", 0.0)) for item in metrics.get("history", [])), default=0.0)


def summarize(output_dir: Path, preset: dict[str, Any]) -> dict[str, Any]:
    metrics_path = output_dir / "metrics.json"
    if not metrics_path.exists():
        return {"name": preset["name"], "status": "missing_metrics", "output_dir": str(output_dir)}
    metrics = read_json(metrics_path)
    row = {
        "name": preset["name"],
        "status": "ok",
        "output_dir": str(output_dir),
        "base_model": metrics.get("base_model"),
        "rows_total": metrics.get("rows", {}).get("total"),
        "rows_train": metrics.get("rows", {}).get("train"),
        "best_val_macro_f1": best_val_macro(metrics),
        "test_mean_macro_f1": mean_macro(metrics.get("test_metrics", {})),
        "epochs": metrics.get("epochs"),
        "batch_size": metrics.get("batch_size"),
        "grad_accum_steps": metrics.get("grad_accum_steps"),
        "effective_batch_size": metrics.get("effective_batch_size"),
        "max_length": metrics.get("max_length"),
        "lr": metrics.get("lr"),
        "silver_weight": metrics.get("silver_weight_override"),
        "class_weight_mode": metrics.get("class_weight_mode"),
        "freeze_encoder": metrics.get("freeze_encoder"),
        "unfreeze_last_n_layers": metrics.get("unfreeze_last_n_layers"),
        "gradient_checkpointing": metrics.get("gradient_checkpointing"),
        "trainable_parameters": metrics.get("trainable_parameters"),
        "total_parameters": metrics.get("total_parameters"),
    }
    for field in TARGET_COLS:
        field_metrics = metrics.get("test_metrics", {}).get(field, {})
        row[f"{field}_macro_f1"] = field_metrics.get("macro_f1")
        row[f"{field}_accuracy"] = field_metrics.get("accuracy")
    return row


def write_summary(output_root: Path, rows: list[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda row: float(row.get("best_val_macro_f1") or 0.0), reverse=True)
    write_json(output_root / "large_model_preset_summary.json", {"runs": rows})
    if rows:
        keys = list(rows[0].keys())
        with (output_root / "large_model_preset_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    lines = [
        "# Large Model Preset Summary",
        "",
        "| Run | Model | Best val macro-F1 | Test mean macro-F1 | Rows | Trainable/Total params | Preset |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        trainable = int(row.get("trainable_parameters") or 0)
        total = int(row.get("total_parameters") or 0)
        preset = f"freeze={row.get('freeze_encoder')}, last={row.get('unfreeze_last_n_layers')}, gc={row.get('gradient_checkpointing')}"
        lines.append(
            f"| `{row['name']}` | `{row.get('base_model')}` | "
            f"{float(row.get('best_val_macro_f1') or 0):.4f} | "
            f"{float(row.get('test_mean_macro_f1') or 0):.4f} | "
            f"{row.get('rows_total')} | {trainable}/{total} | {preset} |"
        )
    (output_root / "large_model_preset_summary.md").write_text("\n".join(lines), encoding="utf-8")


def selected_presets(names: set[str] | None, phase: str) -> list[dict[str, Any]]:
    presets = PRESETS
    if phase == "smoke":
        presets = [preset for preset in presets if preset["name"].endswith("_smoke")]
    elif phase == "quick":
        presets = [preset for preset in presets if preset["name"].endswith("_smoke") or preset["name"].endswith("_full_quick")]
    if names:
        presets = [preset for preset in presets if preset["name"] in names]
    return presets


def run_preset(args: argparse.Namespace, preset: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(args.output_root) / preset["name"]
    metrics_path = output_dir / "metrics.json"
    if metrics_path.exists() and not args.force:
        print(f"skip existing {preset['name']}", flush=True)
        return summarize(output_dir, preset)

    output_dir.mkdir(parents=True, exist_ok=True)
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
        preset["base_model"],
        "--epochs",
        str(preset["epochs"]),
        "--batch-size",
        str(preset["batch_size"]),
        "--grad-accum-steps",
        str(preset["grad_accum_steps"]),
        "--max-length",
        str(preset["max_length"]),
        "--lr",
        str(preset["lr"]),
        "--class-weight-mode",
        preset["class_weight_mode"],
        "--silver-weight-override",
        str(preset["silver_weight"]),
        "--cache-tokenization",
        "--tokenization-batch-size",
        str(args.tokenization_batch_size),
        "--log-every-steps",
        str(args.log_every_steps),
    ]
    if preset.get("max_train_rows"):
        command += ["--max-train-rows", str(preset["max_train_rows"])]
    if preset.get("freeze_encoder"):
        command.append("--freeze-encoder")
    if preset.get("unfreeze_last_n_layers"):
        command += ["--unfreeze-last-n-layers", str(preset["unfreeze_last_n_layers"])]
    if preset.get("gradient_checkpointing"):
        command.append("--gradient-checkpointing")
    if args.save_model:
        command.append("--save-model")

    stdout_path = output_dir / "train.out.log"
    stderr_path = output_dir / "train.err.log"
    print(f"run {preset['name']}", flush=True)
    print(" ".join(command), flush=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            command,
            cwd=args.repo_root,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            stdout.write(line)
            stdout.flush()
        code = proc.wait()
    if code != 0:
        failed = {
            "name": preset["name"],
            "status": "failed",
            "exit_code": code,
            "output_dir": str(output_dir),
            "stderr": str(stderr_path),
        }
        write_json(output_dir / "failed.json", failed)
        print(f"failed {preset['name']} exit={code}; see {stderr_path}", flush=True)
        return failed
    return summarize(output_dir, preset)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default="data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv")
    parser.add_argument("--output-root", default="data/ml_experiments/teacher_student_runs/large_model_presets_2026-06-04")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--phase", choices=["smoke", "quick", "all"], default="smoke")
    parser.add_argument("--preset", action="append", default=[])
    parser.add_argument("--tokenization-batch-size", type=int, default=512)
    parser.add_argument("--log-every-steps", type=int, default=500)
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    names = set(args.preset) if args.preset else None
    presets = selected_presets(names, args.phase)
    write_json(output_root / "large_model_preset_config.json", {"args": vars(args), "presets": presets})

    rows = []
    for preset in presets:
        rows.append(run_preset(args, preset))
        write_summary(output_root, rows)
    write_summary(output_root, rows)
    print(f"summary={output_root / 'large_model_preset_summary.md'}", flush=True)


if __name__ == "__main__":
    main()
