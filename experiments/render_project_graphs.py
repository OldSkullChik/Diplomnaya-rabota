#!/usr/bin/env python
"""Render readable SVG graphs for the ЖКХ annotation process."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


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
    "authority_aspect": "Власть/органы",
    "sentiment": "Тональность",
    "appeal_type": "Тип обращения",
    "responsible_party": "Ответственный",
    "sarcasm": "Сарказм",
    "quality": "Качество",
}


TOPIC_LABELS = {
    "not_jkh": "Не ЖКХ",
    "waste_cleaning": "Мусор и уборка",
    "heating_hot_water": "Отопление/ГВС",
    "cold_water_sewerage": "ХВС/канализация",
    "yard_area": "Двор/территория",
    "house_common_property": "МКД/общее имущество",
    "payments_tariffs": "Платежи/тарифы",
    "public_authorities": "Органы власти",
    "other_jkh": "Другое ЖКХ",
    "management_company": "УК/ТСЖ",
}


COLORS = {
    "bg": "#081316",
    "card": "#11252b",
    "card2": "#163039",
    "ink": "#f5fbfc",
    "muted": "#a7c2c8",
    "line": "#315b66",
    "grid": "#24474f",
    "cyan": "#54d8cf",
    "green": "#7bd88f",
    "yellow": "#ffd166",
    "orange": "#ff9f4a",
    "red": "#ff6b6b",
    "blue": "#7aa7ff",
    "purple": "#b28dff",
    "gray": "#78939a",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_int(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{int(value):,}".replace(",", " ")


def fmt_float(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{100 * value:.{digits}f}%"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def short(value: str, max_len: int = 34) -> str:
    value = str(value)
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


class Canvas:
    def __init__(self, width: int, height: int, title: str) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.parts: list[str] = []

    def add(self, value: str) -> None:
        self.parts.append(value)

    def rect(self, x: int, y: int, w: int, h: int, fill: str, stroke: str | None = None, rx: int = 16, opacity: float = 1.0) -> None:
        stroke_attr = f' stroke="{stroke}" stroke-width="1.2"' if stroke else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" opacity="{opacity}"{stroke_attr}/>')

    def line(self, x1: int, y1: int, x2: int, y2: int, color: str = COLORS["grid"], width: float = 1.0, opacity: float = 1.0) -> None:
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')

    def text(
        self,
        x: int,
        y: int,
        value: Any,
        size: int = 22,
        color: str = COLORS["ink"],
        weight: int | str = 400,
        anchor: str = "start",
        opacity: float = 1.0,
    ) -> None:
        self.add(
            f'<text x="{x}" y="{y}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" opacity="{opacity}">{esc(value)}</text>'
        )

    def wrapped(self, x: int, y: int, value: str, chars: int, size: int = 22, color: str = COLORS["muted"], line_height: int | None = None) -> int:
        line_height = line_height or int(size * 1.35)
        current = y
        for line in textwrap.wrap(value, width=chars, break_long_words=False):
            self.text(x, current, line, size=size, color=color)
            current += line_height
        return current

    def header(self, subtitle: str | None = None) -> None:
        self.text(64, 82, self.title, size=46, weight=850)
        if subtitle:
            self.text(64, 120, subtitle, size=22, color=COLORS["muted"])

    def card(self, x: int, y: int, w: int, h: int, title: str, accent: str = COLORS["cyan"]) -> None:
        self.rect(x, y, w, h, COLORS["card"], COLORS["line"], rx=24)
        self.rect(x, y, 9, h, accent, rx=4)
        self.text(x + 30, y + 45, title, size=28, weight=760)

    def metric(self, x: int, y: int, w: int, h: int, value: str, label: str, color: str) -> None:
        self.rect(x, y, w, h, COLORS["card2"], COLORS["line"], rx=18)
        self.text(x + 24, y + 54, value, size=38, color=color, weight=850)
        self.wrapped(x + 24, y + 89, label, chars=max(18, w // 11), size=17, color=COLORS["muted"], line_height=22)

    def finish(self) -> str:
        body = "\n".join(self.parts)
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#10262c"/>
    <stop offset="58%" stop-color="#081316"/>
    <stop offset="100%" stop-color="#1b1828"/>
  </linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="16" stdDeviation="16" flood-color="#000000" flood-opacity="0.32"/>
  </filter>
</defs>
<rect width="100%" height="100%" fill="url(#bg)"/>
<circle cx="{self.width - 170}" cy="120" r="260" fill="#54d8cf" opacity="0.08"/>
<circle cx="160" cy="{self.height - 260}" r="320" fill="#ff6b6b" opacity="0.055"/>
<g filter="url(#shadow)">
{body}
</g>
</svg>
'''


def horizontal_bars(
    canvas: Canvas,
    x: int,
    y: int,
    w: int,
    items: list[tuple[str, float, str]],
    max_value: float | None = None,
    formatter: Callable[[float], str] = fmt_int,
    row_h: int = 54,
    label_w: int = 360,
) -> int:
    max_value = max_value if max_value is not None else max([v for _, v, _ in items] or [1])
    bar_x = x + label_w
    bar_w = w - label_w - 150
    current = y
    for label, value, color in items:
        canvas.text(x, current + 22, short(label, 38), size=20, color=COLORS["muted"], weight=600)
        canvas.rect(bar_x, current, bar_w, 28, "#0b1a1f", None, rx=14)
        fill_w = 0 if max_value <= 0 else max(3, int(bar_w * value / max_value))
        canvas.rect(bar_x, current, fill_w, 28, color, None, rx=14)
        canvas.text(bar_x + bar_w + 24, current + 22, formatter(value), size=20, color=COLORS["ink"], weight=700)
        current += row_h
    return current


def grouped_bars(
    canvas: Canvas,
    x: int,
    y: int,
    w: int,
    labels: list[str],
    left: list[float],
    right: list[float],
    left_name: str,
    right_name: str,
    max_value: float = 1.0,
    formatter: Callable[[float], str] = lambda v: fmt_float(v, 3),
    row_h: int = 68,
    label_w: int = 350,
) -> int:
    canvas.rect(x + label_w, y - 28, 24, 13, COLORS["blue"], rx=7)
    canvas.text(x + label_w + 34, y - 16, left_name, size=18, color=COLORS["muted"])
    canvas.rect(x + label_w + 200, y - 28, 24, 13, COLORS["green"], rx=7)
    canvas.text(x + label_w + 234, y - 16, right_name, size=18, color=COLORS["muted"])
    bar_x = x + label_w
    bar_w = w - label_w - 155
    current = y
    for label, left_value, right_value in zip(labels, left, right):
        canvas.text(x, current + 25, short(label, 36), size=20, color=COLORS["muted"], weight=600)
        canvas.rect(bar_x, current, bar_w, 17, "#0b1a1f", rx=9)
        canvas.rect(bar_x, current, max(3, int(bar_w * left_value / max_value)), 17, COLORS["blue"], rx=9)
        canvas.rect(bar_x, current + 24, bar_w, 17, "#0b1a1f", rx=9)
        canvas.rect(bar_x, current + 24, max(3, int(bar_w * right_value / max_value)), 17, COLORS["green"], rx=9)
        canvas.text(bar_x + bar_w + 24, current + 15, formatter(left_value), size=18, color=COLORS["blue"], weight=700)
        canvas.text(bar_x + bar_w + 24, current + 39, formatter(right_value), size=18, color=COLORS["green"], weight=700)
        current += row_h
    return current


def load_run(path: Path, name: str) -> dict[str, Any]:
    metrics = read_json(path)
    heads = {
        field: float(metrics.get("test_metrics", {}).get(field, {}).get("macro_f1", 0.0))
        for field in TARGET_COLS
    }
    return {
        "name": name,
        "epochs": metrics.get("epochs"),
        "lr": metrics.get("lr"),
        "silver_weight": metrics.get("silver_weight_override"),
        "heads": heads,
        "mean_macro_f1": sum(heads.values()) / len(heads),
    }


def taxonomy_counts(stats: dict[str, Any], field: str) -> dict[str, int]:
    return {item["value"]: int(item["count"]) for item in stats["approved_dataset_taxonomy"][field]}


def collect(args: argparse.Namespace) -> dict[str, Any]:
    export_dir = Path(args.export_dir)
    runs_dir = Path(args.runs_dir)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stats": read_json(export_dir / "03_gold_statistics" / "annotation_statistics.json"),
        "silver": read_json(export_dir / "06_silver_auto_labeled_all.summary.json"),
        "manifest": read_json(export_dir / "04_gold_silver_manifest.json"),
        "runs": {
            "gold": load_run(runs_dir / "gold_only_full_2026-06-03_01-06" / "metrics.json", "gold-only"),
            "initial": load_run(runs_dir / "gold_silver_full_2026-06-03_01-06" / "metrics.json", "first gold+silver"),
            "quick": load_run(runs_dir / "sweep_2026-06-03" / "quick_w03_weighted" / "metrics.json", "quick best"),
            "final": load_run(runs_dir / "sweep_final_2026-06-03" / "final_w03_weighted_lr1e5_e4" / "metrics.json", "final best"),
        },
    }


def graph_production(data: dict[str, Any]) -> str:
    totals = data["stats"]["totals"]
    scores = data["stats"]["scores"]
    c = Canvas(1500, 900, "Production-разметка: проверка и исходы")
    c.header("Снимок production database из full teacher-student export 2026-06-03_01-06")
    c.metric(64, 165, 250, 120, fmt_int(totals["annotations_checked"]), "проверено всего", COLORS["green"])
    c.metric(340, 165, 250, 120, fmt_int(totals["annotations_approved_dataset"]), "training-ready gold", COLORS["yellow"])
    c.metric(616, 165, 250, 120, fmt_int(totals["deleted_posts_confirmed"]), "удаленные посты", COLORS["orange"])
    c.metric(892, 165, 250, 120, fmt_int(totals["annotations_rejected_total"]), "отклонено", COLORS["red"])
    c.metric(1168, 165, 250, 120, fmt_int(scores["net_points"]), "net points", COLORS["purple"])
    items = [
        ("Training-ready approved", totals["annotations_approved_dataset"], COLORS["yellow"]),
        ("Confirmed deleted posts", totals["deleted_posts_confirmed"], COLORS["orange"]),
        ("Rejected annotations", totals["annotations_rejected_total"], COLORS["red"]),
        ("Pending", totals["annotations_pending"], COLORS["gray"]),
    ]
    horizontal_bars(c, 110, 390, 1260, items, max_value=totals["annotations_checked"], row_h=70)
    c.wrapped(
        110,
        730,
        "Вывод: очередь проверки закрыта, pending = 0. Gold dataset отделен от подтвержденных удаленных постов, поэтому обучение не смешивает реальные метки и исключения без контекста.",
        chars=108,
        size=24,
        color=COLORS["ink"],
        line_height=34,
    )
    return c.finish()


def graph_gold_silver_relevance(data: dict[str, Any]) -> str:
    stats = data["stats"]
    silver = data["silver"]
    gold_rel = taxonomy_counts(stats, "jkh_relevance")
    silver_rel = silver["distributions"]["jkh_relevance"]
    labels = ["ЖКХ yes", "ЖКХ no", "unsure"]
    gold_values = [gold_rel.get("yes", 0), gold_rel.get("no", 0), gold_rel.get("unsure", 0)]
    silver_values = [silver_rel.get("yes", 0), silver_rel.get("no", 0), silver_rel.get("unsure", 0)]
    c = Canvas(1500, 800, "Gold vs Silver: релевантность ЖКХ")
    c.header("Сравнение human-approved gold и automatic teacher silver")
    c.metric(64, 165, 310, 120, fmt_int(sum(gold_values)), "human gold labels", COLORS["yellow"])
    c.metric(404, 165, 310, 120, fmt_int(sum(silver_values)), "silver labels", COLORS["purple"])
    c.metric(744, 165, 310, 120, fmt_pct(gold_values[0] / max(sum(gold_values), 1)), "доля ЖКХ yes в gold", COLORS["green"])
    c.metric(1084, 165, 310, 120, fmt_pct(silver_values[0] / max(sum(silver_values), 1)), "доля ЖКХ yes в silver", COLORS["green"])
    grouped_bars(c, 110, 405, 1260, labels, gold_values, silver_values, "gold", "silver", max_value=max(max(gold_values), max(silver_values)), formatter=fmt_int, row_h=82)
    c.wrapped(110, 700, "Silver сохраняет общий non-JKH фон, но резко расширяет положительные ЖКХ-примеры для обучения.", chars=104, size=24, color=COLORS["ink"])
    return c.finish()


def graph_topics(data: dict[str, Any]) -> str:
    stats = data["stats"]
    silver = data["silver"]
    gold_topics = taxonomy_counts(stats, "jkh_topic")
    silver_topics = silver["distributions"]["jkh_topic"]
    keys = [
        "not_jkh",
        "waste_cleaning",
        "heating_hot_water",
        "cold_water_sewerage",
        "yard_area",
        "house_common_property",
        "payments_tariffs",
        "public_authorities",
        "other_jkh",
    ]
    gold_total = sum(gold_topics.values()) or 1
    silver_total = sum(silver_topics.values()) or 1
    labels = [TOPIC_LABELS.get(key, key) for key in keys]
    gold_pct = [gold_topics.get(key, 0) / gold_total for key in keys]
    silver_pct = [silver_topics.get(key, 0) / silver_total for key in keys]
    c = Canvas(1500, 1120, "Распределение тем: human gold vs silver")
    c.header("Проценты внутри каждого корпуса; так легче сравнивать разные объемы")
    grouped_bars(c, 110, 210, 1260, labels, gold_pct, silver_pct, "gold %", "silver %", max_value=max(gold_pct + silver_pct), formatter=lambda v: fmt_pct(v, 1), row_h=82)
    c.wrapped(
        110,
        1010,
        "Вывод: основная коррекция после enrichment и silver labeling - больше разнообразия в ЖКХ-темах, особенно мусор/уборка, двор/территория, отопление/ГВС и вода/канализация.",
        chars=110,
        size=24,
        color=COLORS["ink"],
    )
    return c.finish()


def graph_dataset(data: dict[str, Any]) -> str:
    ds = {
        "gold_train": 3055,
        "gold_validation": 655,
        "gold_test": 655,
        "silver_train": 259728,
        "gold_silver_total": 264093,
    }
    c = Canvas(1500, 820, "Fixed split для teacher-student обучения")
    c.header("Оценка качества остается на human-gold validation/test")
    c.metric(64, 165, 270, 120, fmt_int(ds["gold_train"]), "gold train", COLORS["green"])
    c.metric(364, 165, 270, 120, fmt_int(ds["gold_validation"]), "gold validation", COLORS["cyan"])
    c.metric(664, 165, 270, 120, fmt_int(ds["gold_test"]), "gold test", COLORS["blue"])
    c.metric(964, 165, 270, 120, fmt_int(ds["silver_train"]), "silver train", COLORS["purple"])
    items = [
        ("gold train", ds["gold_train"], COLORS["green"]),
        ("gold validation", ds["gold_validation"], COLORS["cyan"]),
        ("gold test", ds["gold_test"], COLORS["blue"]),
        ("silver train", ds["silver_train"], COLORS["purple"]),
        ("full fixed dataset", ds["gold_silver_total"], COLORS["orange"]),
    ]
    horizontal_bars(c, 110, 390, 1260, items, max_value=ds["gold_silver_total"], row_h=64)
    c.wrapped(110, 735, "Gold sample weight = 1.0. Silver sample weight по умолчанию = 0.4; лучший sweep использует override 0.3.", chars=112, size=24, color=COLORS["ink"])
    return c.finish()


def graph_model_runs(data: dict[str, Any]) -> str:
    runs = data["runs"]
    c = Canvas(1500, 820, "RuBERT teacher-student: сравнение запусков")
    c.header("Метрика: средний macro-F1 по 8 головам на held-out human-gold test")
    items = [
        ("gold-only", runs["gold"]["mean_macro_f1"], COLORS["blue"]),
        ("first gold+silver", runs["initial"]["mean_macro_f1"], COLORS["purple"]),
        ("quick best", runs["quick"]["mean_macro_f1"], COLORS["yellow"]),
        ("final best", runs["final"]["mean_macro_f1"], COLORS["green"]),
    ]
    c.metric(64, 165, 310, 120, fmt_float(runs["gold"]["mean_macro_f1"]), "gold-only baseline", COLORS["blue"])
    c.metric(404, 165, 310, 120, fmt_float(runs["final"]["mean_macro_f1"]), "best final model", COLORS["green"])
    c.metric(744, 165, 310, 120, "+" + fmt_float(runs["final"]["mean_macro_f1"] - runs["gold"]["mean_macro_f1"]), "delta vs gold-only", COLORS["orange"])
    c.metric(1084, 165, 310, 120, "0.3086", "best validation macro-F1", COLORS["yellow"])
    horizontal_bars(c, 110, 400, 1260, items, max_value=0.35, formatter=lambda v: fmt_float(v, 4), row_h=72)
    c.wrapped(110, 725, "Вывод: silver-расширение дает основной прирост; финальный sweep немного улучшает результат и сохраняет лучший checkpoint.", chars=110, size=24, color=COLORS["ink"])
    return c.finish()


def graph_per_head(data: dict[str, Any]) -> str:
    runs = data["runs"]
    labels = [HEAD_LABELS[key] for key in TARGET_COLS]
    gold = [runs["gold"]["heads"][key] for key in TARGET_COLS]
    final = [runs["final"]["heads"][key] for key in TARGET_COLS]
    c = Canvas(1500, 1100, "По головам модели: что улучшилось")
    c.header("Macro-F1 на human-gold test: gold-only против final teacher-student")
    grouped_bars(c, 110, 210, 1260, labels, gold, final, "gold-only", "final", max_value=0.50, formatter=lambda v: fmt_float(v, 3), row_h=86)
    c.wrapped(
        110,
        970,
        "Сильнее всего выросли тема ЖКХ и тип обращения. Responsible party остается слабой головой: классы редкие, пересекающиеся и плохо представлены даже после silver.",
        chars=112,
        size=24,
        color=COLORS["ink"],
    )
    return c.finish()


def graph_campaign(data: dict[str, Any]) -> str:
    c = Canvas(1500, 850, "ЖКХ-enrichment: отбор приоритетных записей")
    c.header("Пост задает тему; комментарий используется как реакция и уточнение")
    items = [
        ("Активировано ЖКХ-кандидатов", 14954, COLORS["orange"]),
        ("Контрольных записей", 150, COLORS["gray"]),
        ("Общий пул paused", 244684, COLORS["red"]),
        ("Первый offline batch applied", 500, COLORS["green"]),
        ("Full JKH batch prepared", 14376, COLORS["yellow"]),
    ]
    c.metric(64, 165, 300, 120, fmt_int(14954), "JKH candidates", COLORS["orange"])
    c.metric(394, 165, 300, 120, fmt_int(14376), "prepared offline labels", COLORS["yellow"])
    c.metric(724, 165, 300, 120, fmt_int(500), "applied to production", COLORS["green"])
    c.metric(1054, 165, 300, 120, fmt_int(244684), "paused general pool", COLORS["red"])
    horizontal_bars(c, 110, 400, 1260, items, max_value=244684, row_h=66)
    c.wrapped(110, 760, "Статус: полный JKH batch подготовлен локально и использован в silver; production-применение зафиксировано только для первых 500.", chars=112, size=24, color=COLORS["ink"])
    return c.finish()


def graph_dashboard(data: dict[str, Any]) -> str:
    stats = data["stats"]
    totals = stats["totals"]
    silver = data["silver"]
    runs = data["runs"]
    final = runs["final"]
    gold = runs["gold"]
    c = Canvas(1800, 4200, "ЖКХ-разметка: процесс, данные, модель")
    c.header("Чистая версия dashboard v2: больше воздуха, отдельные графики, без налезания текста")

    c.metric(80, 165, 260, 120, fmt_int(totals["source_records_total"]), "исходных записей", COLORS["cyan"])
    c.metric(370, 165, 260, 120, fmt_int(totals["annotations_checked"]), "проверено", COLORS["green"])
    c.metric(660, 165, 260, 120, fmt_int(totals["annotations_approved_dataset"]), "human gold", COLORS["yellow"])
    c.metric(950, 165, 260, 120, fmt_int(silver["counts"]["rows"]), "silver labels", COLORS["purple"])
    c.metric(1240, 165, 260, 120, fmt_float(final["mean_macro_f1"]), "best test macro-F1", COLORS["green"])
    c.metric(1530, 165, 190, 120, "+" + fmt_float(final["mean_macro_f1"] - gold["mean_macro_f1"]), "delta", COLORS["orange"])

    c.card(80, 340, 1640, 440, "1. Production review outcomes", COLORS["green"])
    items = [
        ("Training-ready approved", totals["annotations_approved_dataset"], COLORS["yellow"]),
        ("Confirmed deleted posts", totals["deleted_posts_confirmed"], COLORS["orange"]),
        ("Rejected annotations", totals["annotations_rejected_total"], COLORS["red"]),
        ("Pending", totals["annotations_pending"], COLORS["gray"]),
    ]
    horizontal_bars(c, 130, 425, 1500, items, max_value=totals["annotations_checked"], row_h=62, label_w=420)

    c.card(80, 840, 1640, 520, "2. Gold vs silver relevance", COLORS["purple"])
    gold_rel = taxonomy_counts(stats, "jkh_relevance")
    silver_rel = silver["distributions"]["jkh_relevance"]
    grouped_bars(
        c,
        130,
        940,
        1500,
        ["ЖКХ yes", "ЖКХ no", "unsure"],
        [gold_rel.get("yes", 0), gold_rel.get("no", 0), gold_rel.get("unsure", 0)],
        [silver_rel.get("yes", 0), silver_rel.get("no", 0), silver_rel.get("unsure", 0)],
        "gold",
        "silver",
        max_value=max(silver_rel.values()),
        formatter=fmt_int,
        row_h=86,
        label_w=420,
    )
    c.wrapped(130, 1270, "Gold остается эталоном оценки; silver расширяет train-пул и добавляет много положительных ЖКХ-примеров.", chars=128, size=22, color=COLORS["ink"])

    c.card(80, 1420, 1640, 700, "3. Topic distribution, normalized", COLORS["yellow"])
    keys = ["not_jkh", "waste_cleaning", "heating_hot_water", "cold_water_sewerage", "yard_area", "house_common_property", "payments_tariffs", "public_authorities", "other_jkh"]
    gold_topics = taxonomy_counts(stats, "jkh_topic")
    silver_topics = silver["distributions"]["jkh_topic"]
    gold_total = sum(gold_topics.values()) or 1
    silver_total = sum(silver_topics.values()) or 1
    grouped_bars(
        c,
        130,
        1520,
        1500,
        [TOPIC_LABELS.get(key, key) for key in keys],
        [gold_topics.get(key, 0) / gold_total for key in keys],
        [silver_topics.get(key, 0) / silver_total for key in keys],
        "gold %",
        "silver %",
        max_value=0.82,
        formatter=lambda v: fmt_pct(v, 1),
        row_h=62,
        label_w=420,
    )

    c.card(80, 2180, 1640, 500, "4. Teacher-student dataset split", COLORS["blue"])
    split_items = [
        ("Gold train", 3055, COLORS["green"]),
        ("Gold validation", 655, COLORS["cyan"]),
        ("Gold test", 655, COLORS["blue"]),
        ("Silver train", 259728, COLORS["purple"]),
        ("Full train/eval file", 264093, COLORS["orange"]),
    ]
    horizontal_bars(c, 130, 2280, 1500, split_items, max_value=264093, row_h=66, label_w=420)
    c.wrapped(130, 2600, "Validation/test не содержат silver, поэтому итоговые метрики не являются самопроверкой automatic teacher-разметки.", chars=128, size=22, color=COLORS["ink"])

    c.card(80, 2740, 1640, 520, "5. Model runs, mean macro-F1", COLORS["green"])
    run_items = [
        ("Gold-only", runs["gold"]["mean_macro_f1"], COLORS["blue"]),
        ("First gold+silver", runs["initial"]["mean_macro_f1"], COLORS["purple"]),
        ("Quick best", runs["quick"]["mean_macro_f1"], COLORS["yellow"]),
        ("Final best", runs["final"]["mean_macro_f1"], COLORS["green"]),
    ]
    horizontal_bars(c, 130, 2840, 1500, run_items, max_value=0.35, formatter=lambda v: fmt_float(v, 4), row_h=72, label_w=420)

    c.card(80, 3320, 1640, 690, "6. Per-head macro-F1: gold-only vs final", COLORS["purple"])
    grouped_bars(
        c,
        130,
        3420,
        1500,
        [HEAD_LABELS[key] for key in TARGET_COLS],
        [runs["gold"]["heads"][key] for key in TARGET_COLS],
        [runs["final"]["heads"][key] for key in TARGET_COLS],
        "gold-only",
        "final",
        max_value=0.50,
        formatter=lambda v: fmt_float(v, 3),
        row_h=62,
        label_w=420,
    )
    c.wrapped(130, 3930, "Вывод: teacher-student уверенно помогает полной таксономии, но responsible_party требует дополнительных gold-примеров редких классов.", chars=128, size=22, color=COLORS["ink"])
    c.text(80, 4150, f"Generated: {data['generated_at']} | Source: teacher_student_full_export_2026-06-03_01-06", size=18, color=COLORS["muted"])
    return c.finish()


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8-sig")


def render_all(data: dict[str, Any], output_dir: Path, desktop_copy: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    charts = {
        "00_full_dashboard_v2.svg": graph_dashboard(data),
        "01_production_review_outcomes.svg": graph_production(data),
        "02_gold_vs_silver_relevance.svg": graph_gold_silver_relevance(data),
        "03_topic_distribution_gold_vs_silver.svg": graph_topics(data),
        "04_teacher_student_dataset_split.svg": graph_dataset(data),
        "05_model_macro_f1_runs.svg": graph_model_runs(data),
        "06_per_head_macro_f1.svg": graph_per_head(data),
        "07_jkh_enrichment_campaign.svg": graph_campaign(data),
    }
    for name, content in charts.items():
        write_text(output_dir / name, content)
    index = [
        "# ЖКХ process graphs v2",
        "",
        "Отдельные графики и исправленный dashboard без налезания текста.",
        "",
    ]
    for name in charts:
        index.append(f"- `{name}`")
    write_text(output_dir / "README.md", "\n".join(index) + "\n")
    (output_dir / "source_summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if desktop_copy:
        desktop_dir = Path.home() / "Desktop" / "ЖКХ_графики_процесс_модель_v2_2026-06-03"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        for path in output_dir.iterdir():
            if path.is_file():
                shutil.copy2(path, desktop_dir / path.name)
        print(f"desktop={desktop_dir}")
    print(f"output={output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", default="data/exports/teacher_student_full_export_2026-06-03_01-06")
    parser.add_argument("--runs-dir", default="data/ml_experiments/teacher_student_runs")
    parser.add_argument("--output-dir", default="data/exports/project_process_graphs_v2_2026-06-03")
    parser.add_argument("--desktop-copy", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = collect(args)
    render_all(data, Path(args.output_dir), args.desktop_copy)


if __name__ == "__main__":
    main()
