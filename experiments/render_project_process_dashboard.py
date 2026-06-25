#!/usr/bin/env python
"""Render a full-process dashboard for the ЖКХ annotation project."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
import textwrap
from datetime import datetime
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


HEAD_LABELS = {
    "jkh_relevance": "ЖКХ-релевантность",
    "jkh_topic": "Тема ЖКХ",
    "authority_aspect": "Органы/власть",
    "sentiment": "Тональность",
    "appeal_type": "Тип обращения",
    "responsible_party": "Ответственный",
    "sarcasm": "Сарказм",
    "quality": "Качество",
}


PALETTE = {
    "bg": "#071114",
    "panel": "#102026",
    "panel_2": "#142a30",
    "panel_3": "#0d1b20",
    "line": "#2b4f59",
    "text": "#f4fbfc",
    "muted": "#a9c4c9",
    "soft": "#d9eef0",
    "cyan": "#53d7ce",
    "green": "#7bd88f",
    "yellow": "#ffd166",
    "orange": "#ff9f4a",
    "red": "#ff6b6b",
    "blue": "#7aa7ff",
    "purple": "#b28dff",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_int(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{int(value):,}".replace(",", " ")


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.{digits}f}%"


def fmt_float(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def metric_mean(metrics: dict[str, Any]) -> float:
    values = []
    for field in TARGET_COLS:
        value = metrics.get("test_metrics", {}).get(field, {}).get("macro_f1")
        if value is not None:
            values.append(float(value))
    return sum(values) / len(values)


def load_run(path: Path, name: str) -> dict[str, Any]:
    metrics = read_json(path)
    return {
        "name": name,
        "epochs": metrics.get("epochs"),
        "lr": metrics.get("lr"),
        "silver_weight": metrics.get("silver_weight_override"),
        "mean_macro_f1": metric_mean(metrics),
        "heads": {
            field: float(metrics.get("test_metrics", {}).get(field, {}).get("macro_f1", 0.0))
            for field in TARGET_COLS
        },
    }


def taxonomy_items(stats: dict[str, Any], field: str, limit: int = 10) -> list[dict[str, Any]]:
    values = stats.get("approved_dataset_taxonomy", {}).get(field, [])
    return sorted(values, key=lambda item: int(item.get("count", 0)), reverse=True)[:limit]


def count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def collect_data(args: argparse.Namespace) -> dict[str, Any]:
    export_dir = Path(args.export_dir)
    stats = read_json(export_dir / "03_gold_statistics" / "annotation_statistics.json")
    silver = read_json(export_dir / "06_silver_auto_labeled_all.summary.json")
    manifest = read_json(export_dir / "04_gold_silver_manifest.json")

    run_root = Path(args.runs_dir)
    runs = {
        "gold_only": load_run(run_root / "gold_only_full_2026-06-03_01-06" / "metrics.json", "gold_only_full"),
        "gold_silver_initial": load_run(run_root / "gold_silver_full_2026-06-03_01-06" / "metrics.json", "gold_silver_initial"),
        "quick_best": load_run(run_root / "sweep_2026-06-03" / "quick_w03_weighted" / "metrics.json", "quick_w03_weighted"),
        "final_best": load_run(
            run_root / "sweep_final_2026-06-03" / "final_w03_weighted_lr1e5_e4" / "metrics.json",
            "final_w03_weighted_lr1e5_e4",
        ),
    }

    first_batch_path = Path("data/exports/offline_jkh_labels_2026-06-02_15-07/unresolved_jkh_candidates_labeled.csv")
    all_jkh_path = Path("data/exports/offline_jkh_labels_all_2026-06-03_00-33/unresolved_jkh_candidates_labeled.csv")

    dataset_counts = {
        "clean_gold": 4365,
        "gold_train": 3055,
        "gold_val": 655,
        "gold_test": 655,
        "silver_train": 259728,
        "gold_only_dataset": 4365,
        "gold_silver_dataset": 264093,
        "gold_weight": 1.0,
        "silver_weight_default": 0.4,
    }

    campaign = {
        "activated_candidates": 14954,
        "activated_controls": 150,
        "paused_general": 244684,
        "first_offline_applied": count_rows(first_batch_path) if first_batch_path.exists() else 500,
        "full_jkh_prepared": count_rows(all_jkh_path) if all_jkh_path.exists() else 14376,
        "full_jkh_prepared_status": "prepared locally, not yet recorded as applied in production",
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "export_dir": str(export_dir),
        "stats": stats,
        "silver": silver,
        "manifest": manifest,
        "runs": runs,
        "dataset_counts": dataset_counts,
        "campaign": campaign,
    }


class Svg:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.parts: list[str] = []

    def add(self, text: str) -> None:
        self.parts.append(text)

    def rect(self, x: int, y: int, w: int, h: int, fill: str, stroke: str | None = None, rx: int = 18, opacity: float = 1.0) -> None:
        stroke_attr = f' stroke="{stroke}" stroke-width="1.2"' if stroke else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" opacity="{opacity}"{stroke_attr}/>')

    def line(self, x1: int, y1: int, x2: int, y2: int, color: str, width: float = 1.0, opacity: float = 1.0) -> None:
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')

    def text(
        self,
        x: int,
        y: int,
        value: str,
        size: int = 24,
        color: str = PALETTE["text"],
        weight: int | str = 400,
        anchor: str = "start",
        opacity: float = 1.0,
    ) -> None:
        escaped = html.escape(str(value))
        self.add(
            f'<text x="{x}" y="{y}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" opacity="{opacity}">{escaped}</text>'
        )

    def wrapped(
        self,
        x: int,
        y: int,
        value: str,
        width_chars: int,
        size: int = 22,
        color: str = PALETTE["soft"],
        line_height: int | None = None,
        weight: int | str = 400,
    ) -> int:
        line_height = line_height or int(size * 1.36)
        current_y = y
        for raw_line in str(value).split("\n"):
            lines = textwrap.wrap(raw_line, width=width_chars, break_long_words=False) or [""]
            for line in lines:
                self.text(x, current_y, line, size=size, color=color, weight=weight)
                current_y += line_height
        return current_y

    def card(self, x: int, y: int, w: int, h: int, title: str, accent: str = PALETTE["cyan"]) -> None:
        self.rect(x, y, w, h, PALETTE["panel"], PALETTE["line"], rx=20)
        self.rect(x, y, 8, h, accent, None, rx=4, opacity=0.95)
        self.text(x + 28, y + 42, title, size=27, color=PALETTE["text"], weight=700)

    def metric_card(self, x: int, y: int, w: int, h: int, value: str, label: str, accent: str) -> None:
        self.rect(x, y, w, h, PALETTE["panel_2"], PALETTE["line"], rx=18)
        self.text(x + 22, y + 48, value, size=36, color=accent, weight=800)
        self.wrapped(x + 22, y + 84, label, width_chars=22, size=18, color=PALETTE["muted"], line_height=23)

    def bar_chart(
        self,
        x: int,
        y: int,
        w: int,
        title: str,
        items: list[tuple[str, float, str | None]],
        max_value: float | None = None,
        bar_color: str = PALETTE["cyan"],
        label_width_chars: int = 28,
        row_h: int = 34,
        value_formatter: Any = fmt_int,
    ) -> int:
        self.text(x, y, title, size=23, color=PALETTE["text"], weight=700)
        current_y = y + 34
        max_value = max_value or max([value for _, value, _ in items] or [1])
        bar_x = x + 315
        bar_w = w - 430
        for label, value, custom_color in items:
            color = custom_color or bar_color
            self.wrapped(x, current_y + 17, label, width_chars=label_width_chars, size=17, color=PALETTE["muted"], line_height=19)
            self.rect(bar_x, current_y, bar_w, 18, PALETTE["panel_3"], None, rx=9)
            fill_w = 0 if max_value <= 0 else max(3, int(bar_w * value / max_value))
            self.rect(bar_x, current_y, fill_w, 18, color, None, rx=9)
            self.text(bar_x + bar_w + 18, current_y + 16, value_formatter(value), size=17, color=PALETTE["soft"], weight=600)
            current_y += row_h
        return current_y

    def dual_bars(
        self,
        x: int,
        y: int,
        w: int,
        title: str,
        labels: list[str],
        left_values: list[float],
        right_values: list[float],
        left_name: str,
        right_name: str,
    ) -> int:
        self.text(x, y, title, size=23, color=PALETTE["text"], weight=700)
        self.rect(x + 320, y + 12, 24, 12, PALETTE["blue"], None, rx=6)
        self.text(x + 352, y + 24, left_name, size=17, color=PALETTE["muted"])
        self.rect(x + 505, y + 12, 24, 12, PALETTE["green"], None, rx=6)
        self.text(x + 537, y + 24, right_name, size=17, color=PALETTE["muted"])
        current_y = y + 48
        bar_x = x + 315
        bar_w = w - 470
        for label, left, right in zip(labels, left_values, right_values):
            self.wrapped(x, current_y + 16, label, width_chars=28, size=16, color=PALETTE["muted"], line_height=18)
            self.rect(bar_x, current_y, bar_w, 11, PALETTE["panel_3"], None, rx=5)
            self.rect(bar_x, current_y, max(2, int(bar_w * left)), 11, PALETTE["blue"], None, rx=5)
            self.rect(bar_x, current_y + 16, bar_w, 11, PALETTE["panel_3"], None, rx=5)
            self.rect(bar_x, current_y + 16, max(2, int(bar_w * right)), 11, PALETTE["green"], None, rx=5)
            self.text(bar_x + bar_w + 16, current_y + 10, fmt_float(left, 3), size=15, color=PALETTE["soft"])
            self.text(bar_x + bar_w + 16, current_y + 27, fmt_float(right, 3), size=15, color=PALETTE["green"], weight=700)
            current_y += 43
        return current_y

    def to_string(self) -> str:
        header = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
<defs>
  <linearGradient id="hero" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#102b32"/>
    <stop offset="55%" stop-color="#071114"/>
    <stop offset="100%" stop-color="#221826"/>
  </linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000000" flood-opacity="0.35"/>
  </filter>
</defs>
<rect width="100%" height="100%" fill="url(#hero)"/>
<circle cx="1540" cy="110" r="260" fill="#53d7ce" opacity="0.10"/>
<circle cx="180" cy="530" r="250" fill="#ff6b6b" opacity="0.08"/>
<g filter="url(#shadow)">
'''
        footer = "</g>\n</svg>\n"
        return header + "\n".join(self.parts) + footer


def render_svg(data: dict[str, Any]) -> str:
    stats = data["stats"]
    totals = stats["totals"]
    scores = stats["scores"]
    silver = data["silver"]
    runs = data["runs"]
    campaign = data["campaign"]
    ds = data["dataset_counts"]

    final = runs["final_best"]
    gold = runs["gold_only"]
    initial = runs["gold_silver_initial"]

    width, height = 1800, 3300
    svg = Svg(width, height)

    svg.text(80, 90, "ЖКХ-разметка: путь данных, проверки и модели", size=52, weight=850)
    svg.text(
        80,
        128,
        "Сводная инфографика по производственной разметке, gold/silver датасету и RuBERT teacher-student обучению",
        size=24,
        color=PALETTE["muted"],
    )
    svg.text(1720, 90, "2026-06-03", size=24, color=PALETTE["yellow"], weight=700, anchor="end")
    svg.text(1720, 124, "локальный снимок D:\\Diplom", size=18, color=PALETTE["muted"], anchor="end")

    # Executive metrics.
    card_y = 170
    cards = [
        (80, fmt_int(totals["source_records_total"]), "исходных записей в production базе", PALETTE["cyan"]),
        (360, fmt_int(totals["annotations_checked"]), "проверенных разметок, pending = 0", PALETTE["green"]),
        (640, fmt_int(totals["annotations_approved_dataset"]), "training-ready gold labels", PALETTE["yellow"]),
        (920, fmt_int(silver["counts"]["rows"]), "automatic silver labels для обучения", PALETTE["purple"]),
        (1200, fmt_float(final["mean_macro_f1"], 4), "лучший test mean macro-F1", PALETTE["green"]),
        (1480, "+" + fmt_float(final["mean_macro_f1"] - gold["mean_macro_f1"], 4), "прирост к gold-only", PALETTE["orange"]),
    ]
    for x, value, label, color in cards:
        svg.metric_card(x, card_y, 240, 130, value, label, color)

    # Pipeline.
    svg.card(80, 350, 1640, 305, "1. Конвейер данных и решений", PALETTE["cyan"])
    steps = [
        ("Исходные записи", totals["source_records_total"], "пост + комментарий, ЖКХ-контекст определяется по посту"),
        ("Проверка людьми", totals["annotations_checked"], "админы/суперадмин: approve, reject, deleted-confirm"),
        ("Gold dataset", totals["annotations_approved_dataset"], "только проверенные человеком training-ready ответы"),
        ("Silver export", silver["counts"]["rows"], "неразмеченные записи: правила + automatic teacher"),
        ("RuBERT training", ds["gold_silver_dataset"], "gold train + silver train, val/test только gold"),
        ("Best checkpoint", int(final["mean_macro_f1"] * 10000), "mean macro-F1 0.3003 на human-gold test"),
    ]
    step_x, step_y = 120, 430
    step_w, gap = 245, 24
    for idx, (title, value, note) in enumerate(steps):
        x = step_x + idx * (step_w + gap)
        svg.rect(x, step_y, step_w, 150, PALETTE["panel_2"], PALETTE["line"], rx=18)
        svg.text(x + 20, step_y + 38, title, size=22, color=PALETTE["text"], weight=750)
        shown = fmt_float(value / 10000, 4) if title == "Best checkpoint" else fmt_int(value)
        svg.text(x + 20, step_y + 80, shown, size=34, color=[PALETTE["cyan"], PALETTE["green"], PALETTE["yellow"], PALETTE["purple"], PALETTE["blue"], PALETTE["orange"]][idx], weight=850)
        svg.wrapped(x + 20, step_y + 112, note, width_chars=22, size=15, color=PALETTE["muted"], line_height=18)
        if idx < len(steps) - 1:
            ax = x + step_w + 4
            ay = step_y + 75
            svg.line(ax, ay, ax + gap - 8, ay, PALETTE["muted"], width=2, opacity=0.7)
            svg.text(ax + gap - 8, ay + 7, "›", size=30, color=PALETTE["muted"], weight=800)

    # Production status.
    svg.card(80, 700, 790, 455, "2. Production-разметка и очки", PALETTE["green"])
    prod_items = [
        ("Проверено всего", totals["annotations_checked"], PALETTE["green"]),
        ("Принято training-ready", totals["annotations_approved_dataset"], PALETTE["yellow"]),
        ("Подтверждено удаленных постов", totals["deleted_posts_confirmed"], PALETTE["orange"]),
        ("Отклонено всего", totals["annotations_rejected_total"], PALETTE["red"]),
        ("Уникальных проверенных записей", totals["unique_records_checked"], PALETTE["cyan"]),
        ("Net points", scores["net_points"], PALETTE["purple"]),
    ]
    svg.bar_chart(120, 775, 710, "Итоги production snapshot", prod_items, max_value=totals["annotations_checked"], row_h=42)
    approve_rate = totals["annotations_approved_dataset"] / totals["annotations_checked"]
    reject_rate = totals["annotations_rejected_total"] / totals["annotations_checked"]
    deleted_rate = totals["deleted_posts_confirmed"] / totals["annotations_checked"]
    svg.wrapped(
        120,
        1085,
        f"Доля training-ready gold: {fmt_pct(approve_rate)}; подтвержденные удаленные посты: {fmt_pct(deleted_rate)}; отклонения: {fmt_pct(reject_rate)}. Pending после последней проверки: 0.",
        width_chars=70,
        size=18,
        color=PALETTE["soft"],
    )

    # Gold taxonomy.
    svg.card(930, 700, 790, 455, "3. Что внутри human gold", PALETTE["yellow"])
    relevance_items = [(item["label"], item["count"], PALETTE["green"] if item["value"] == "yes" else PALETTE["muted"]) for item in taxonomy_items(stats, "jkh_relevance", 3)]
    svg.bar_chart(970, 775, 710, "Релевантность ЖКХ в gold", relevance_items, max_value=max(item[1] for item in relevance_items), row_h=42)
    topic_items = [(item["label"], item["count"], None) for item in taxonomy_items(stats, "jkh_topic", 6)]
    svg.bar_chart(970, 930, 710, "Топ тем в gold", topic_items, max_value=topic_items[0][1], bar_color=PALETTE["yellow"], row_h=36)
    gold_yes = next((item["count"] for item in stats["approved_dataset_taxonomy"]["jkh_relevance"] if item["value"] == "yes"), 0)
    gold_no = next((item["count"] for item in stats["approved_dataset_taxonomy"]["jkh_relevance"] if item["value"] == "no"), 0)
    svg.wrapped(
        970,
        1100,
        f"Вывод: в human gold до enrichment сильный перекос в non-JKH: {fmt_int(gold_no)} no против {fmt_int(gold_yes)} yes. Поэтому отдельно запускалась приоритизация ЖКХ-кандидатов.",
        width_chars=70,
        size=18,
        color=PALETTE["soft"],
    )

    # JKH campaign and offline labels.
    svg.card(80, 1200, 790, 520, "4. ЖКХ-enrichment и offline labeling", PALETTE["orange"])
    camp_items = [
        ("Активировано ЖКХ-кандидатов", campaign["activated_candidates"], PALETTE["orange"]),
        ("Контрольных non-JKH", campaign["activated_controls"], PALETTE["muted"]),
        ("Общий пул временно paused", campaign["paused_general"], PALETTE["red"]),
        ("Первый offline batch applied", campaign["first_offline_applied"], PALETTE["green"]),
        ("Full JKH batch prepared", campaign["full_jkh_prepared"], PALETTE["yellow"]),
    ]
    svg.bar_chart(120, 1275, 710, "Приоритизация и подготовка", camp_items, max_value=campaign["paused_general"], row_h=42)
    svg.wrapped(
        120,
        1585,
        "Важно: полный JKH batch на 14 376 записей подготовлен локально и использован как audited overrides для silver, но в production он пока не зафиксирован как примененный. Примененный production batch: первые 500 записей.",
        width_chars=72,
        size=18,
        color=PALETTE["soft"],
    )

    # Silver.
    svg.card(930, 1200, 790, 520, "5. automatic silver labels", PALETTE["purple"])
    silver_counts = silver["counts"]
    svg.metric_card(970, 1270, 220, 105, fmt_int(silver_counts["rows"]), "всего silver rows", PALETTE["purple"])
    svg.metric_card(1210, 1270, 220, 105, fmt_int(silver_counts["generated"]), "сгенерировано правилами", PALETTE["cyan"])
    svg.metric_card(1450, 1270, 220, 105, fmt_int(silver_counts["overrides"]), "audited overrides", PALETTE["yellow"])
    silver_rel = silver["distributions"]["jkh_relevance"]
    rel_items = [
        ("silver yes", silver_rel.get("yes", 0), PALETTE["green"]),
        ("silver no", silver_rel.get("no", 0), PALETTE["muted"]),
    ]
    svg.bar_chart(970, 1415, 710, "Silver relevance", rel_items, max_value=max(item[1] for item in rel_items), row_h=42)
    silver_topics = sorted(silver["distributions"]["jkh_topic"].items(), key=lambda kv: kv[1], reverse=True)[:7]
    topic_labels = [(label, value, PALETTE["purple"] if label != "not_jkh" else PALETTE["muted"]) for label, value in silver_topics]
    svg.bar_chart(970, 1530, 710, "Топ silver topics", topic_labels, max_value=topic_labels[0][1], row_h=32, label_width_chars=25)

    # Dataset split.
    svg.card(80, 1765, 790, 420, "6. Датасет для обучения", PALETTE["blue"])
    split_items = [
        ("clean human gold", ds["clean_gold"], PALETTE["yellow"]),
        ("gold train", ds["gold_train"], PALETTE["green"]),
        ("gold validation", ds["gold_val"], PALETTE["cyan"]),
        ("gold test", ds["gold_test"], PALETTE["blue"]),
        ("silver train", ds["silver_train"], PALETTE["purple"]),
        ("gold+silver fixed dataset", ds["gold_silver_dataset"], PALETTE["orange"]),
    ]
    svg.bar_chart(120, 1840, 710, "Fixed split", split_items, max_value=ds["gold_silver_dataset"], row_h=40)
    svg.wrapped(
        120,
        2118,
        "Политика качества: validation/test остаются только human gold; silver используется только в train с меньшим весом. Это защищает оценку от самоподтверждения automatic teacher-разметки.",
        width_chars=72,
        size=18,
        color=PALETTE["soft"],
    )

    # Model comparison.
    svg.card(930, 1765, 790, 420, "7. RuBERT teacher-student: итог", PALETTE["green"])
    run_items = [
        ("gold-only", gold["mean_macro_f1"], PALETTE["blue"]),
        ("first gold+silver", initial["mean_macro_f1"], PALETTE["purple"]),
        ("quick best", runs["quick_best"]["mean_macro_f1"], PALETTE["yellow"]),
        ("final best", final["mean_macro_f1"], PALETTE["green"]),
    ]
    svg.bar_chart(970, 1840, 710, "Mean macro-F1 на human-gold test", run_items, max_value=0.35, row_h=48, value_formatter=lambda v: fmt_float(v, 4))
    svg.metric_card(970, 2060, 220, 90, "+" + fmt_float(final["mean_macro_f1"] - gold["mean_macro_f1"], 4), "к gold-only", PALETTE["green"])
    svg.metric_card(1210, 2060, 220, 90, "+" + fmt_float(final["mean_macro_f1"] - initial["mean_macro_f1"], 4), "к first full", PALETTE["yellow"])
    svg.metric_card(1450, 2060, 220, 90, fmt_float(final["heads"]["jkh_topic"], 4), "jkh_topic macro-F1", PALETTE["purple"])

    # Per-head comparison.
    svg.card(80, 2230, 1640, 500, "8. По головам модели: где выросло, где болит", PALETTE["purple"])
    labels = [HEAD_LABELS[field] for field in TARGET_COLS]
    gold_values = [gold["heads"][field] for field in TARGET_COLS]
    final_values = [final["heads"][field] for field in TARGET_COLS]
    svg.dual_bars(120, 2305, 1540, "Macro-F1: gold-only vs optimized teacher-student", labels, gold_values, final_values, "gold-only", "optimized")
    svg.wrapped(
        120,
        2680,
        "Главный выигрыш silver-обучения: тема ЖКХ и тип обращения. Слабое место: responsible_party; редкие классы типа регоператора, ГЖИ, ресурсника и конкретного исполнителя представлены мало, поэтому macro-F1 остается низким даже при приличной weighted-F1.",
        width_chars=140,
        size=19,
        color=PALETTE["soft"],
    )

    # Operational evidence and conclusion.
    svg.card(80, 2775, 790, 355, "9. Эксплуатационная устойчивость", PALETTE["cyan"])
    ops = [
        ("gunicorn workers", 4, PALETTE["cyan"]),
        ("local /login/ stress requests", 225000, PALETTE["green"]),
        ("failed requests in stress", 0, PALETTE["yellow"]),
        ("throughput after tuning, req/s", 1064, PALETTE["orange"]),
    ]
    svg.bar_chart(120, 2850, 710, "Production evidence", ops, max_value=225000, row_h=42)
    svg.wrapped(
        120,
        3070,
        "После перехода с 2 на 4 sync workers throughput login-page stress вырос примерно с 644 до 1064 req/s; healthz оставался OK, swap не использовался.",
        width_chars=72,
        size=18,
        color=PALETTE["soft"],
    )

    svg.card(930, 2775, 790, 355, "10. Аналитический вывод", PALETTE["green"])
    conclusion = (
        "Процесс замкнут: production-разметка дает human gold, automatic teacher расширяет обучающую выборку silver, "
        "а качество проверяется только на human-gold validation/test. Teacher-student уже дает заметный прирост "
        "по полной 8-осевой таксономии, но для сильного авторазметчика нужны дополнительные gold-примеры редких "
        "ЖКХ-классов и особенно responsible_party."
    )
    svg.wrapped(970, 2850, conclusion, width_chars=72, size=22, color=PALETTE["soft"], line_height=31)
    svg.wrapped(
        970,
        3055,
        "Архив-источник: teacher_student_full_export_2026-06-03_01-06. Подробности: docs/project_data_archive.md и docs/teacher_student_training_2026-06-03.md.",
        width_chars=72,
        size=17,
        color=PALETTE["muted"],
        line_height=23,
    )

    svg.text(80, 3250, f"Generated locally: {data['generated_at']}", size=16, color=PALETTE["muted"])
    svg.text(1720, 3250, "Gold = human approved; Silver = automatic teacher labels; test = human-gold only", size=16, color=PALETTE["muted"], anchor="end")
    return svg.to_string()


def render_markdown(data: dict[str, Any]) -> str:
    stats = data["stats"]
    totals = stats["totals"]
    scores = stats["scores"]
    silver = data["silver"]
    runs = data["runs"]
    final = runs["final_best"]
    gold = runs["gold_only"]
    initial = runs["gold_silver_initial"]
    ds = data["dataset_counts"]
    campaign = data["campaign"]

    lines = [
        "# ЖКХ-разметка: сводка процесса, данных и модели",
        "",
        f"Generated: `{data['generated_at']}`",
        "",
        "## Главные числа",
        "",
        f"- Исходных записей в production базе: `{fmt_int(totals['source_records_total'])}`.",
        f"- Проверенных разметок: `{fmt_int(totals['annotations_checked'])}`; pending: `{fmt_int(totals['annotations_pending'])}`.",
        f"- Training-ready human gold labels: `{fmt_int(totals['annotations_approved_dataset'])}`.",
        f"- Подтвержденных удаленных постов: `{fmt_int(totals['deleted_posts_confirmed'])}`.",
        f"- Отклоненных разметок: `{fmt_int(totals['annotations_rejected_total'])}`.",
        f"- Net points: `{fmt_int(scores['net_points'])}`.",
        f"- automatic silver labels: `{fmt_int(silver['counts']['rows'])}`.",
        f"- Fixed teacher-student dataset: `{fmt_int(ds['gold_silver_dataset'])}` rows.",
        f"- Лучший held-out human-gold test mean macro-F1: `{fmt_float(final['mean_macro_f1'])}`.",
        "",
        "## Gold / Silver",
        "",
        f"- Clean human gold: `{fmt_int(ds['clean_gold'])}`.",
        f"- Gold split: train `{fmt_int(ds['gold_train'])}`, validation `{fmt_int(ds['gold_val'])}`, test `{fmt_int(ds['gold_test'])}`.",
        f"- Silver train: `{fmt_int(ds['silver_train'])}`.",
        "- Validation and test are human-gold only.",
        f"- Default training weights: gold `{ds['gold_weight']}`, silver `{ds['silver_weight_default']}`; best sweep used silver override `0.3`.",
        "",
        "## ЖКХ enrichment",
        "",
        f"- Activated JKH candidates: `{fmt_int(campaign['activated_candidates'])}`.",
        f"- Control records: `{fmt_int(campaign['activated_controls'])}`.",
        f"- Paused general records: `{fmt_int(campaign['paused_general'])}`.",
        f"- First offline batch applied to production: `{fmt_int(campaign['first_offline_applied'])}`.",
        f"- Full JKH batch prepared locally: `{fmt_int(campaign['full_jkh_prepared'])}`.",
        f"- Status: `{campaign['full_jkh_prepared_status']}`.",
        "",
        "## Silver distributions",
        "",
        f"- Silver relevance yes/no: `{fmt_int(silver['distributions']['jkh_relevance'].get('yes', 0))}` / `{fmt_int(silver['distributions']['jkh_relevance'].get('no', 0))}`.",
        "- Top silver topics:",
    ]
    for label, count in sorted(silver["distributions"]["jkh_topic"].items(), key=lambda kv: kv[1], reverse=True)[:10]:
        lines.append(f"  - `{label}`: `{fmt_int(count)}`")

    lines += [
        "",
        "## Model comparison",
        "",
        "| Run | Test mean macro-F1 | jkh_relevance | jkh_topic | authority | sentiment | appeal | responsible | sarcasm | quality |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ["gold_only", "gold_silver_initial", "quick_best", "final_best"]:
        run = runs[key]
        h = run["heads"]
        lines.append(
            f"| `{run['name']}` | {fmt_float(run['mean_macro_f1'])} | {fmt_float(h['jkh_relevance'])} | "
            f"{fmt_float(h['jkh_topic'])} | {fmt_float(h['authority_aspect'])} | {fmt_float(h['sentiment'])} | "
            f"{fmt_float(h['appeal_type'])} | {fmt_float(h['responsible_party'])} | {fmt_float(h['sarcasm'])} | {fmt_float(h['quality'])} |"
        )

    lines += [
        "",
        "## Best checkpoint",
        "",
        "`data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/model.pt`",
        "",
        "Configuration: `cointegrated/rubert-tiny2`, all 8 heads, `post_comment`, 4 epochs, batch size 32, max length 256, CUDA, `silver_weight=0.3`, `weighted_balanced`, `lr=0.00001`.",
        "",
        "## Analysis",
        "",
        f"- Teacher-student gain over gold-only: `+{fmt_float(final['mean_macro_f1'] - gold['mean_macro_f1'])}` mean macro-F1.",
        f"- Gain over the first full gold+silver run: `+{fmt_float(final['mean_macro_f1'] - initial['mean_macro_f1'])}` mean macro-F1.",
        "- Largest durable gain is `jkh_topic`: silver gives the model enough topic variety to stop collapsing into the dominant non-JKH class.",
        "- `responsible_party` remains the weakest head because rare responsible-party classes are still sparse and ambiguous.",
        "- For the diploma, the strongest methodological point is clean separation: human gold is used for evaluation; automatic silver is only used to expand training.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(data: dict[str, Any], output_dir: Path, desktop_copy: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "zhkh_process_dashboard_2026-06-03.svg"
    md_path = output_dir / "zhkh_process_dashboard_2026-06-03.md"
    json_path = output_dir / "zhkh_process_dashboard_2026-06-03.json"

    svg_path.write_text(render_svg(data), encoding="utf-8-sig")
    md_path.write_text(render_markdown(data), encoding="utf-8-sig")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if desktop_copy:
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            target = desktop / "ЖКХ_процесс_данные_модель_2026-06-03"
            target.mkdir(parents=True, exist_ok=True)
            for path in [svg_path, md_path, json_path]:
                shutil.copy2(path, target / path.name)

    print(f"svg={svg_path}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    if desktop_copy:
        print(f"desktop={Path.home() / 'Desktop' / 'ЖКХ_процесс_данные_модель_2026-06-03'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", default="data/exports/teacher_student_full_export_2026-06-03_01-06")
    parser.add_argument("--runs-dir", default="data/ml_experiments/teacher_student_runs")
    parser.add_argument("--output-dir", default="data/exports/project_process_dashboard_2026-06-03")
    parser.add_argument("--desktop-copy", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = collect_data(args)
    write_outputs(data, Path(args.output_dir), args.desktop_copy)


if __name__ == "__main__":
    main()
