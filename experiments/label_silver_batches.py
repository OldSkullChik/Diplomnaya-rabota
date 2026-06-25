#!/usr/bin/env python
"""Label exported unresolved records for teacher-student RuBERT training.

The script fills the offline label columns in every silver batch using the
current automatic teacher rule labeler. Previously audited offline labels can be passed as
overrides by ``record_id`` so hand-polished rows keep their final labels.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any


LABEL_FIELDS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]

OFFLINE_FIELDS = ["offline_action", *LABEL_FIELDS, "offline_comment"]

ALLOWED_VALUES = {
    "offline_action": {"approve", "deleted_confirm", "skip"},
    "jkh_relevance": {"yes", "no", "unsure"},
    "jkh_topic": {
        "not_jkh",
        "heating_hot_water",
        "cold_water_sewerage",
        "waste_cleaning",
        "house_common_property",
        "yard_area",
        "payments_tariffs",
        "management_company",
        "public_authorities",
        "other_jkh",
    },
    "authority_aspect": {
        "not_applicable",
        "no_action",
        "slow_response",
        "poor_quality",
        "communication",
        "tariff_policy",
        "supervision",
        "positive_feedback",
        "other",
    },
    "sentiment": {"negative", "neutral", "positive", "mixed"},
    "appeal_type": {
        "complaint",
        "question",
        "request",
        "demand",
        "suggestion",
        "gratitude",
        "opinion",
        "info",
        "other",
    },
    "responsible_party": {
        "management_company",
        "resource_provider",
        "local_administration",
        "housing_inspection",
        "waste_operator",
        "residents",
        "specific_person",
        "unknown",
        "not_applicable",
    },
    "sarcasm": {"no", "yes", "unsure"},
    "quality": {"normal", "difficult", "spam", "duplicate", "no_context"},
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def load_rules_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("offline_teacher_rules", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot import rules module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "labels_for_row"):
        raise SystemExit(f"Rules module has no labels_for_row(row): {path}")
    return module


def read_override_labels(paths: list[Path]) -> dict[str, dict[str, str]]:
    overrides: dict[str, dict[str, str]] = {}
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                record_id = clean(row.get("record_id"))
                if not record_id:
                    continue
                labels = {field: clean(row.get(field)) for field in OFFLINE_FIELDS}
                labels["offline_comment"] = labels["offline_comment"] or "Audited offline override."
                overrides[record_id] = labels
    return overrides


def validate_labels(labels: dict[str, str]) -> list[str]:
    errors = []
    for field, allowed in ALLOWED_VALUES.items():
        value = clean(labels.get(field))
        if value not in allowed:
            errors.append(f"{field}={value!r}")
    if labels.get("jkh_relevance") == "no" and labels.get("jkh_topic") != "not_jkh":
        errors.append("jkh_relevance=no requires jkh_topic=not_jkh")
    if labels.get("jkh_topic") == "not_jkh" and labels.get("jkh_relevance") != "no":
        errors.append("jkh_topic=not_jkh requires jkh_relevance=no")
    return errors


def label_row(row: dict[str, str], rules: ModuleType, overrides: dict[str, dict[str, str]]) -> tuple[dict[str, str], str]:
    record_id = clean(row.get("record_id"))
    if record_id in overrides:
        labels = dict(overrides[record_id])
        labels["offline_comment"] = labels["offline_comment"] or "Audited offline override."
        return labels, "override"

    labels = rules.labels_for_row(
        {
            "post_text": clean(row.get("post_text")),
            "comment_text": clean(row.get("comment_text")),
        }
    )
    labels = {field: clean(labels.get(field)) for field in OFFLINE_FIELDS}
    labels["offline_comment"] = labels["offline_comment"] or "Teacher silver label."
    return labels, "generated"


def ensure_fields(fieldnames: list[str] | None) -> list[str]:
    fields = list(fieldnames or [])
    for field in OFFLINE_FIELDS:
        if field not in fields:
            fields.insert(0, field)
    return fields


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Silver batch labeling summary",
        "",
        f"- input_dir: `{summary['input_dir']}`",
        f"- output_dir: `{summary['output_dir']}`",
        f"- combined_output: `{summary['combined_output']}`",
        f"- rules_module: `{summary['rules_module']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Label Distributions", ""]
    for field, values in summary["distributions"].items():
        lines.append(f"- `{field}`: {values}")
    lines += ["", "## Batch Rows", ""]
    for batch in summary["batches"]:
        lines.append(
            f"- `{batch['input']}`: rows={batch['rows']}, generated={batch['generated']}, "
            f"overrides={batch['overrides']}, validation_errors={batch['validation_errors']}"
        )
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="Directory with silver batch CSV files.")
    parser.add_argument("--output-dir", required=True, help="Directory for labeled per-batch CSV files.")
    parser.add_argument("--combined-output", required=True, help="Combined labeled CSV output path.")
    parser.add_argument("--rules-module", required=True, help="Python file with labels_for_row(row).")
    parser.add_argument("--override-labeled", nargs="*", default=[], help="Already audited labeled CSV files.")
    parser.add_argument("--summary-output", default="", help="Optional summary JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    combined_output = Path(args.combined_output)
    rules_module = Path(args.rules_module)
    summary_output = Path(args.summary_output) if args.summary_output else combined_output.with_suffix(".summary.json")

    rules = load_rules_module(rules_module)
    overrides = read_override_labels([Path(path) for path in args.override_labeled])
    batch_paths = sorted(input_dir.glob("*.csv"))
    if not batch_paths:
        raise SystemExit(f"No CSV batches found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    combined_output.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    generated_rows = 0
    override_rows = 0
    validation_errors = 0
    duplicate_records = 0
    seen_records: set[str] = set()
    distributions = {field: Counter() for field in ["offline_action", *LABEL_FIELDS]}
    pool_distribution = Counter()
    batch_summaries = []
    sample_errors: list[dict[str, Any]] = []

    combined_fields: list[str] | None = None
    with combined_output.open("w", encoding="utf-8-sig", newline="") as combined_handle:
        combined_writer: csv.DictWriter[str] | None = None

        for batch_path in batch_paths:
            with batch_path.open("r", encoding="utf-8-sig", newline="") as input_handle:
                reader = csv.DictReader(input_handle)
                fields = ensure_fields(reader.fieldnames)
                if combined_fields is None:
                    combined_fields = fields
                    combined_writer = csv.DictWriter(combined_handle, fieldnames=combined_fields, extrasaction="ignore")
                    combined_writer.writeheader()

                output_path = output_dir / batch_path.name.replace(".csv", "_labeled.csv")
                batch_rows = 0
                batch_generated = 0
                batch_overrides = 0
                batch_errors = 0

                with output_path.open("w", encoding="utf-8-sig", newline="") as output_handle:
                    writer = csv.DictWriter(output_handle, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()

                    for row in reader:
                        labels, source = label_row(row, rules, overrides)
                        row.update(labels)
                        row["offline_comment"] = clean(row.get("offline_comment"))

                        record_id = clean(row.get("record_id"))
                        if record_id in seen_records:
                            duplicate_records += 1
                        elif record_id:
                            seen_records.add(record_id)

                        errors = validate_labels(labels)
                        if errors:
                            validation_errors += 1
                            batch_errors += 1
                            if len(sample_errors) < 20:
                                sample_errors.append({"record_id": record_id, "errors": errors})

                        for field in distributions:
                            distributions[field][clean(row.get(field))] += 1
                        pool_distribution[clean(row.get("sampling_pool"))] += 1

                        writer.writerow(row)
                        if combined_writer is None:
                            raise RuntimeError("combined_writer was not initialized")
                        combined_writer.writerow(row)

                        batch_rows += 1
                        total_rows += 1
                        if source == "override":
                            batch_overrides += 1
                            override_rows += 1
                        else:
                            batch_generated += 1
                            generated_rows += 1

                batch_summaries.append(
                    {
                        "input": batch_path.name,
                        "output": output_path.name,
                        "rows": batch_rows,
                        "generated": batch_generated,
                        "overrides": batch_overrides,
                        "validation_errors": batch_errors,
                    }
                )
                print(
                    f"{batch_path.name}: rows={batch_rows} generated={batch_generated} "
                    f"overrides={batch_overrides} validation_errors={batch_errors}"
                )

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "combined_output": str(combined_output),
        "rules_module": str(rules_module),
        "override_files": args.override_labeled,
        "counts": {
            "batches": len(batch_paths),
            "rows": total_rows,
            "generated": generated_rows,
            "overrides": override_rows,
            "override_records_loaded": len(overrides),
            "duplicate_records": duplicate_records,
            "validation_errors": validation_errors,
            "unique_records": len(seen_records),
        },
        "pool_distribution": dict(pool_distribution.most_common()),
        "distributions": {field: dict(counter.most_common()) for field, counter in distributions.items()},
        "batches": batch_summaries,
        "sample_errors": sample_errors,
    }
    write_summary(summary_output, summary)

    print(f"combined={combined_output}")
    print(f"summary={summary_output}")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
