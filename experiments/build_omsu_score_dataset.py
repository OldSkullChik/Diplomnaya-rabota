#!/usr/bin/env python
"""Append OMSU score/class columns to a teacher-student dataset."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from omsu_scoring import calculate_omsu_score


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build(args: argparse.Namespace) -> None:
    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)
    rows = read_csv(input_path)
    output_rows: list[dict[str, Any]] = []
    counters = {
        "omsu_impact_class": Counter(),
        "omsu_negative_signal": Counter(),
        "split_impact": Counter(),
        "split_negative": Counter(),
    }
    score_sum = 0
    for row in rows:
        score = calculate_omsu_score(row)
        out = dict(row)
        out["omsu_score"] = str(score.score)
        out["omsu_impact_class"] = score.impact_class
        out["omsu_negative_signal"] = score.negative_signal
        out["omsu_scope_weight"] = f"{score.scope_weight:.4f}"
        out["omsu_confidence_weight"] = f"{score.confidence_weight:.4f}"
        out["omsu_score_reason"] = score.reason
        output_rows.append(out)
        counters["omsu_impact_class"][score.impact_class] += 1
        counters["omsu_negative_signal"][score.negative_signal] += 1
        split = row.get("split", "")
        counters["split_impact"][(split, score.impact_class)] += 1
        counters["split_negative"][(split, score.negative_signal)] += 1
        score_sum += score.score

    fieldnames = list(rows[0].keys()) + [
        "omsu_score",
        "omsu_impact_class",
        "omsu_negative_signal",
        "omsu_scope_weight",
        "omsu_confidence_weight",
        "omsu_score_reason",
    ]
    write_csv(output_path, output_rows, fieldnames)

    summary = {
        "input_csv": str(input_path),
        "output_csv": str(output_path),
        "rows": len(output_rows),
        "mean_omsu_score": score_sum / max(len(output_rows), 1),
        "omsu_impact_class": dict(counters["omsu_impact_class"].most_common()),
        "omsu_negative_signal": dict(counters["omsu_negative_signal"].most_common()),
        "split_impact": {f"{split}:{label}": count for (split, label), count in counters["split_impact"].most_common()},
        "split_negative": {f"{split}:{label}": count for (split, label), count in counters["split_negative"].most_common()},
    }
    summary_path = output_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    return parser.parse_args()


def main() -> None:
    build(parse_args())


if __name__ == "__main__":
    main()
