#!/usr/bin/env python
"""Prepare reproducible old/new datasets for RuBERT benchmark experiments."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path


COMMON_FIELDS = ["text", "post_text", "sentiment", "appeal_type", "common_addressee"]
NEW_FULL_FIELDS = [
    "text",
    "post_text",
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]


SENTIMENT_MAP = {
    "negative": "negative",
    "neutral": "neutral",
    "positive": "positive",
    "mixed": "mixed",
    "негативный": "negative",
    "негативная": "negative",
    "нейтральный": "neutral",
    "нейтральная": "neutral",
    "позитивный": "positive",
    "позитивная": "positive",
}

APPEAL_MAP = {
    "complaint": "complaint",
    "question": "question",
    "request": "request",
    "demand": "demand",
    "suggestion": "suggestion",
    "gratitude": "gratitude",
    "opinion": "opinion",
    "info": "info",
    "other": "other",
    "жалоба": "complaint",
    "вопрос": "question",
    "просьба": "request",
    "требование": "demand",
    "предложение": "suggestion",
    "благодарность": "gratitude",
    "мнение": "opinion",
    "информирование": "info",
    "другое": "other",
}

OLD_ADDRESSEE_MAP = {
    "ук/жкх": "jkh_organization",
    "администрация/власть": "authority",
    "без адресата": "none_or_unknown",
    "нет адресата": "none_or_unknown",
    "конкретное лицо": "specific_person",
    "сообщество/жители": "residents",
}

NEW_RESPONSIBLE_TO_COMMON = {
    "management_company": "jkh_organization",
    "resource_provider": "jkh_organization",
    "housing_inspection": "authority",
    "waste_operator": "jkh_organization",
    "local_administration": "authority",
    "residents": "residents",
    "specific_person": "specific_person",
    "unknown": "none_or_unknown",
    "not_applicable": "none_or_unknown",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def norm_key(value: object) -> str:
    return clean(value).casefold()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_old_common(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        sentiment = SENTIMENT_MAP.get(norm_key(row.get("sentiment")))
        appeal_type = APPEAL_MAP.get(norm_key(row.get("appeal_type")))
        common_addressee = OLD_ADDRESSEE_MAP.get(norm_key(row.get("addressee")))
        text = clean(row.get("text"))
        if not text or not sentiment or not appeal_type or not common_addressee:
            continue
        normalized.append(
            {
                "source_project": "old",
                "text": text,
                "post_text": clean(row.get("post_text")),
                "sentiment": sentiment,
                "appeal_type": appeal_type,
                "common_addressee": common_addressee,
            }
        )
    return normalized


def normalize_new(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    common_rows = []
    full_rows = []
    for row in rows:
        status = clean(row.get("status"))
        if status and status != "approved":
            continue

        text = clean(row.get("text"))
        if not text:
            continue

        sentiment = SENTIMENT_MAP.get(norm_key(row.get("sentiment")))
        appeal_type = APPEAL_MAP.get(norm_key(row.get("appeal_type")))
        common_addressee = NEW_RESPONSIBLE_TO_COMMON.get(norm_key(row.get("responsible_party")))
        post_text = clean(row.get("post_text"))
        if sentiment and appeal_type and common_addressee:
            common_rows.append(
                {
                    "source_project": "new",
                    "text": text,
                    "post_text": post_text,
                    "sentiment": sentiment,
                    "appeal_type": appeal_type,
                    "common_addressee": common_addressee,
                }
            )

        full = {"source_project": "new", "text": text, "post_text": post_text}
        complete = True
        for field in NEW_FULL_FIELDS:
            if field in {"text", "post_text"}:
                continue
            value = clean(row.get(field))
            if not value:
                complete = False
                break
            full[field] = value
        if complete:
            full_rows.append(full)

    return common_rows, full_rows


def distribution(rows: list[dict[str, str]], fields: list[str]) -> dict[str, dict[str, int]]:
    result = {}
    for field in fields:
        result[field] = dict(Counter(row.get(field, "") for row in rows).most_common())
    return result


def write_summary(path: Path, summary: dict) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# RuBERT benchmark dataset summary",
        "",
        f"Seed: `{summary['seed']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Distributions", ""]
    for dataset, dist in summary["distributions"].items():
        lines += [f"### {dataset}", ""]
        for field, values in dist.items():
            lines.append(f"- `{field}`: {values}")
        lines.append("")
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-approved", default="data/exports/approved_annotations.csv")
    parser.add_argument("--old-labeled", default="Normalizaciya/structured/dataset_labeled.csv")
    parser.add_argument("--output-dir", default="data/ml_experiments/rubert_benchmarks")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new_path = Path(args.new_approved)
    old_path = Path(args.old_labeled)
    output_dir = Path(args.output_dir)

    if not new_path.exists():
        raise SystemExit(
            f"New approved export not found: {new_path}\n"
            "Create it on the server with: python manage.py export_annotations data/exports/approved_annotations.csv"
        )
    if not old_path.exists():
        raise SystemExit(f"Old labeled dataset not found: {old_path}")

    rng = random.Random(args.seed)
    new_common, new_full = normalize_new(read_csv(new_path))
    old_common_all = normalize_old_common(read_csv(old_path))

    n_new = len(new_common)
    if n_new == 0:
        raise SystemExit(f"No usable approved new rows found in {new_path}")
    if len(old_common_all) < n_new:
        raise SystemExit(f"Old dataset has only {len(old_common_all)} usable rows, but new dataset has {n_new}")

    old_common_equal = rng.sample(old_common_all, n_new)

    test1_dir = output_dir / "test1_equal_common_axes"
    test2_dir = output_dir / "test2_all_available"

    write_csv(test1_dir / "new_common_all.csv", new_common, ["source_project"] + COMMON_FIELDS)
    write_csv(test1_dir / "old_common_equal_random.csv", old_common_equal, ["source_project"] + COMMON_FIELDS)
    write_csv(test2_dir / "new_common_all.csv", new_common, ["source_project"] + COMMON_FIELDS)
    write_csv(test2_dir / "old_common_all.csv", old_common_all, ["source_project"] + COMMON_FIELDS)
    write_csv(test2_dir / "new_full_all.csv", new_full, ["source_project"] + NEW_FULL_FIELDS)

    summary = {
        "seed": args.seed,
        "inputs": {"new_approved": str(new_path), "old_labeled": str(old_path)},
        "counts": {
            "new_common_all": len(new_common),
            "new_full_all": len(new_full),
            "old_common_all": len(old_common_all),
            "old_common_equal_random": len(old_common_equal),
        },
        "distributions": {
            "test1_new_common_all": distribution(new_common, COMMON_FIELDS[2:]),
            "test1_old_common_equal_random": distribution(old_common_equal, COMMON_FIELDS[2:]),
            "test2_old_common_all": distribution(old_common_all, COMMON_FIELDS[2:]),
            "test2_new_full_all": distribution(new_full, NEW_FULL_FIELDS[2:]),
        },
    }
    write_summary(output_dir / "summary.json", summary)
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    print(f"Prepared benchmark datasets in {output_dir}")


if __name__ == "__main__":
    main()
