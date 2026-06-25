#!/usr/bin/env python
"""Render absolute-count confusion matrices with Matplotlib."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm


HEADS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]

HEAD_TITLES = {
    "jkh_relevance": "ЖКХ-релевантность",
    "jkh_topic": "Тема ЖКХ",
    "authority_aspect": "Аспект власти",
    "sentiment": "Тональность",
    "appeal_type": "Тип обращения",
    "responsible_party": "Ответственная сторона",
    "sarcasm": "Сарказм",
    "quality": "Качество",
}

LABELS_RU = {
    "cold_water_sewerage": "ХВС/канализация",
    "heating_hot_water": "Отопление/ГВС",
    "house_common_property": "МКД/общедомовое",
    "management_company": "УК/ТСЖ",
    "not_jkh": "Не ЖКХ",
    "other_jkh": "Другое ЖКХ",
    "payments_tariffs": "Платежи/тарифы",
    "public_authorities": "Органы власти",
    "waste_cleaning": "Мусор/уборка",
    "yard_area": "Двор/территория",
    "communication": "Коммуникация",
    "no_action": "Бездействие",
    "not_applicable": "Не применимо",
    "other": "Другое",
    "poor_quality": "Плохое качество",
    "positive_feedback": "Позитивная оценка",
    "slow_response": "Медленная реакция",
    "supervision": "Надзор",
    "tariff_policy": "Тарифная политика",
    "local_administration": "Администрация",
    "housing_inspection": "ГЖИ",
    "resource_provider": "РСО",
    "specific_person": "Должностное лицо",
    "waste_operator": "Оператор ТКО",
    "residents": "Жители",
    "unknown": "Неясно",
    "complaint": "Жалоба",
    "demand": "Требование",
    "gratitude": "Благодарность",
    "info": "Информация",
    "opinion": "Мнение",
    "question": "Вопрос",
    "request": "Просьба",
    "suggestion": "Предложение",
    "mixed": "Смешанная",
    "negative": "Негативная",
    "neutral": "Нейтральная",
    "positive": "Позитивная",
    "difficult": "Сложный случай",
    "duplicate": "Дубль",
    "normal": "Нормальный",
    "spam": "Спам",
    "no": "Нет",
    "unsure": "Не уверено",
    "yes": "Да",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


def labels_ru(labels: list[str]) -> list[str]:
    return [LABELS_RU.get(label, label) for label in labels]


def write_matrix_csv(output: Path, field: str, labels: list[str], matrix: np.ndarray) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["true\\pred", *labels_ru(labels), "row_total"])
        for label, row in zip(labels, matrix):
            writer.writerow([LABELS_RU.get(label, label), *[int(v) for v in row], int(row.sum())])
        writer.writerow(["column_total", *[int(v) for v in matrix.sum(axis=0)], int(matrix.sum())])


def plot_matrix(field: str, labels: list[str], matrix: np.ndarray, output_png: Path, output_svg: Path, dpi: int) -> None:
    n = len(labels)
    width = max(10.5, 1.15 * n + 5.8)
    height = max(9.0, 1.05 * n + 5.2)
    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)

    positive = matrix[matrix > 0]
    if len(positive):
        norm = LogNorm(vmin=max(1, int(positive.min())), vmax=max(1, int(positive.max())))
    else:
        norm = None

    im = ax.imshow(matrix, cmap="YlGnBu", norm=norm)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Количество записей (цветовая шкала логарифмическая)", fontsize=11)

    ru = labels_ru(labels)
    ax.set_xticks(np.arange(n), labels=ru)
    ax.set_yticks(np.arange(n), labels=ru)
    ax.tick_params(axis="x", labelrotation=45, labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    for tick in ax.get_xticklabels():
        tick.set_horizontalalignment("right")
        tick.set_rotation_mode("anchor")

    max_count = int(matrix.max()) if matrix.size else 0
    threshold = max_count * 0.48
    for i in range(n):
        for j in range(n):
            value = int(matrix[i, j])
            text_color = "white" if value > threshold and value > 0 else "#101820"
            alpha = 0.45 if value == 0 else 1.0
            ax.text(j, i, str(value), ha="center", va="center", color=text_color, fontsize=9, alpha=alpha)

    row_totals = matrix.sum(axis=1)
    col_totals = matrix.sum(axis=0)
    total = int(matrix.sum())
    correct = int(np.trace(matrix))
    accuracy = correct / total if total else 0.0

    ax.set_title(
        f"Матрица ошибок: {HEAD_TITLES[field]}\n"
        f"Абсолютные числа, test={total}, верно={correct}, accuracy={accuracy:.3f}",
        fontsize=15,
        fontweight="bold",
        pad=18,
    )
    ax.set_xlabel("Предсказанный класс", fontsize=12, labelpad=14)
    ax.set_ylabel("Истинный класс", fontsize=12, labelpad=14)

    ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.25)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Add totals outside the matrix without changing the confusion data itself.
    for i, value in enumerate(row_totals):
        ax.text(n + 0.12, i, f"Σ {int(value)}", va="center", ha="left", fontsize=9, color="#303030")
    for j, value in enumerate(col_totals):
        ax.text(j, n + 0.16, f"Σ {int(value)}", va="top", ha="center", fontsize=9, color="#303030", rotation=90)
    ax.set_xlim(-0.5, n + 1.25)
    ax.set_ylim(n + 1.10, -0.5)

    fig.text(
        0.012,
        0.012,
        "Примечание: числа в ячейках - реальные counts; цвет логарифмический, чтобы были видны редкие ошибки.",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout(rect=(0.02, 0.04, 0.98, 0.96))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(output_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_index(output_dir: Path, rows: int, files: list[dict[str, str]]) -> None:
    cards = []
    for item in files:
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(item['title'])}</h2>
              <p><a href="{html.escape(item['csv'])}">CSV с абсолютными числами</a> · <a href="{html.escape(item['svg'])}">SVG</a></p>
              <img src="{html.escape(item['png'])}" alt="{html.escape(item['title'])}">
            </section>
            """
        )
    page = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Матрицы ошибок counts</title>
  <style>
    body {{
      margin: 0;
      background: #f4f7f8;
      color: #101820;
      font-family: "Segoe UI", Arial, sans-serif;
    }}
    main {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 32px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
    }}
    p {{
      color: #4a5a60;
      font-size: 17px;
      line-height: 1.55;
    }}
    .note {{
      padding: 16px 18px;
      border-left: 5px solid #1976a3;
      background: #ffffff;
      border-radius: 10px;
      margin: 22px 0 30px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #d8e2e5;
      border-radius: 14px;
      padding: 22px;
      margin: 28px 0;
      box-shadow: 0 10px 26px rgba(16, 24, 32, 0.08);
    }}
    h2 {{
      margin: 0 0 10px;
      font-size: 24px;
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid #edf1f3;
      border-radius: 10px;
      margin-top: 12px;
    }}
    a {{ color: #0b6fa4; }}
    code {{
      background: #edf3f5;
      padding: 2px 6px;
      border-radius: 5px;
    }}
  </style>
</head>
<body>
<main>
  <h1>Матрицы ошибок по осям классификации</h1>
  <p>Источник: human-gold test, <code>{rows}</code> записей. В ячейках указаны абсолютные числа, а не проценты.</p>
  <div class="note">
    Цветовая шкала на изображениях логарифмическая: это сделано только для читаемости, чтобы редкие ошибки не терялись рядом с большими классами.
    Числа внутри ячеек остаются точными count-значениями.
  </div>
  {''.join(cards)}
</main>
</body>
</html>
"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")


def render(args: argparse.Namespace) -> None:
    source = Path(args.source)
    output_dir = Path(args.output_dir)
    desktop_dir = Path.home() / "Desktop" / args.desktop_folder
    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = read_json(source)
    rows = int(data["rows"])
    files = []
    for order, field in enumerate(HEADS, 1):
        matrix_data = data["matrices"][field]
        labels = matrix_data["labels"]
        matrix = np.array(matrix_data["counts"], dtype=int)
        stem = f"{order:02d}_{safe_name(field)}_counts"
        png = f"{stem}.png"
        svg = f"{stem}.svg"
        csv_name = f"{stem}.csv"
        plot_matrix(
            field,
            labels,
            matrix,
            output_dir / png,
            output_dir / svg,
            args.dpi,
        )
        write_matrix_csv(output_dir / csv_name, field, labels, matrix)
        files.append({"title": HEAD_TITLES[field], "png": png, "svg": svg, "csv": csv_name})

    manifest = {
        "source": str(source),
        "rows": rows,
        "kind": "absolute_count_confusion_matrices",
        "note": "Cell annotations are raw counts. Color uses logarithmic normalization for readability.",
        "files": files,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    build_index(output_dir, rows, files)

    if args.desktop_copy:
        if desktop_dir.exists() and args.clean_desktop:
            shutil.rmtree(desktop_dir)
        desktop_dir.mkdir(parents=True, exist_ok=True)
        for path in output_dir.rglob("*"):
            if path.is_file():
                target = desktop_dir / path.relative_to(output_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    print(f"output={output_dir.resolve()}")
    if args.desktop_copy:
        print(f"desktop={desktop_dir}")
    print(f"matrices={len(files)} rows={rows}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/exports/project_advanced_charts_2026-06-03/confusion_matrices.json")
    parser.add_argument("--output-dir", default="data/exports/confusion_counts_matplotlib_2026-06-03")
    parser.add_argument("--desktop-folder", default="ЖКХ_матрицы_ошибок_абсолютные_числа_2026-06-03")
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--desktop-copy", action="store_true")
    parser.add_argument("--clean-desktop", action="store_true")
    return parser.parse_args()


def main() -> None:
    render(parse_args())


if __name__ == "__main__":
    main()
