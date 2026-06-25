#!/usr/bin/env python
"""Render advanced charts: lines, pies, heatmaps and confusion matrices."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import torch
from sklearn.metrics import confusion_matrix
from torch.utils.data import DataLoader
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments"))

from train_rubert_multitask import (  # noqa: E402
    MultiHeadRuBert,
    TextMultiTaskDataset,
    apply_sample_weight_overrides,
    read_csv,
    set_seed,
    split_rows,
)


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

SHORT_LABELS = {
    "cold_water_sewerage": "ХВС/канал.",
    "heating_hot_water": "Отопл./ГВС",
    "house_common_property": "МКД",
    "management_company": "УК/ТСЖ",
    "not_jkh": "Не ЖКХ",
    "other_jkh": "Другое",
    "payments_tariffs": "Тарифы",
    "public_authorities": "Власть",
    "waste_cleaning": "Мусор",
    "yard_area": "Двор",
    "communication": "Комм.",
    "no_action": "Безд.",
    "not_applicable": "Н/П",
    "other": "Другое",
    "poor_quality": "Качество",
    "positive_feedback": "Позитив",
    "slow_response": "Сроки",
    "supervision": "Контроль",
    "tariff_policy": "Тарифы",
    "local_administration": "Админ.",
    "housing_inspection": "ГЖИ",
    "resource_provider": "РСО",
    "specific_person": "Персона",
    "waste_operator": "Регоп.",
    "residents": "Жители",
    "unknown": "Неясно",
    "complaint": "Жалоба",
    "demand": "Треб.",
    "gratitude": "Благод.",
    "info": "Инфо",
    "opinion": "Мнение",
    "question": "Вопрос",
    "request": "Просьба",
    "suggestion": "Предл.",
    "mixed": "Смеш.",
    "negative": "Негат.",
    "neutral": "Нейтр.",
    "positive": "Позит.",
    "difficult": "Сложн.",
    "duplicate": "Дубль",
    "normal": "Норма",
    "spam": "Спам",
    "no": "Нет",
    "unsure": "Не увер.",
    "yes": "Да",
}

HEAD_LABELS.update(
    {
        "jkh_relevance": "ЖКХ-релевантность",
        "jkh_topic": "Тема ЖКХ",
        "authority_aspect": "Аспект власти",
        "sentiment": "Тональность",
        "appeal_type": "Тип обращения",
        "responsible_party": "Ответственная сторона",
        "sarcasm": "Сарказм",
        "quality": "Качество",
    }
)

SHORT_LABELS.update(
    {
        "cold_water_sewerage": "ХВС/канал.",
        "heating_hot_water": "Отопл./ГВС",
        "house_common_property": "МКД",
        "management_company": "УК/ТСЖ",
        "not_jkh": "Не ЖКХ",
        "other_jkh": "Другое ЖКХ",
        "payments_tariffs": "Тарифы",
        "public_authorities": "Власть",
        "waste_cleaning": "Мусор",
        "yard_area": "Двор",
        "communication": "Комм.",
        "no_action": "Безд.",
        "not_applicable": "Н/П",
        "other": "Другое",
        "poor_quality": "Плох. кач.",
        "positive_feedback": "Позитив",
        "slow_response": "Сроки",
        "supervision": "Надзор",
        "tariff_policy": "Тарифы",
        "local_administration": "Админ.",
        "housing_inspection": "ГЖИ",
        "resource_provider": "РСО",
        "specific_person": "Персона",
        "waste_operator": "Регоп.",
        "residents": "Жители",
        "unknown": "Неясно",
        "complaint": "Жалоба",
        "demand": "Треб.",
        "gratitude": "Благод.",
        "info": "Инфо",
        "opinion": "Мнение",
        "question": "Вопрос",
        "request": "Просьба",
        "suggestion": "Предл.",
        "mixed": "Смеш.",
        "negative": "Негат.",
        "neutral": "Нейтр.",
        "positive": "Позит.",
        "difficult": "Сложн.",
        "duplicate": "Дубль",
        "normal": "Норма",
        "spam": "Спам",
        "no": "Нет",
        "unsure": "Не увер.",
        "yes": "Да",
    }
)

COLORS = {
    "bg": "#081316",
    "panel": "#11252b",
    "panel2": "#163039",
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
    "black": "#071114",
}

SERIES = [
    COLORS["blue"],
    COLORS["purple"],
    COLORS["green"],
    COLORS["yellow"],
    COLORS["orange"],
    COLORS["cyan"],
    COLORS["red"],
    "#d0f4de",
    "#f5cac3",
    "#cdb4db",
]


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class Canvas:
    def __init__(self, width: int, height: int, title: str, subtitle: str | None = None) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.subtitle = subtitle
        self.parts: list[str] = []

    def add(self, value: str) -> None:
        self.parts.append(value)

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str | None = None, rx: float = 12, opacity: float = 1.0) -> None:
        stroke_attr = f' stroke="{stroke}" stroke-width="1.2"' if stroke else ""
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx:.2f}" fill="{fill}" opacity="{opacity}"{stroke_attr}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = COLORS["grid"], width: float = 1.2, opacity: float = 1.0) -> None:
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')

    def circle(self, x: float, y: float, r: float, fill: str, stroke: str | None = None, width: float = 1.0, opacity: float = 1.0) -> None:
        stroke_attr = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
        self.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" opacity="{opacity}"{stroke_attr}/>')

    def path(self, d: str, fill: str, stroke: str | None = None, width: float = 1.0, opacity: float = 1.0) -> None:
        stroke_attr = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
        self.add(f'<path d="{d}" fill="{fill}" opacity="{opacity}"{stroke_attr}/>')

    def polyline(self, points: list[tuple[float, float]], color: str, width: float = 3.0) -> None:
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        self.add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')

    def text(self, x: float, y: float, value: Any, size: int = 22, color: str = COLORS["ink"], weight: int | str = 400, anchor: str = "start", opacity: float = 1.0, rotate: float | None = None) -> None:
        transform = f' transform="rotate({rotate:.1f} {x:.2f} {y:.2f})"' if rotate is not None else ""
        self.add(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" opacity="{opacity}"{transform}>{esc(value)}</text>'
        )

    def header(self) -> None:
        self.text(54, 72, self.title, size=42, weight=850)
        if self.subtitle:
            self.text(54, 108, self.subtitle, size=21, color=COLORS["muted"])

    def finish(self) -> str:
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#10262c"/>
    <stop offset="60%" stop-color="#081316"/>
    <stop offset="100%" stop-color="#1b1828"/>
  </linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="14" stdDeviation="14" flood-color="#000000" flood-opacity="0.28"/>
  </filter>
</defs>
<rect width="100%" height="100%" fill="url(#bg)"/>
<circle cx="{self.width - 120}" cy="110" r="230" fill="#54d8cf" opacity="0.06"/>
<circle cx="160" cy="{self.height - 130}" r="250" fill="#ff6b6b" opacity="0.05"/>
<g filter="url(#shadow)">
{chr(10).join(self.parts)}
</g>
</svg>
'''


def mean_macro(metrics: dict[str, Any]) -> float:
    return sum(float(metrics["test_metrics"][field]["macro_f1"]) for field in TARGET_COLS) / len(TARGET_COLS)


def load_metrics(path: Path, name: str) -> dict[str, Any]:
    metrics = read_json(path)
    return {
        "name": name,
        "metrics": metrics,
        "mean_macro_f1": mean_macro(metrics),
        "heads": {field: float(metrics["test_metrics"][field]["macro_f1"]) for field in TARGET_COLS},
        "history": metrics.get("history", []),
    }


def color_scale(value: float, max_value: float, low: tuple[int, int, int] = (17, 37, 43), high: tuple[int, int, int] = (84, 216, 207)) -> str:
    ratio = 0.0 if max_value <= 0 else max(0.0, min(1.0, value / max_value))
    gamma = math.sqrt(ratio)
    rgb = [int(low[i] + (high[i] - low[i]) * gamma) for i in range(3)]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def pie_segment(cx: float, cy: float, r: float, start: float, end: float) -> str:
    x1 = cx + r * math.cos(start)
    y1 = cy + r * math.sin(start)
    x2 = cx + r * math.cos(end)
    y2 = cy + r * math.sin(end)
    large = 1 if end - start > math.pi else 0
    return f"M {cx:.2f} {cy:.2f} L {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {x2:.2f} {y2:.2f} Z"


def donut_chart(canvas: Canvas, cx: float, cy: float, r: float, values: list[tuple[str, int, str]]) -> None:
    total = sum(v for _, v, _ in values) or 1
    start = -math.pi / 2
    for label, value, color in values:
        end = start + 2 * math.pi * value / total
        canvas.path(pie_segment(cx, cy, r, start, end), color)
        start = end
    canvas.circle(cx, cy, r * 0.56, COLORS["panel"], opacity=1)
    canvas.text(cx, cy - 4, fmt_int(total), size=30, color=COLORS["ink"], weight=850, anchor="middle")
    canvas.text(cx, cy + 28, "total", size=17, color=COLORS["muted"], anchor="middle")
    lx = cx + r + 55
    ly = cy - r + 28
    for label, value, color in values:
        canvas.rect(lx, ly - 16, 22, 14, color, rx=7)
        canvas.text(lx + 34, ly, f"{label}: {fmt_int(value)} ({fmt_pct(value / total)})", size=19, color=COLORS["ink"])
        ly += 34


def line_chart(
    canvas: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    series: list[tuple[str, list[tuple[int, float]], str]],
    y_min: float,
    y_max: float,
    formatter: Callable[[float], str],
) -> None:
    canvas.rect(x, y, w, h, COLORS["panel"], COLORS["line"], rx=18)
    plot_x = x + 78
    plot_y = y + 52
    plot_w = w - 118
    plot_h = h - 105
    for i in range(6):
        yy = plot_y + plot_h * i / 5
        val = y_max - (y_max - y_min) * i / 5
        canvas.line(plot_x, yy, plot_x + plot_w, yy, COLORS["grid"], opacity=0.55)
        canvas.text(plot_x - 18, yy + 6, formatter(val), size=15, color=COLORS["muted"], anchor="end")
    max_epoch = max((epoch for _, points, _ in series for epoch, _ in points), default=1)
    for epoch in range(1, max_epoch + 1):
        xx = plot_x + plot_w * (epoch - 1) / max(max_epoch - 1, 1)
        canvas.line(xx, plot_y, xx, plot_y + plot_h, COLORS["grid"], opacity=0.28)
        canvas.text(xx, plot_y + plot_h + 30, str(epoch), size=16, color=COLORS["muted"], anchor="middle")
    canvas.text(plot_x + plot_w / 2, y + h - 18, "epoch", size=17, color=COLORS["muted"], anchor="middle")
    for name, points, color in series:
        mapped = []
        for epoch, value in points:
            xx = plot_x + plot_w * (epoch - 1) / max(max_epoch - 1, 1)
            yy = plot_y + plot_h * (1 - (value - y_min) / max(y_max - y_min, 1e-9))
            mapped.append((xx, yy))
        if mapped:
            canvas.polyline(mapped, color, width=4)
            for xx, yy in mapped:
                canvas.circle(xx, yy, 5, color, stroke=COLORS["bg"], width=2)
    lx = plot_x + 20
    ly = y + 28
    for name, _, color in series:
        canvas.rect(lx, ly - 13, 22, 12, color, rx=6)
        canvas.text(lx + 32, ly, name, size=17, color=COLORS["muted"])
        lx += 285


def heatmap(
    canvas: Canvas,
    x: float,
    y: float,
    labels_x: list[str],
    labels_y: list[str],
    values: list[list[float]],
    cell: float,
    formatter: Callable[[float], str],
    title: str | None = None,
    label_w: float = 210,
    top_h: float = 110,
    x_label_size: int = 16,
    y_label_size: int = 17,
    value_size: int = 14,
    rotate_x: float = -42,
) -> None:
    if title:
        canvas.text(x, y - 18, title, size=26, weight=760)
    max_value = max([v for row in values for v in row] or [1])
    canvas.rect(x, y, label_w + cell * len(labels_x) + 20, top_h + cell * len(labels_y) + 28, COLORS["panel"], COLORS["line"], rx=18)
    for i, label in enumerate(labels_x):
        cx = x + label_w + i * cell + cell / 2
        canvas.text(cx, y + top_h - 18, label, size=x_label_size, color=COLORS["muted"], anchor="end", rotate=rotate_x)
    for j, label in enumerate(labels_y):
        cy = y + top_h + j * cell + cell * 0.62
        canvas.text(x + label_w - 18, cy, label, size=y_label_size, color=COLORS["muted"], anchor="end")
    for j, row in enumerate(values):
        for i, value in enumerate(row):
            cx = x + label_w + i * cell
            cy = y + top_h + j * cell
            color = color_scale(value, max_value)
            canvas.rect(cx, cy, cell - 3, cell - 3, color, rx=6)
            text_color = COLORS["bg"] if value / max_value > 0.62 else COLORS["ink"]
            canvas.text(cx + cell / 2 - 1, cy + cell * 0.58, formatter(value), size=value_size, color=text_color, weight=750, anchor="middle")


def render_confusion_matrix(field: str, labels: list[str], matrix: list[list[int]], normalized: list[list[float]], output: Path) -> None:
    n = len(labels)
    cell = max(46, min(76, 760 // max(n, 1)))
    width = 360 + cell * n + 90
    height = 320 + cell * n + 120
    c = Canvas(width, height, f"Матрица ошибок: {HEAD_LABELS[field]}", "Final teacher-student model, human-gold test")
    c.header()
    short_labels = [SHORT_LABELS.get(label, label[:10]) for label in labels]
    heatmap(c, 60, 175, short_labels, short_labels, normalized, cell, lambda v: fmt_pct(v, 0), title="Нормировано по истинному классу")
    c.text(80, height - 62, "Y: истинный класс; X: предсказание. В ячейках доля внутри строки.", size=20, color=COLORS["muted"])
    output.write_text(c.finish(), encoding="utf-8-sig")


def evaluate_best_model(args: argparse.Namespace, metrics: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    eval_path = output_dir / "confusion_matrices.json"
    if eval_path.exists() and not args.force_eval:
        return read_json(eval_path)

    set_seed(42)
    rows = [row for row in read_csv(metrics["input_csv"]) if all(row.get(col) for col in TARGET_COLS)]
    apply_sample_weight_overrides(rows, metrics.get("gold_weight_override"), metrics.get("silver_weight_override"))
    _, _, test_rows = split_rows(rows, 0.15, 0.15, 42)
    label_maps = metrics["label_maps"]
    inverse_maps = {col: {idx: label for label, idx in mapping.items()} for col, mapping in label_maps.items()}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer_path = Path(args.best_run_dir) / "tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"])
    dataset = TextMultiTaskDataset(
        test_rows,
        TARGET_COLS,
        label_maps,
        tokenizer,
        metrics["max_length"],
        metrics["text_mode"],
        cache_tokenization=True,
        tokenization_batch_size=1024,
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, pin_memory=(device.type == "cuda"))
    model = MultiHeadRuBert(
        metrics["base_model"],
        {col: len(label_maps[col]) for col in TARGET_COLS},
        dropout=float(metrics.get("dropout", 0.3)),
    ).to(device)
    state = torch.load(Path(args.best_run_dir) / "model.pt", map_location=device)
    model.load_state_dict(state)
    model.eval()

    y_true = {col: [] for col in TARGET_COLS}
    y_pred = {col: [] for col in TARGET_COLS}
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device=device, dtype=torch.long)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            for col in TARGET_COLS:
                y_true[col].extend(batch[col].cpu().tolist())
                y_pred[col].extend(torch.argmax(outputs[col], dim=1).cpu().tolist())

    result = {"rows": len(test_rows), "device": str(device), "matrices": {}, "predictions": {}}
    for col in TARGET_COLS:
        labels_idx = list(range(len(label_maps[col])))
        labels = [inverse_maps[col][idx] for idx in labels_idx]
        cm = confusion_matrix(y_true[col], y_pred[col], labels=labels_idx)
        row_sums = cm.sum(axis=1, keepdims=True)
        norm = cm.astype(float) / (row_sums + (row_sums == 0))
        result["matrices"][col] = {
            "labels": labels,
            "counts": cm.astype(int).tolist(),
            "row_normalized": norm.tolist(),
        }
        result["predictions"][col] = {
            "y_true": y_true[col],
            "y_pred": y_pred[col],
        }
    eval_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def graph_training_curves(runs: dict[str, dict[str, Any]], output: Path) -> None:
    c = Canvas(1500, 900, "Линейные графики обучения", "Validation macro-F1 и train loss по эпохам")
    c.header()
    val_series = []
    loss_series = []
    for idx, key in enumerate(["initial", "final_w03", "final_w04", "final_lr1e5"]):
        run = runs[key]
        history = run["history"]
        color = SERIES[idx]
        val_series.append((run["name"], [(int(h["epoch"]), float(h["mean_val_macro_f1"])) for h in history], color))
        loss_series.append((run["name"], [(int(h["epoch"]), float(h["train"]["loss"])) for h in history], color))
    line_chart(c, 70, 155, 1360, 330, val_series, 0.25, 0.33, lambda v: fmt_float(v, 3))
    c.text(92, 190, "Validation mean macro-F1", size=24, weight=760)
    line_chart(c, 70, 535, 1360, 300, loss_series, 1.2, 3.1, lambda v: fmt_float(v, 1))
    c.text(92, 570, "Train loss", size=24, weight=760)
    output.write_text(c.finish(), encoding="utf-8-sig")


def graph_pies(data: dict[str, Any], output: Path) -> None:
    stats = data["stats"]
    totals = stats["totals"]
    silver = data["silver"]
    c = Canvas(1600, 1050, "Pie / donut charts", "Доли outcome, relevance и состава обучающего файла")
    c.header()
    donut_chart(
        c,
        255,
        310,
        145,
        [
            ("approved dataset", totals["annotations_approved_dataset"], COLORS["green"]),
            ("deleted confirmed", totals["deleted_posts_confirmed"], COLORS["orange"]),
            ("rejected", totals["annotations_rejected_total"], COLORS["red"]),
        ],
    )
    c.text(110, 520, "Production outcomes", size=25, weight=760)

    gold_rel = {item["value"]: int(item["count"]) for item in stats["approved_dataset_taxonomy"]["jkh_relevance"]}
    donut_chart(
        c,
        255,
        760,
        145,
        [
            ("yes", gold_rel.get("yes", 0), COLORS["green"]),
            ("no", gold_rel.get("no", 0), COLORS["gray"]),
            ("unsure", gold_rel.get("unsure", 0), COLORS["yellow"]),
        ],
    )
    c.text(130, 970, "Human gold relevance", size=25, weight=760)

    silver_rel = silver["distributions"]["jkh_relevance"]
    donut_chart(
        c,
        965,
        310,
        145,
        [
            ("yes", silver_rel.get("yes", 0), COLORS["green"]),
            ("no", silver_rel.get("no", 0), COLORS["gray"]),
        ],
    )
    c.text(825, 520, "Silver relevance", size=25, weight=760)

    donut_chart(
        c,
        965,
        760,
        145,
        [
            ("gold train/val/test", 4365, COLORS["yellow"]),
            ("silver train", 259728, COLORS["purple"]),
        ],
    )
    c.text(825, 970, "Teacher-student file", size=25, weight=760)
    output.write_text(c.finish(), encoding="utf-8-sig")


def graph_metrics_heatmap(runs: dict[str, dict[str, Any]], output: Path) -> None:
    c = Canvas(1550, 900, "Тепловая карта качества модели", "Macro-F1 по запускам и головам таксономии")
    c.header()
    run_order = ["gold", "initial", "quick", "final"]
    labels_y = [runs[key]["name"] for key in run_order]
    labels_x = [HEAD_LABELS[field] for field in TARGET_COLS]
    values = [[runs[key]["heads"][field] for field in TARGET_COLS] for key in run_order]
    heatmap(c, 70, 175, labels_x, labels_y, values, 105, lambda v: fmt_float(v, 2), title="Macro-F1")
    c.text(95, 790, "Чем ярче ячейка, тем выше macro-F1. Gold-only проваливает многоклассовые головы; silver заметно поднимает тему ЖКХ и тип обращения.", size=22, color=COLORS["muted"])
    output.write_text(c.finish(), encoding="utf-8-sig")


def graph_confusion_grid(conf: dict[str, Any], output: Path) -> None:
    c = Canvas(1800, 2300, "Confusion matrices: все головы", "Нормировано по истинному классу, final teacher-student на human-gold test")
    c.header()
    positions = [(70, 160), (940, 160), (70, 690), (940, 690), (70, 1220), (940, 1220), (70, 1750), (940, 1750)]
    for (x, y), field in zip(positions, TARGET_COLS):
        mat = conf["matrices"][field]
        labels = [SHORT_LABELS.get(label, label[:8]) for label in mat["labels"]]
        norm = mat["row_normalized"]
        n = len(labels)
        cell = min(54, max(34, 455 // max(n, 1)))
        c.text(x, y, HEAD_LABELS[field], size=24, weight=760)
        heatmap(c, x, y + 35, labels, labels, norm, cell, lambda v: fmt_pct(v, 0))
    c.text(80, 2255, "Y: истинный класс; X: предсказание. Большая яркая диагональ = меньше ошибок.", size=20, color=COLORS["muted"])
    output.write_text(c.finish(), encoding="utf-8-sig")


def render_confusion_matrix(field: str, labels: list[str], matrix: list[list[int]], normalized: list[list[float]], output: Path) -> None:
    n = len(labels)
    cell = max(64, min(88, 840 // max(n, 1)))
    label_w = 245
    top_h = 150
    width = int(label_w + cell * n + 190)
    height = int(340 + top_h + cell * n + 120)
    c = Canvas(width, height, f"Матрица ошибок: {HEAD_LABELS[field]}", "Final teacher-student model, human-gold test")
    c.header()
    short_labels = [SHORT_LABELS.get(label, label[:10]) for label in labels]
    heatmap(
        c,
        60,
        185,
        short_labels,
        short_labels,
        normalized,
        cell,
        lambda v: fmt_pct(v, 0),
        title="Нормировано по истинному классу",
        label_w=label_w,
        top_h=top_h,
        x_label_size=18,
        y_label_size=19,
        value_size=16,
        rotate_x=-45,
    )
    c.text(80, height - 62, "Y: истинный класс; X: предсказание. В ячейках показана доля внутри строки.", size=20, color=COLORS["muted"])
    output.write_text(c.finish(), encoding="utf-8-sig")


def graph_confusion_grid(conf: dict[str, Any], output: Path) -> None:
    card_w = 1080
    card_h = 815
    margin_x = 80
    col_gap = 90
    row_gap = 900
    start_y = 180
    width = margin_x * 2 + card_w * 2 + col_gap
    height = start_y + row_gap * 4 + 170
    c = Canvas(width, height, "Confusion matrices: все головы", "Нормировано по истинному классу, final teacher-student на human-gold test")
    c.header()

    for idx, field in enumerate(TARGET_COLS):
        col = idx % 2
        row = idx // 2
        x = margin_x + col * (card_w + col_gap)
        y = start_y + row * row_gap
        mat = conf["matrices"][field]
        labels = [SHORT_LABELS.get(label, label[:9]) for label in mat["labels"]]
        norm = mat["row_normalized"]
        n = len(labels)
        cell = max(52, min(68, 590 // max(n, 1)))
        label_w = 235
        top_h = 142
        c.text(x, y, HEAD_LABELS[field], size=31, weight=820)
        heatmap(
            c,
            x,
            y + 55,
            labels,
            labels,
            norm,
            cell,
            lambda v: fmt_pct(v, 0),
            label_w=label_w,
            top_h=top_h,
            x_label_size=17,
            y_label_size=18,
            value_size=15,
            rotate_x=-45,
        )
        c.text(x, y + card_h - 18, "Y: истина; X: предсказание", size=18, color=COLORS["muted"])

    c.text(90, height - 72, "Чем ярче диагональ, тем меньше ошибок. Значения в ячейках показывают долю внутри истинного класса.", size=24, color=COLORS["muted"])
    output.write_text(c.finish(), encoding="utf-8-sig")


def graph_topic_stacked(data: dict[str, Any], output: Path) -> None:
    stats = data["stats"]
    silver = data["silver"]
    gold_topics = {item["value"]: int(item["count"]) for item in stats["approved_dataset_taxonomy"]["jkh_topic"]}
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
    c = Canvas(1600, 900, "Stacked distribution: темы ЖКХ", "Сравнение долей gold и silver")
    c.header()
    x, y, w, h = 120, 250, 1220, 90
    for row_idx, (name, values) in enumerate([("Human gold", gold_topics), ("automatic silver", silver_topics)]):
        total = sum(values.values()) or 1
        yy = y + row_idx * 230
        c.text(x, yy - 28, name, size=28, weight=760)
        offset = 0
        for idx, key in enumerate(keys):
            val = values.get(key, 0)
            seg = w * val / total
            c.rect(x + offset, yy, seg, h, SERIES[idx % len(SERIES)], rx=10 if idx == 0 else 0)
            if seg > 76:
                c.text(x + offset + seg / 2, yy + 54, fmt_pct(val / total, 0), size=18, color=COLORS["bg"], weight=800, anchor="middle")
            offset += seg
        c.text(x + w + 35, yy + 55, fmt_int(total), size=24, color=COLORS["ink"], weight=760)
    lx, ly = 120, 720
    for idx, key in enumerate(keys):
        col = SERIES[idx % len(SERIES)]
        c.rect(lx, ly - 17, 22, 14, col, rx=7)
        c.text(lx + 32, ly, SHORT_LABELS.get(key, key), size=19, color=COLORS["muted"])
        lx += 250
        if lx > 1320:
            lx = 120
            ly += 42
    output.write_text(c.finish(), encoding="utf-8-sig")


def build_data(args: argparse.Namespace) -> dict[str, Any]:
    export_dir = Path(args.export_dir)
    runs_dir = Path(args.runs_dir)
    stats = read_json(export_dir / "03_gold_statistics" / "annotation_statistics.json")
    silver = read_json(export_dir / "06_silver_auto_labeled_all.summary.json")
    runs = {
        "gold": load_metrics(runs_dir / "gold_only_full_2026-06-03_01-06" / "metrics.json", "gold-only"),
        "initial": load_metrics(runs_dir / "gold_silver_full_2026-06-03_01-06" / "metrics.json", "first gold+silver"),
        "quick": load_metrics(runs_dir / "sweep_2026-06-03" / "quick_w03_weighted" / "metrics.json", "quick best"),
        "final": load_metrics(runs_dir / "sweep_final_2026-06-03" / "final_w03_weighted_lr1e5_e4" / "metrics.json", "final best"),
        "final_w03": load_metrics(runs_dir / "sweep_final_2026-06-03" / "final_w03_weighted_e4" / "metrics.json", "final w03 lr2e-5"),
        "final_w04": load_metrics(runs_dir / "sweep_final_2026-06-03" / "final_w04_weighted_e4" / "metrics.json", "final w04 lr2e-5"),
        "final_lr1e5": load_metrics(runs_dir / "sweep_final_2026-06-03" / "final_w03_weighted_lr1e5_e4" / "metrics.json", "final w03 lr1e-5"),
    }
    return {"stats": stats, "silver": silver, "runs": runs}


def render_all(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = build_data(args)
    best_metrics = data["runs"]["final"]["metrics"]
    conf = evaluate_best_model(args, best_metrics, output_dir)

    graph_training_curves(
        {
            "initial": data["runs"]["initial"],
            "final_w03": data["runs"]["final_w03"],
            "final_w04": data["runs"]["final_w04"],
            "final_lr1e5": data["runs"]["final_lr1e5"],
        },
        output_dir / "01_line_training_curves.svg",
    )
    graph_pies(data, output_dir / "02_pie_donut_summary.svg")
    graph_metrics_heatmap(data["runs"], output_dir / "03_heatmap_model_macro_f1.svg")
    graph_topic_stacked(data, output_dir / "04_stacked_topic_distribution.svg")
    graph_confusion_grid(conf, output_dir / "05_confusion_matrices_grid.svg")

    conf_dir = output_dir / "confusion_matrices"
    conf_dir.mkdir(exist_ok=True)
    for field in TARGET_COLS:
        mat = conf["matrices"][field]
        render_confusion_matrix(field, mat["labels"], mat["counts"], mat["row_normalized"], conf_dir / f"confusion_{field}.svg")

    readme = [
        "# Advanced process charts",
        "",
        "Содержит линейные графики обучения, pie/donut, heatmap и реальные confusion matrices по gold-test.",
        "",
        "- `01_line_training_curves.svg`",
        "- `02_pie_donut_summary.svg`",
        "- `03_heatmap_model_macro_f1.svg`",
        "- `04_stacked_topic_distribution.svg`",
        "- `05_confusion_matrices_grid.svg`",
        "- `confusion_matrices/confusion_*.svg`",
        "- `confusion_matrices.json`",
    ]
    (output_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8-sig")
    html_lines = [
        "<!doctype html>",
        '<html lang="ru">',
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>ЖКХ advanced charts</title>",
        "  <style>",
        "    body { margin: 0; background: #081316; color: #f5fbfc; font-family: Segoe UI, Arial, sans-serif; }",
        "    main { max-width: 1680px; margin: 0 auto; padding: 32px; }",
        "    h1 { margin: 0 0 8px; font-size: 34px; }",
        "    p { color: #a7c2c8; font-size: 18px; }",
        "    section { margin: 34px 0; padding: 20px; border: 1px solid #315b66; border-radius: 16px; background: #11252b; }",
        "    h2 { margin: 0 0 16px; font-size: 22px; }",
        "    img { display: block; width: 100%; height: auto; border-radius: 10px; background: #081316; }",
        "    code { color: #ffd166; }",
        "  </style>",
        "</head>",
        "<body><main>",
        "  <h1>ЖКХ advanced charts</h1>",
        "  <p>Линии обучения, pie/donut, heatmap и реальные confusion matrices по human-gold test.</p>",
    ]
    for name in [
        "01_line_training_curves.svg",
        "02_pie_donut_summary.svg",
        "03_heatmap_model_macro_f1.svg",
        "04_stacked_topic_distribution.svg",
        "05_confusion_matrices_grid.svg",
    ]:
        html_lines.extend(
            [
                "  <section>",
                f"    <h2><code>{name}</code></h2>",
                f'    <img src="{name}" alt="{name}">',
                "  </section>",
            ]
        )
    for field in TARGET_COLS:
        name = f"confusion_matrices/confusion_{field}.svg"
        html_lines.extend(
            [
                "  <section>",
                f"    <h2><code>{name}</code></h2>",
                f'    <img src="{name}" alt="{name}">',
                "  </section>",
            ]
        )
    html_lines.extend(["</main></body>", "</html>"])
    (output_dir / "index.html").write_text("\n".join(html_lines) + "\n", encoding="utf-8-sig")
    summary = {
        "best_model_dir": args.best_run_dir,
        "test_rows": conf["rows"],
        "device": conf["device"],
        "output_dir": str(output_dir),
    }
    (output_dir / "advanced_charts_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.desktop_copy:
        desktop = Path.home() / "Desktop" / "ЖКХ_исправленные_матрицы_ошибок_2026-06-03"
        if desktop.exists() and args.clean_desktop_copy:
            shutil.rmtree(desktop)
        desktop.mkdir(parents=True, exist_ok=True)
        for path in output_dir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(output_dir)
                target = desktop / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        print(f"desktop={desktop}")
    print(f"output={output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", default="data/exports/teacher_student_full_export_2026-06-03_01-06")
    parser.add_argument("--runs-dir", default="data/ml_experiments/teacher_student_runs")
    parser.add_argument("--best-run-dir", default="data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4")
    parser.add_argument("--output-dir", default="data/exports/project_advanced_charts_2026-06-03")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--desktop-copy", action="store_true")
    parser.add_argument("--clean-desktop-copy", action="store_true")
    parser.add_argument("--force-eval", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_all(args)


if __name__ == "__main__":
    main()
