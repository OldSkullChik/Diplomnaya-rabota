#!/usr/bin/env python
"""Build per-label class-weight JSON presets from validation split errors."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def row_weight(row: dict[str, str]) -> float:
    try:
        return float(row.get("sample_weight", "1") or "1")
    except ValueError:
        return 1.0


def apply_weight_overrides(rows: list[dict[str, str]], gold_weight: float | None, silver_weight: float | None) -> None:
    for row in rows:
        source = row.get("label_source", "")
        if source == "gold_human" and gold_weight is not None:
            row["sample_weight"] = f"{gold_weight:g}"
        elif source == "silver_auto" and silver_weight is not None:
            row["sample_weight"] = f"{silver_weight:g}"


def split_rows(rows: list[dict[str, str]], split: str) -> list[dict[str, str]]:
    return [row for row in rows if str(row.get("split", "")).strip().lower() == split]


def counts(rows: list[dict[str, str]], col: str, weighted: bool = False) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in rows:
        value = row.get(col)
        if value:
            result[value] += row_weight(row) if weighted else 1
    return result


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def balanced_weights(source_counts: Counter[str], labels: list[str], power: float = 1.0, max_weight: float = 0.0) -> dict[str, float]:
    total = sum(source_counts.values())
    if total <= 0:
        return {label: 1.0 for label in labels}
    weights: dict[str, float] = {}
    for label in labels:
        count = max(float(source_counts.get(label, 0)), 1.0)
        weight = total / (len(labels) * count)
        if power != 1.0:
            weight = weight**power
        weights[label] = float(weight)
    weighted_mean = sum(float(source_counts.get(label, 0)) * weights[label] for label in labels) / total
    if weighted_mean > 0:
        weights = {label: float(weight / weighted_mean) for label, weight in weights.items()}
    if max_weight > 0:
        weights = {label: min(weight, max_weight) for label, weight in weights.items()}
    return weights


def guarded_multiplier(stats: dict[str, Any]) -> tuple[float, str]:
    support = int(stats["support"])
    precision = float(stats["precision"])
    recall = float(stats["recall"])
    f1 = float(stats["f1"])
    fp = int(stats["fp"])
    fn = int(stats["fn"])
    tp = int(stats["tp"])
    if support == 0:
        return 1.0, "no validation support"
    if support < 3:
        return 1.0, "validation support below 3"

    multiplier = 1.0
    reasons: list[str] = []
    if recall < 0.15:
        multiplier *= 1.80
        reasons.append("very low recall")
    elif recall < 0.35:
        multiplier *= 1.45
        reasons.append("low recall")
    elif recall < 0.55:
        multiplier *= 1.20
        reasons.append("moderate recall deficit")

    if f1 < 0.15:
        multiplier *= 1.25
        reasons.append("very low f1")
    elif f1 < 0.30:
        multiplier *= 1.10
        reasons.append("low f1")

    if precision < 0.20 and fp >= max(3, tp + fn):
        multiplier *= 0.55
        reasons.append("too many false positives")
    elif precision < 0.35 and fp > fn:
        multiplier *= 0.75
        reasons.append("false positives dominate")

    return clamp(multiplier, 0.45, 2.20), "; ".join(reasons) or "kept"


def ratio_multiplier(stats: dict[str, Any]) -> tuple[float, str]:
    support = int(stats["support"])
    if support < 3:
        return 1.0, "validation support below 3"
    precision = float(stats["precision"])
    recall = float(stats["recall"])
    f1 = float(stats["f1"])
    fp = int(stats["fp"])
    fn = int(stats["fn"])
    multiplier = ((fn + 1.0) / (fp + 1.0)) ** 0.35
    reasons = [f"fn/fp ratio={fn}/{fp}"]
    if recall < 0.40:
        multiplier *= 1.15
        reasons.append("recall below 0.40")
    if precision < 0.30 and fp > fn:
        multiplier *= 0.80
        reasons.append("precision guard")
    if f1 < 0.20:
        multiplier *= 1.10
        reasons.append("f1 below 0.20")
    return clamp(multiplier, 0.50, 1.90), "; ".join(reasons)


def weak_only_multiplier(target: str, stats: dict[str, Any]) -> tuple[float, str]:
    weak_targets = {"authority_aspect", "appeal_type", "responsible_party", "quality"}
    support = int(stats["support"])
    f1 = float(stats["f1"])
    recall = float(stats["recall"])
    precision = float(stats["precision"])
    fp = int(stats["fp"])
    fn = int(stats["fn"])
    if target not in weak_targets:
        return 1.0, "not a weak target"
    if support < 3:
        return 1.0, "validation support below 3"
    multiplier = 1.0
    reasons: list[str] = []
    if f1 < 0.20 or recall < 0.25:
        multiplier *= 1.70
        reasons.append("weak target rare class boost")
    elif f1 < 0.35 or recall < 0.45:
        multiplier *= 1.30
        reasons.append("weak target mild boost")
    if precision < 0.25 and fp > fn:
        multiplier *= 0.65
        reasons.append("precision guard")
    return clamp(multiplier, 0.50, 2.00), "; ".join(reasons) or "kept"


PRESET_BUILDERS = {
    "individual_guarded": guarded_multiplier,
    "individual_fn_fp_ratio": ratio_multiplier,
    "individual_weak_only": weak_only_multiplier,
}


def target_weight_cap(target: str, label: str, base_weight: float) -> float:
    if base_weight <= 20:
        return 60.0
    if target in {"jkh_relevance", "sarcasm", "quality"}:
        return 120.0
    return 180.0


def proposed_weight(base_weight: float, multiplier: float, cap: float) -> float:
    if abs(multiplier - 1.0) < 1e-9:
        return base_weight
    if multiplier > 1.0 and base_weight > cap:
        return base_weight
    return clamp(base_weight * multiplier, 0.03, cap)


def build(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_metrics = json.loads((Path(args.checkpoint_dir) / "metrics.json").read_text(encoding="utf-8"))
    split_reports = json.loads(Path(args.split_report_json).read_text(encoding="utf-8"))
    target_cols = checkpoint_metrics["target_cols"]

    rows = [row for row in read_csv(Path(args.input_csv)) if all(row.get(col) for col in target_cols)]
    apply_weight_overrides(rows, args.gold_weight_override, args.silver_weight_override)
    train_rows = split_rows(rows, "train")
    gold_train_rows = [row for row in train_rows if row.get("label_source") == "gold_human"]

    train_counts = {col: counts(train_rows, col, weighted=True) for col in target_cols}
    gold_counts = {col: counts(gold_train_rows, col, weighted=False) for col in target_cols}
    val_reports = split_reports["splits"]["val"]
    base_weights = checkpoint_metrics.get("class_weights", {})

    presets: dict[str, dict[str, dict[str, float]]] = {
        name: {col: {} for col in target_cols}
        for name in PRESET_BUILDERS
    }
    rationale_rows: list[dict[str, Any]] = []

    for col in target_cols:
        labels = [label for label, _ in sorted(checkpoint_metrics["label_maps"][col].items(), key=lambda item: item[1])]
        if col not in base_weights:
            base_weights[col] = balanced_weights(
                train_counts[col],
                labels,
                power=float(checkpoint_metrics.get("class_weight_power", 1.0)),
                max_weight=float(checkpoint_metrics.get("class_weight_max", 0.0) or 0.0),
            )
        for label in labels:
            stats = val_reports[col]["per_class"][label]
            base_weight = float(base_weights[col][label])
            for preset_name, builder in PRESET_BUILDERS.items():
                if preset_name == "individual_weak_only":
                    multiplier, reason = builder(col, stats)
                else:
                    multiplier, reason = builder(stats)
                cap = target_weight_cap(col, label, base_weight)
                proposed = proposed_weight(base_weight, multiplier, cap)
                presets[preset_name][col][label] = round(proposed, 8)
                rationale_rows.append(
                    {
                        "preset": preset_name,
                        "target": col,
                        "label": label,
                        "base_weight": round(base_weight, 6),
                        "proposed_weight": round(proposed, 6),
                        "multiplier": round(proposed / base_weight if base_weight else 1.0, 6),
                        "cap": cap,
                        "val_support": stats["support"],
                        "val_tp": stats["tp"],
                        "val_fp": stats["fp"],
                        "val_fn": stats["fn"],
                        "val_precision": round(float(stats["precision"]), 6),
                        "val_recall": round(float(stats["recall"]), 6),
                        "val_f1": round(float(stats["f1"]), 6),
                        "weighted_train_count": round(float(train_counts[col].get(label, 0)), 4),
                        "gold_train_count": gold_counts[col].get(label, 0),
                        "reason": reason,
                    }
                )

    for preset_name, weights in presets.items():
        (output_dir / f"{preset_name}.json").write_text(
            json.dumps(weights, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    write_csv(
        output_dir / "individual_class_weight_rationale.csv",
        rationale_rows,
        [
            "preset",
            "target",
            "label",
            "base_weight",
            "proposed_weight",
            "multiplier",
            "cap",
            "val_support",
            "val_tp",
            "val_fp",
            "val_fn",
            "val_precision",
            "val_recall",
            "val_f1",
            "weighted_train_count",
            "gold_train_count",
            "reason",
        ],
    )

    lines = [
        "# Individual Class Weight Presets",
        "",
        f"- Input: `{args.input_csv}`",
        f"- Checkpoint: `{args.checkpoint_dir}`",
        f"- Validation report: `{args.split_report_json}`",
        "",
        "## Presets",
        "",
    ]
    for preset_name in presets:
        changed = [row for row in rationale_rows if row["preset"] == preset_name and abs(float(row["multiplier"]) - 1.0) > 1e-6]
        lines.append(f"- `{preset_name}`: changed `{len(changed)}` class weights.")
    lines += ["", "## Strongest Adjustments", ""]
    for preset_name in presets:
        changed = [
            row for row in rationale_rows
            if row["preset"] == preset_name and abs(float(row["multiplier"]) - 1.0) > 1e-6
        ]
        changed.sort(key=lambda row: abs(float(row["multiplier"]) - 1.0), reverse=True)
        lines.append(f"### `{preset_name}`")
        for row in changed[:20]:
            lines.append(
                "- "
                f"`{row['target']}.{row['label']}`: "
                f"{row['base_weight']} -> {row['proposed_weight']} "
                f"(x{row['multiplier']}; val support={row['val_support']}; "
                f"tp/fp/fn={row['val_tp']}/{row['val_fp']}/{row['val_fn']}; "
                f"f1={row['val_f1']}; {row['reason']})"
            )
        lines.append("")
    (output_dir / "individual_class_weight_rationale.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "presets": list(presets)}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--split-report-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gold-weight-override", type=float, default=None)
    parser.add_argument("--silver-weight-override", type=float, default=0.3)
    return parser.parse_args()


def main() -> None:
    build(parse_args())


if __name__ == "__main__":
    main()
