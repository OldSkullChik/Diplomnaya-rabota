#!/usr/bin/env python
"""Render binary agreement matrices for full-corpus model predictions.

The source prediction CSV already contains true_* and pred_* columns for every
taxonomy head. This script collapses each head into a binary outcome:
"matched" when the predicted label equals the reference label, otherwise
"not_matched". It also reports a strict all-heads exact-match outcome.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


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

METRICS = [*HEADS, "all_heads_exact_match"]

METRIC_TITLES = {
    "jkh_relevance": "ЖКХ-релевантность",
    "jkh_topic": "Тема ЖКХ",
    "authority_aspect": "Аспект власти",
    "sentiment": "Тональность",
    "appeal_type": "Тип обращения",
    "responsible_party": "Ответственная сторона",
    "sarcasm": "Сарказм",
    "quality": "Качество",
    "all_heads_exact_match": "Все 8 осей одновременно",
}

GROUP_ORDER = [
    ("all", "01_all_265181", "Весь корпус"),
    ("gold_raw", "02_gold_raw_5953", "Gold / ручная проверка"),
    ("silver_auto", "03_silver_auto_259228", "Silver / автоматическая разметка"),
]

OUTCOME_TITLES = {
    "matched": "Да, сошлось",
    "not_matched": "Нет, не сошлось",
}


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


def pct(value: int, total: int) -> float:
    return value / total if total else 0.0


def read_predictions(path: Path) -> tuple[
    dict[str, Counter[str]],
    dict[str, int],
    list[dict[str, str]],
]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    group_rows: Counter[str] = Counter()
    binary_rows: list[dict[str, str]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label_source = row["label_source"]
            groups = ["all", label_source]
            matches: dict[str, bool] = {}
            for head in HEADS:
                matches[head] = row.get(f"true_{head}", "") == row.get(f"pred_{head}", "")
            matches["all_heads_exact_match"] = all(matches[head] for head in HEADS)

            for group in groups:
                group_rows[group] += 1
                for metric, is_match in matches.items():
                    counters[f"{group}:{metric}"]["matched" if is_match else "not_matched"] += 1

            binary_rows.append(
                {
                    "row_id": row["row_id"],
                    "label_source": label_source,
                    "record_id": row["record_id"],
                    **{
                        f"match_{metric}": "yes" if is_match else "no"
                        for metric, is_match in matches.items()
                    },
                }
            )

    return counters, dict(group_rows), binary_rows


def write_binary_rows(output: Path, rows: list[dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "row_id",
        "label_source",
        "record_id",
        *[f"match_{metric}" for metric in METRICS],
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_matrix_csv(output: Path, group: str, metric: str, counts: Counter[str]) -> None:
    matched = int(counts["matched"])
    not_matched = int(counts["not_matched"])
    total = matched + not_matched
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["group", group])
        writer.writerow(["metric", metric])
        writer.writerow(["metric_title", METRIC_TITLES[metric]])
        writer.writerow(["total", total])
        writer.writerow([])
        writer.writerow(["outcome", "count", "share"])
        writer.writerow([OUTCOME_TITLES["matched"], matched, f"{pct(matched, total):.6f}"])
        writer.writerow([OUTCOME_TITLES["not_matched"], not_matched, f"{pct(not_matched, total):.6f}"])
        writer.writerow([])
        writer.writerow(["matrix", OUTCOME_TITLES["matched"], OUTCOME_TITLES["not_matched"], "row_total"])
        writer.writerow(["Проверенные пары", matched, not_matched, total])


def plot_matrix(
    output_png: Path,
    output_svg: Path,
    group_title: str,
    metric: str,
    counts: Counter[str],
    dpi: int,
) -> None:
    matched = int(counts["matched"])
    not_matched = int(counts["not_matched"])
    total = matched + not_matched
    accuracy = pct(matched, total)

    matrix = np.array([[matched, not_matched]], dtype=int)
    fig, ax = plt.subplots(figsize=(10.8, 4.8), dpi=dpi)
    im = ax.imshow(matrix, cmap="YlGnBu")
    cbar = fig.colorbar(im, ax=ax, fraction=0.036, pad=0.04)
    cbar.set_label("Количество записей", fontsize=10)

    ax.set_xticks([0, 1], [OUTCOME_TITLES["matched"], OUTCOME_TITLES["not_matched"]])
    ax.set_yticks([0], ["Проверенные пары"])
    ax.tick_params(axis="x", labelsize=12)
    ax.tick_params(axis="y", labelsize=12)

    max_value = int(matrix.max()) if matrix.size else 0
    for col, value in enumerate(matrix[0]):
        text_color = "white" if max_value and value > max_value * 0.55 else "#111827"
        share = pct(int(value), total)
        ax.text(
            col,
            0,
            f"{int(value):,}".replace(",", " ") + f"\n{share:.2%}",
            ha="center",
            va="center",
            fontsize=17,
            fontweight="bold",
            color=text_color,
        )

    ax.set_title(
        f"{group_title}: {METRIC_TITLES[metric]}\n"
        f"Бинарная сходимость: total={total}, сошлось={matched}, не сошлось={not_matched}, accuracy={accuracy:.4f}",
        fontsize=15,
        fontweight="bold",
        pad=16,
    )
    ax.set_xlabel("Итог сравнения эталонной и предсказанной метки", fontsize=12, labelpad=12)
    ax.set_ylabel("")
    ax.set_xticks(np.arange(-0.5, 2, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 1, 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)

    fig.text(
        0.02,
        0.025,
        "Примечание: это не новая классификация модели, а бинарная проверка совпадения true_* и pred_* по выбранной оси.",
        fontsize=9,
        color="#4b5563",
    )
    fig.tight_layout(rect=(0.02, 0.06, 0.98, 0.98))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(output_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_overview(
    output_png: Path,
    output_svg: Path,
    group_title: str,
    group: str,
    counters: dict[str, Counter[str]],
    dpi: int,
) -> None:
    labels = [METRIC_TITLES[metric] for metric in METRICS]
    values = []
    errors = []
    for metric in METRICS:
        counts = counters[f"{group}:{metric}"]
        matched = int(counts["matched"])
        not_matched = int(counts["not_matched"])
        total = matched + not_matched
        values.append(pct(matched, total) * 100)
        errors.append(not_matched)

    fig, ax = plt.subplots(figsize=(13.5, 7.2), dpi=dpi)
    y = np.arange(len(labels))
    colors = ["#1f9d78" if metric != "all_heads_exact_match" else "#c2410c" for metric in METRICS]
    ax.barh(y, values, color=colors, alpha=0.88)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Сходимость, %", fontsize=12)
    ax.set_title(f"{group_title}: бинарная сходимость по всем осям", fontsize=16, fontweight="bold", pad=16)
    ax.grid(axis="x", color="#dbe3e7", linewidth=1)
    ax.set_axisbelow(True)

    for idx, value in enumerate(values):
        ax.text(
            min(value + 1.0, 97.0),
            idx,
            f"{value:.2f}%  | ошибок: {errors[idx]}",
            va="center",
            fontsize=10,
            color="#111827",
        )

    fig.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(output_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_group_index(output_dir: Path, group_title: str, files: list[dict[str, str]]) -> None:
    cards = []
    for item in files:
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(item['title'])}</h2>
              <p><a href="{html.escape(item['csv'])}">CSV</a> · <a href="{html.escape(item['svg'])}">SVG</a></p>
              <img src="{html.escape(item['png'])}" alt="{html.escape(item['title'])}">
            </section>
            """
        )
    page = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{html.escape(group_title)}: бинарные матрицы сходимости</title>
  <style>
    body {{ margin: 0; background: #f4f7f8; color: #111827; font-family: "Segoe UI", Arial, sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; }}
    p {{ color: #4b5563; font-size: 17px; line-height: 1.5; }}
    .card {{ background: white; border: 1px solid #d8e2e5; border-radius: 14px; padding: 22px; margin: 28px 0; box-shadow: 0 10px 26px rgba(16,24,32,.08); }}
    h2 {{ margin: 0 0 8px; font-size: 23px; }}
    img {{ width: 100%; height: auto; border: 1px solid #edf1f3; border-radius: 10px; margin-top: 12px; }}
    a {{ color: #0b6fa4; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(group_title)}: бинарные матрицы сходимости</h1>
  <p>Каждая матрица показывает, сколько записей по выбранной оси сошлось с эталонной меткой и сколько не сошлось.</p>
  {''.join(cards)}
</main>
</body>
</html>
"""
    output_dir.joinpath("index.html").write_text(page, encoding="utf-8")


def build_root_index(output_dir: Path, summary_rows: list[dict[str, Any]]) -> None:
    rows = []
    for item in summary_rows:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['group_title'])}</td>"
            f"<td>{html.escape(item['metric_title'])}</td>"
            f"<td>{item['total']}</td>"
            f"<td>{item['matched']}</td>"
            f"<td>{item['not_matched']}</td>"
            f"<td>{item['accuracy']:.4f}</td>"
            "</tr>"
        )
    page = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Бинарные матрицы сходимости, 265181 строка</title>
  <style>
    body {{ margin: 0; background: #f4f7f8; color: #111827; font-family: "Segoe UI", Arial, sans-serif; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; }}
    p, li {{ color: #4b5563; font-size: 16px; line-height: 1.5; }}
    .note {{ background: white; border-left: 5px solid #0b6fa4; border-radius: 10px; padding: 16px 18px; margin: 20px 0 26px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 26px rgba(16,24,32,.08); }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5edf0; text-align: left; }}
    th {{ background: #eaf3f6; }}
    a {{ color: #0b6fa4; }}
  </style>
</head>
<body>
<main>
  <h1>Бинарные матрицы сходимости по всем метрикам</h1>
  <div class="note">
    <p>Это свертка исходных матриц ошибок: для каждой оси проверяется, совпала ли предсказанная метка с эталонной. Значения в матрицах - абсолютные числа.</p>
    <p>Разрезы: <a href="01_all_265181/index.html">весь корпус</a>, <a href="02_gold_raw_5953/index.html">gold</a>, <a href="03_silver_auto_259228/index.html">silver</a>.</p>
  </div>
  <table>
    <thead>
      <tr><th>Разрез</th><th>Метрика</th><th>Всего</th><th>Сошлось</th><th>Не сошлось</th><th>Доля сходимости</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</main>
</body>
</html>
"""
    output_dir.joinpath("index.html").write_text(page, encoding="utf-8")


def write_summary_csv(output: Path, rows: list[dict[str, Any]]) -> None:
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "group",
                "group_title",
                "metric",
                "metric_title",
                "total",
                "matched",
                "not_matched",
                "accuracy",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def render(args: argparse.Namespace) -> None:
    predictions_csv = Path(args.predictions_csv)
    output_dir = Path(args.output_dir)
    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    counters, group_rows, binary_rows = read_predictions(predictions_csv)
    write_binary_rows(output_dir / "binary_agreement_by_row.csv", binary_rows)

    summary_rows: list[dict[str, Any]] = []
    for group, folder, group_title in GROUP_ORDER:
        group_dir = output_dir / folder
        group_dir.mkdir(parents=True, exist_ok=True)
        files = []
        plot_overview(
            group_dir / "00_binary_agreement_overview.png",
            group_dir / "00_binary_agreement_overview.svg",
            group_title,
            group,
            counters,
            args.dpi,
        )
        files.append(
            {
                "title": "Обзор сходимости по всем осям",
                "csv": "../binary_agreement_summary.csv",
                "png": "00_binary_agreement_overview.png",
                "svg": "00_binary_agreement_overview.svg",
            }
        )

        for idx, metric in enumerate(METRICS, 1):
            counts = counters[f"{group}:{metric}"]
            matched = int(counts["matched"])
            not_matched = int(counts["not_matched"])
            total = matched + not_matched
            if total != group_rows.get(group, 0):
                raise RuntimeError(f"Bad total for {group}:{metric}: {total} != {group_rows.get(group, 0)}")

            stem = f"{idx:02d}_{safe_name(metric)}_binary_agreement"
            write_matrix_csv(group_dir / f"{stem}.csv", group, metric, counts)
            plot_matrix(
                group_dir / f"{stem}.png",
                group_dir / f"{stem}.svg",
                group_title,
                metric,
                counts,
                args.dpi,
            )
            files.append(
                {
                    "title": METRIC_TITLES[metric],
                    "csv": f"{stem}.csv",
                    "png": f"{stem}.png",
                    "svg": f"{stem}.svg",
                }
            )
            summary_rows.append(
                {
                    "group": group,
                    "group_title": group_title,
                    "metric": metric,
                    "metric_title": METRIC_TITLES[metric],
                    "total": total,
                    "matched": matched,
                    "not_matched": not_matched,
                    "accuracy": pct(matched, total),
                }
            )

        group_manifest = {
            "group": group,
            "group_title": group_title,
            "rows": group_rows.get(group, 0),
            "files": files,
        }
        group_dir.joinpath("manifest.json").write_text(
            json.dumps(group_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        build_group_index(group_dir, group_title, files)

    write_summary_csv(output_dir / "binary_agreement_summary.csv", summary_rows)
    output_dir.joinpath("binary_agreement_summary.json").write_text(
        json.dumps(
            {
                "source_predictions_csv": str(predictions_csv),
                "groups": group_rows,
                "rows": summary_rows,
                "note": (
                    "Binary agreement checks whether true_* equals pred_* for each metric. "
                    "All/silver groups use automatic silver labels as reference; gold_raw uses the production approved slice."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    build_root_index(output_dir, summary_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions_csv")
    parser.add_argument("output_dir")
    parser.add_argument("--dpi", type=int, default=170)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    render(parse_args())
