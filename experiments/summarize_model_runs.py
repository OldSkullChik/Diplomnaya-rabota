#!/usr/bin/env python
"""Summarize multitask classifier run directories into CSV/Markdown."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def mean_macro(metrics: dict[str, Any]) -> float:
    values = [
        value["macro_f1"]
        for value in metrics.values()
        if isinstance(value, dict) and "macro_f1" in value
    ]
    return sum(values) / max(len(values), 1)


def best_val(metrics: dict[str, Any]) -> float:
    return max((float(item.get("mean_val_macro_f1", 0.0)) for item in metrics.get("history", [])), default=0.0)


def summarize_run(path: Path) -> dict[str, Any]:
    metrics = read_json(path / "metrics.json")
    row: dict[str, Any] = {
        "run": path.name,
        "path": str(path),
        "base_model": metrics.get("base_model"),
        "rows_total": metrics.get("rows", {}).get("total"),
        "rows_train": metrics.get("rows", {}).get("train"),
        "rows_val": metrics.get("rows", {}).get("val"),
        "rows_test": metrics.get("rows", {}).get("test"),
        "epochs": metrics.get("epochs"),
        "batch_size": metrics.get("batch_size"),
        "grad_accum_steps": metrics.get("grad_accum_steps"),
        "effective_batch_size": metrics.get("effective_batch_size"),
        "max_length": metrics.get("max_length"),
        "lr": metrics.get("lr"),
        "dropout": metrics.get("dropout"),
        "class_weight_mode": metrics.get("class_weight_mode"),
        "silver_weight": metrics.get("silver_weight_override"),
        "freeze_encoder": metrics.get("freeze_encoder"),
        "unfreeze_last_n_layers": metrics.get("unfreeze_last_n_layers"),
        "gradient_checkpointing": metrics.get("gradient_checkpointing"),
        "trainable_parameters": metrics.get("trainable_parameters"),
        "total_parameters": metrics.get("total_parameters"),
        "best_val_macro_f1": best_val(metrics),
        "test_mean_macro_f1": mean_macro(metrics.get("test_metrics", {})),
    }
    for field in metrics.get("target_cols", []):
        metric = metrics.get("test_metrics", {}).get(field, {})
        row[f"{field}_macro_f1"] = metric.get("macro_f1")
        row[f"{field}_accuracy"] = metric.get("accuracy")
    row["target_cols"] = ",".join(metrics.get("target_cols", []))
    return row


def collect_target_cols(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for field in str(row.get("target_cols") or "").split(","):
            if field and field not in fields:
                fields.append(field)
    return fields


def write_csv(path: Path, rows: list[dict[str, Any]], target_cols: list[str]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    for field in target_cols:
        for suffix in ("macro_f1", "accuracy"):
            key = f"{field}_{suffix}"
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, rows: list[dict[str, Any]], target_cols: list[str]) -> None:
    lines = [
        "# Model Run Summary",
        "",
        "| Run | Model | Train rows | Best val macro-F1 | Test mean macro-F1 | Preset |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        preset = (
            f"len={row.get('max_length')}, lr={row.get('lr')}, "
            f"freeze={row.get('freeze_encoder')}, last={row.get('unfreeze_last_n_layers')}, "
            f"gc={row.get('gradient_checkpointing')}"
        )
        lines.append(
            f"| `{row['run']}` | `{row.get('base_model')}` | {row.get('rows_train')} | "
            f"{float(row.get('best_val_macro_f1') or 0):.4f} | "
            f"{float(row.get('test_mean_macro_f1') or 0):.4f} | {preset} |"
        )
    lines += [
        "",
        "## Per-Head Test Macro-F1",
        "",
        "| Run | " + " | ".join(target_cols) + " |",
        "| --- | " + " | ".join(["---:"] * len(target_cols)) + " |",
    ]
    for row in rows:
        values = [
            f"{float(row[f'{field}_macro_f1']):.4f}" if row.get(f"{field}_macro_f1") is not None else ""
            for field in target_cols
        ]
        lines.append(f"| `{row['run']}` | " + " | ".join(values) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for run_dir in args.run_dir:
        root = Path(run_dir)
        if (root / "metrics.json").exists():
            rows.append(summarize_run(root))
        else:
            for metrics_path in sorted(root.glob("*/metrics.json")):
                rows.append(summarize_run(metrics_path.parent))
    rows = sorted(rows, key=lambda row: float(row.get("best_val_macro_f1") or 0), reverse=True)
    target_cols = collect_target_cols(rows)
    write_csv(output_dir / "model_run_summary.csv", rows, target_cols)
    write_md(output_dir / "model_run_summary.md", rows, target_cols)
    (output_dir / "model_run_summary.json").write_text(
        json.dumps({"target_cols": target_cols, "runs": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output_dir / "model_run_summary.md")


if __name__ == "__main__":
    main()
