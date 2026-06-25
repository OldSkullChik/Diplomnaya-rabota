#!/usr/bin/env python
"""Build a targeted pseudo-gold layer for weak taxonomy classes.

Pseudo-gold is not human gold. It is a teacher-assisted training layer selected
from silver records by class deficits, model agreement/confidence, and explicit
text anchors. Gold validation/test rows remain unchanged for evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
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

WEAK_AXES = ["jkh_topic", "authority_aspect", "appeal_type", "responsible_party", "quality"]


TARGET_MIN = {
    "jkh_relevance": {"yes": 1000, "unsure": 80},
    "jkh_topic": {
        "yard_area": 350,
        "heating_hot_water": 350,
        "waste_cleaning": 350,
        "public_authorities": 350,
        "cold_water_sewerage": 350,
        "other_jkh": 250,
        "payments_tariffs": 300,
        "management_company": 250,
        "house_common_property": 250,
    },
    "authority_aspect": {
        "poor_quality": 350,
        "no_action": 350,
        "communication": 300,
        "other": 200,
        "slow_response": 300,
        "positive_feedback": 250,
        "supervision": 250,
        "tariff_policy": 250,
    },
    "appeal_type": {
        "question": 350,
        "complaint": 350,
        "suggestion": 300,
        "gratitude": 250,
        "request": 250,
        "demand": 220,
        "other": 300,
    },
    "responsible_party": {
        "local_administration": 350,
        "management_company": 300,
        "unknown": 250,
        "resource_provider": 280,
        "waste_operator": 250,
        "residents": 220,
        "specific_person": 120,
        "housing_inspection": 220,
    },
    "sarcasm": {"unsure": 250},
    "quality": {"spam": 350, "difficult": 250, "duplicate": 80},
}


ANCHORS: dict[str, dict[str, list[str]]] = {
    "jkh_relevance": {
        "yes": [
            r"\bжкх\b",
            r"коммунальн",
            r"управляющ\w*\s+компан",
            r"\bук\b",
            r"отоплен",
            r"горяч\w*\s+вод",
            r"холодн\w*\s+вод",
            r"канализац",
            r"мусор",
            r"тко\b",
            r"контейнер",
            r"двор",
            r"придомов",
            r"капремонт",
            r"тариф",
        ],
        "unsure": [r"не\s+понят", r"вроде", r"похоже", r"может"],
    },
    "jkh_topic": {
        "yard_area": [r"двор", r"придомов", r"газон", r"лавоч", r"детск\w*\s+площад", r"парковк", r"подъездн\w*\s+путь"],
        "heating_hot_water": [r"отоплен", r"батаре", r"теплоснаб", r"теплоэнерго", r"котельн", r"горяч\w*\s+вод"],
        "waste_cleaning": [r"мусор", r"\bтко\b", r"контейнер", r"свалк", r"помойк", r"отход", r"мусоровоз", r"регоператор"],
        "public_authorities": [r"администрац", r"мэр", r"глава", r"муниципал", r"чиновник", r"губернатор", r"омсу"],
        "cold_water_sewerage": [r"холодн\w*\s+вод", r"водоснаб", r"водоканал", r"канализац", r"сток", r"ливнев", r"колодц", r"затоп"],
        "other_jkh": [r"\bжкх\b", r"коммунальн", r"коммуналк"],
        "payments_tariffs": [r"тариф", r"квитанц", r"плат[её]ж", r"начисл", r"сч[её]тчик", r"оплат", r"капремонт"],
        "management_company": [r"управляющ\w*\s+компан", r"\bук\b", r"домоуправ", r"\bтсж\b", r"управдом"],
        "house_common_property": [r"подъезд", r"крыша", r"подвал", r"лифт", r"фасад", r"общедом", r"\bмкд\b", r"домофон"],
    },
    "authority_aspect": {
        "poor_quality": [r"плохо", r"ужас", r"некачествен", r"криво", r"гряз", r"бардак", r"разбит", r"развал", r"халтур"],
        "no_action": [r"ничего\s+не\s+дел", r"не\s+дела[ею]т", r"бездейств", r"нет\s+реакц", r"игнор", r"всем\s+плевать", r"не\s+реша"],
        "communication": [r"ответ", r"сообщ", r"звон", r"обращ", r"поясн", r"уточн", r"отписк"],
        "other": [r"ответствен", r"вопрос", r"проблем"],
        "slow_response": [r"когда", r"сколько\s+можно", r"до\s+сих\s+пор", r"жд[её]м", r"месяц", r"год", r"срок", r"не\s+дожд"],
        "positive_feedback": [r"спасибо", r"благодар", r"молодц", r"хорошо", r"отлично", r"сделали", r"решили"],
        "supervision": [r"провер", r"контрол", r"надзор", r"прокурат", r"жилищн\w*\s+инспек", r"\bгжи\b", r"штраф"],
        "tariff_policy": [r"тариф", r"плата", r"плат[её]ж", r"квитанц", r"начисл", r"подорож", r"цена"],
    },
    "appeal_type": {
        "complaint": [r"жалоб", r"плохо", r"ужас", r"не\s+работ", r"нет\s+", r"проблем", r"невозможно"],
        "demand": [r"треб", r"должн", r"обяз", r"немедлен", r"верните", r"сделайте", r"прекратите"],
        "request": [r"прошу", r"просьб", r"пожалуйста", r"подскажите", r"помогите", r"можно\s+ли"],
        "question": [r"\?", r"когда", r"почему", r"куда", r"кто", r"как\s+", r"зачем"],
        "suggestion": [r"предлага", r"давайте", r"лучше\s+бы", r"нужно\s+бы", r"можно\s+сделать", r"стоит"],
        "gratitude": [r"спасибо", r"благодар", r"молодц", r"отлично", r"здорово"],
        "info": [r"сообщаем", r"информац", r"по\s+информац", r"добрый\s+день", r"будут\s+провед", r"работы\s+будут"],
        "other": [r"лол", r"хм", r"ладно", r"понятно"],
        "opinion": [r"считаю", r"думаю", r"кажется", r"мо[её]\s+мнение", r"по\s+моему"],
    },
    "responsible_party": {
        "local_administration": [r"администрац", r"мэр", r"глава", r"муниципал", r"правительств", r"никитин", r"шалабаев"],
        "management_company": [r"управляющ\w*\s+компан", r"\bук\b", r"домоуправ", r"\bтсж\b", r"управдом"],
        "unknown": [r"кто\s+ответ", r"непонятно\s+кто", r"не\s+ясно", r"ответственн"],
        "resource_provider": [r"водоканал", r"теплоэнерго", r"ресурсоснаб", r"\bмуп\b", r"\bтвк\b", r"котельн", r"электросет"],
        "waste_operator": [r"оператор\s+тко", r"регоператор", r"мусоровоз", r"вывоз\w*\s+мусор"],
        "residents": [r"жители", r"соседи", r"жильцы", r"люди", r"собачник", r"автовладельц"],
        "specific_person": [r"\[id\d+\|[^\]]+\]", r"\bникитин\b", r"\bшалабаев\b", r"\bлюлин\b", r"\bкочетков\b"],
        "housing_inspection": [r"жилищн\w*\s+инспек", r"\bгжи\b", r"госжилинспек"],
    },
    "sarcasm": {
        "yes": [r"ага", r"конечно", r"ну\s+да", r"смешно", r"сарказ", r"🤣", r"😂"],
        "unsure": [r"вроде\s+бы", r"как\s+бы", r"может\s+и", r"не\s+понятно"],
    },
    "quality": {
        "spam": [r"https?://", r"vk\.com/sticker", r"продам", r"заработ", r"реклам", r"подписывай"],
        "difficult": [r"не\s+понял", r"непонятно", r"ничего\s+не\s+понят", r"что\s+это", r"бред", r"без\s+контекст"],
        "duplicate": [r"дубл", r"повтор"],
    },
}


@dataclass
class Candidate:
    record_id: str
    axis: str
    label: str
    score: float
    anchor_hits: int
    reason: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def text_for(row: dict[str, str]) -> str:
    return f"{row.get('post_text', '')} {row.get('text', '')}".lower()


def anchor_hits(axis: str, label: str, text: str) -> int:
    patterns = ANCHORS.get(axis, {}).get(label, [])
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_row(row: dict[str, Any]) -> None:
    if (
        row.get("jkh_topic") not in {"", "not_jkh"}
        or row.get("authority_aspect") not in {"", "not_applicable"}
        or row.get("responsible_party") not in {"", "not_applicable"}
    ):
        row["jkh_relevance"] = "yes"
    if row.get("jkh_relevance") == "no":
        row["jkh_topic"] = "not_jkh"
        row["authority_aspect"] = "not_applicable"
        row["responsible_party"] = "not_applicable"
    if row.get("jkh_relevance") == "yes" and row.get("jkh_topic") == "not_jkh":
        row["jkh_topic"] = "other_jkh"


def gold_train_counts(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    counts = {axis: Counter() for axis in TARGET_COLS}
    for row in rows:
        if row.get("label_source") == "gold_human" and row.get("split") == "train":
            for axis in TARGET_COLS:
                counts[axis][row[axis]] += 1
    return counts


def train_counts(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    counts = {axis: Counter() for axis in TARGET_COLS}
    for row in rows:
        if row.get("split") == "train":
            for axis in TARGET_COLS:
                counts[axis][row[axis]] += 1
    return counts


def deficits(counts: dict[str, Counter[str]], multiplier: float) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for axis, targets in TARGET_MIN.items():
        for label, target in targets.items():
            need = max(0, int(round(target * multiplier)) - counts[axis][label])
            if need:
                out.setdefault(axis, {})[label] = need
    return out


def candidate_for(
    axis: str,
    label: str,
    source_row: dict[str, str],
    score_row: dict[str, str],
    text: str,
    allow_override: bool,
) -> Candidate | None:
    silver = score_row.get(f"{axis}_silver", source_row.get(axis, ""))
    pred = score_row.get(f"{axis}_pred", "")
    silver_prob = as_float(score_row.get(f"{axis}_silver_prob"))
    pred_prob = as_float(score_row.get(f"{axis}_pred_prob"))
    agree = score_row.get(f"{axis}_agree") == "1"
    hits = anchor_hits(axis, label, text)
    diamond_score = as_float(score_row.get("diamond_score"))
    agree_heads = as_int(score_row.get("agree_heads"))
    logic_ok = score_row.get("logic_ok") == "1"

    if not logic_ok:
        return None

    score = 0.0
    reasons: list[str] = []
    if silver == label:
        score += 0.35 + min(silver_prob, 1.0) * 0.25
        reasons.append(f"silver={label}:{silver_prob:.2f}")
    if pred == label:
        score += 0.30 + min(pred_prob, 1.0) * 0.25
        reasons.append(f"model={label}:{pred_prob:.2f}")
    if hits:
        score += min(hits, 3) * 0.18
        reasons.append(f"anchors={hits}")
    score += min(diamond_score, 1.0) * 0.12
    score += min(agree_heads / len(TARGET_COLS), 1.0) * 0.08

    if silver == label and agree and (silver_prob >= 0.28 or hits >= 1):
        pass
    elif pred == label and allow_override and pred_prob >= 0.35 and hits >= 1:
        pass
    elif allow_override and hits >= 2:
        pass
    else:
        return None

    return Candidate(
        record_id=source_row["record_id"],
        axis=axis,
        label=label,
        score=score,
        anchor_hits=hits,
        reason="; ".join(reasons),
    )


def build(args: argparse.Namespace) -> None:
    dataset_path = Path(args.input_csv)
    scores_path = Path(args.scores_csv)
    output_dir = Path(args.output_dir)
    rows = read_csv(dataset_path)
    score_rows = {row["record_id"]: row for row in read_csv(scores_path)}
    by_id = {row["record_id"]: row for row in rows}
    counts = gold_train_counts(rows)
    needs = deficits(counts, args.target_multiplier)

    silver_counts = {axis: Counter() for axis in TARGET_COLS}
    for row in rows:
        if row.get("label_source") == "silver_auto" and row.get("split") == "train":
            for axis in TARGET_COLS:
                silver_counts[axis][row[axis]] += 1

    candidates: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    for row in rows:
        if row.get("label_source") != "silver_auto" or row.get("split") != "train":
            continue
        rid = row["record_id"]
        score_row = score_rows.get(rid)
        if not score_row:
            continue
        full_text = text_for(row)
        for axis, labels in needs.items():
            for label in labels:
                allow_override = silver_counts[axis][label] == 0 or args.allow_overrides
                candidate = candidate_for(axis, label, row, score_row, full_text, allow_override)
                if candidate:
                    candidates[(axis, label)].append(candidate)

    selected_by_id: dict[str, dict[str, Any]] = {}
    selected_details: list[dict[str, Any]] = []
    filled: dict[str, dict[str, int]] = defaultdict(dict)
    for axis, labels in needs.items():
        for label, need in labels.items():
            pool = sorted(
                candidates.get((axis, label), []),
                key=lambda item: (item.score, item.anchor_hits),
                reverse=True,
            )
            used = 0
            for candidate in pool:
                if used >= need:
                    break
                source = by_id[candidate.record_id]
                out = selected_by_id.get(candidate.record_id)
                if out is None:
                    out = dict(source)
                    out["label_source"] = "pseudo_gold_auto"
                    out["sample_weight"] = f"{args.pseudo_weight:.3f}"
                    out["split"] = "train"
                    out["pseudo_gold_axes"] = ""
                    out["pseudo_gold_reasons"] = ""
                    selected_by_id[candidate.record_id] = out
                out[axis] = label
                axes = set(filter(None, out["pseudo_gold_axes"].split(";")))
                axes.add(f"{axis}:{label}")
                out["pseudo_gold_axes"] = ";".join(sorted(axes))
                reason_piece = f"{axis}:{label}:{candidate.score:.3f}:{candidate.reason}"
                out["pseudo_gold_reasons"] = (
                    f"{out['pseudo_gold_reasons']} | {reason_piece}" if out["pseudo_gold_reasons"] else reason_piece
                )
                selected_details.append(
                    {
                        "record_id": candidate.record_id,
                        "axis": axis,
                        "label": label,
                        "score": f"{candidate.score:.6f}",
                        "anchor_hits": candidate.anchor_hits,
                        "reason": candidate.reason,
                    }
                )
                used += 1
            filled[axis][label] = used

    pseudo_rows = list(selected_by_id.values())
    for row in pseudo_rows:
        normalize_row(row)

    gold_train = [dict(row) for row in rows if row.get("label_source") == "gold_human" and row.get("split") == "train"]
    gold_val_test = [dict(row) for row in rows if row.get("label_source") == "gold_human" and row.get("split") in {"val", "test"}]
    dataset_rows = gold_train + pseudo_rows + gold_val_test

    base_fields = list(rows[0].keys())
    extra_fields = ["pseudo_gold_axes", "pseudo_gold_reasons"]
    fieldnames = base_fields + [field for field in extra_fields if field not in base_fields]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "pseudo_gold_train.csv", pseudo_rows, fieldnames)
    write_csv(output_dir / "dataset_gold_pseudogold_fixed_split.csv", dataset_rows, fieldnames)
    write_csv(
        output_dir / "pseudo_gold_selection_details.csv",
        selected_details,
        ["record_id", "axis", "label", "score", "anchor_hits", "reason"],
    )

    final_counts = train_counts(dataset_rows)
    selected_counts = {axis: Counter() for axis in TARGET_COLS}
    for row in pseudo_rows:
        for axis in TARGET_COLS:
            selected_counts[axis][row[axis]] += 1
    summary = {
        "input_csv": str(dataset_path),
        "scores_csv": str(scores_path),
        "target_multiplier": args.target_multiplier,
        "pseudo_weight": args.pseudo_weight,
        "gold_train_rows": len(gold_train),
        "pseudo_gold_rows": len(pseudo_rows),
        "gold_val_test_rows": len(gold_val_test),
        "dataset_rows": len(dataset_rows),
        "needs": {axis: dict(labels) for axis, labels in needs.items()},
        "filled": {axis: dict(labels) for axis, labels in filled.items()},
        "selected_label_distribution": {axis: dict(counter.most_common()) for axis, counter in selected_counts.items()},
        "final_train_counts": {axis: dict(counter.most_common()) for axis, counter in final_counts.items()},
    }
    write_json(output_dir / "pseudo_gold_summary.json", summary)

    lines = [
        "# Pseudo-Gold Layer Summary",
        "",
        f"- gold train rows: `{len(gold_train)}`",
        f"- pseudo-gold rows: `{len(pseudo_rows)}`",
        f"- gold val/test rows: `{len(gold_val_test)}`",
        f"- pseudo weight: `{args.pseudo_weight}`",
        "",
        "## Filled Deficits",
        "",
        "| Axis | Label | Need | Filled |",
        "| --- | --- | ---: | ---: |",
    ]
    for axis, labels in needs.items():
        for label, need in labels.items():
            lines.append(f"| `{axis}` | `{label}` | {need} | {filled.get(axis, {}).get(label, 0)} |")
    (output_dir / "pseudo_gold_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-csv",
        default="data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv",
    )
    parser.add_argument(
        "--scores-csv",
        default="data/ml_experiments/diamond_dataset_2026-06-03/silver_model_scores.csv",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pseudo-weight", type=float, default=0.85)
    parser.add_argument("--target-multiplier", type=float, default=1.0)
    parser.add_argument("--allow-overrides", action="store_true")
    return parser.parse_args()


def main() -> None:
    build(parse_args())


if __name__ == "__main__":
    main()
