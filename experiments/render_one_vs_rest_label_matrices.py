#!/usr/bin/env python
"""Render one-vs-rest confusion matrices for every label in every taxonomy head.

For each head/label pair this script builds a classic 2x2 matrix:

    true label     vs predicted label     -> TP
    true label     vs predicted other     -> FN
    true other     vs predicted label     -> FP
    true other     vs predicted other     -> TN

The input is the full prediction CSV produced by evaluate_full_labeled_confusions.py.
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

HEAD_TITLES = {
    "jkh_relevance": "ЖКХ-релевантность",
    "jkh_topic": "Тема ЖКХ",
    "authority_aspect": "Аспект работы власти/служб",
    "sentiment": "Тональность",
    "appeal_type": "Тип обращения",
    "responsible_party": "Ответственная сторона",
    "sarcasm": "Сарказм",
    "quality": "Качество комментария",
}

LABELS_RU = {
    "__missing__": "Пустое значение",
    "yes": "Да",
    "no": "Нет",
    "unsure": "Не уверено",
    "not_jkh": "Не ЖКХ",
    "cold_water_sewerage": "ХВС/канализация",
    "heating_hot_water": "Отопление/ГВС",
    "house_common_property": "МКД/общедомовое имущество",
    "management_company": "УК/ТСЖ",
    "other_jkh": "Другое ЖКХ",
    "payments_tariffs": "Платежи/тарифы",
    "public_authorities": "Органы власти",
    "waste_cleaning": "Мусор/уборка",
    "yard_area": "Двор/территория",
    "communication": "Коммуникация",
    "no_action": "Бездействие",
    "not_applicable": "Не применимо",
    "other": "Другое",
    "poor_quality": "Плохое качество работы",
    "positive_feedback": "Положительная оценка",
    "slow_response": "Медленная реакция",
    "supervision": "Контроль/надзор",
    "tariff_policy": "Тарифная политика",
    "local_administration": "Администрация",
    "housing_inspection": "Жилищная инспекция",
    "resource_provider": "Ресурсоснабжающая организация",
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
    "no_context": "Нет контекста",
}

GROUPS = [
    ("all", "01_all_265181", "Весь корпус"),
    ("gold_raw", "02_gold_raw_5953", "Gold / ручная проверка"),
    ("silver_auto", "03_silver_auto_259228", "Silver / автоматическая разметка"),
]


def label_ru(label: str) -> str:
    return LABELS_RU.get(label, label)


def safe_name(value: str) -> str:
    return (
        value.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(":", "_")
        .replace(";", "_")
        .replace("|", "_")
    )


def div(num: int, den: int) -> float:
    return num / den if den else 0.0


def read_predictions(path: Path) -> tuple[
    dict[str, dict[str, Counter[tuple[str, str]]]],
    dict[str, int],
    dict[str, set[str]],
]:
    counters: dict[str, dict[str, Counter[tuple[str, str]]]] = defaultdict(lambda: defaultdict(Counter))
    group_rows: Counter[str] = Counter()
    labels_by_head: dict[str, set[str]] = defaultdict(set)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label_source = row["label_source"]
            groups = ["all", label_source]
            for group in groups:
                group_rows[group] += 1
            for head in HEADS:
                true_label = row.get(f"true_{head}", "") or "__missing__"
                pred_label = row.get(f"pred_{head}", "") or "__missing__"
                labels_by_head[head].add(true_label)
                labels_by_head[head].add(pred_label)
                for group in groups:
                    counters[group][head][(true_label, pred_label)] += 1

    return counters, dict(group_rows), labels_by_head


def label_order(labels: set[str]) -> list[str]:
    preferred = list(LABELS_RU.keys())
    ordered = [label for label in preferred if label in labels]
    ordered.extend(sorted(labels - set(ordered)))
    return ordered


def one_vs_rest(counter: Counter[tuple[str, str]], target: str) -> dict[str, int]:
    tp = fp = fn = tn = 0
    for (true_label, pred_label), count in counter.items():
        true_is_target = true_label == target
        pred_is_target = pred_label == target
        if true_is_target and pred_is_target:
            tp += count
        elif true_is_target and not pred_is_target:
            fn += count
        elif not true_is_target and pred_is_target:
            fp += count
        else:
            tn += count
    return {"tp": int(tp), "fn": int(fn), "fp": int(fp), "tn": int(tn)}


def metrics(values: dict[str, int]) -> dict[str, float | int]:
    tp, fn, fp, tn = values["tp"], values["fn"], values["fp"], values["tn"]
    total = tp + fn + fp + tn
    precision = div(tp, tp + fp)
    recall = div(tp, tp + fn)
    f1 = div(2 * precision * recall, precision + recall)
    specificity = div(tn, tn + fp)
    npv = div(tn, tn + fn)
    return {
        "total": total,
        "support": tp + fn,
        "predicted_positive": tp + fp,
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "accuracy": div(tp + tn, total),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
        "npv": npv,
    }


def write_matrix_csv(output: Path, row: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        for key in [
            "group",
            "group_title",
            "head",
            "head_title",
            "label",
            "label_ru",
            "total",
            "support",
            "predicted_positive",
            "accuracy",
            "precision",
            "recall",
            "f1",
            "specificity",
            "npv",
        ]:
            writer.writerow([key, row[key]])
        writer.writerow([])
        writer.writerow(["matrix", "pred: target", "pred: other", "row_total"])
        writer.writerow(["true: target", row["tp"], row["fn"], row["tp"] + row["fn"]])
        writer.writerow(["true: other", row["fp"], row["tn"], row["fp"] + row["tn"]])
        writer.writerow(["column_total", row["tp"] + row["fp"], row["fn"] + row["tn"], row["total"]])


def plot_matrix(
    output_png: Path,
    output_svg: Path,
    group_title: str,
    head_title: str,
    label: str,
    row: dict[str, Any],
    dpi: int,
) -> None:
    matrix = np.array([[row["tp"], row["fn"]], [row["fp"], row["tn"]]], dtype=int)
    fig, ax = plt.subplots(figsize=(11.2, 8.4), dpi=dpi)
    im = ax.imshow(matrix, cmap="YlGnBu")
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label("Количество записей", fontsize=10)

    target = label_ru(label)
    ax.set_xticks([0, 1], [f"Предсказано:\n{target}", "Предсказано:\nдругое"])
    ax.set_yticks([0, 1], [f"Истина:\n{target}", "Истина:\nдругое"])
    ax.tick_params(axis="x", labelsize=11)
    ax.tick_params(axis="y", labelsize=11)

    names = np.array([["TP", "FN"], ["FP", "TN"]])
    max_value = int(matrix.max()) if matrix.size else 0
    for i in range(2):
        for j in range(2):
            value = int(matrix[i, j])
            color = "white" if max_value and value > max_value * 0.55 else "#111827"
            ax.text(
                j,
                i,
                f"{names[i, j]}\n{value:,}".replace(",", " "),
                ha="center",
                va="center",
                fontsize=20,
                fontweight="bold",
                color=color,
            )

    title = (
        f"{group_title}: {head_title}\n"
        f"Класс: {target} | support={row['support']} | precision={row['precision']:.3f} | "
        f"recall={row['recall']:.3f} | F1={row['f1']:.3f}"
    )
    ax.set_title(title, fontsize=14, fontweight="bold", pad=16)
    ax.set_xlabel("Предсказание модели", fontsize=12, labelpad=14)
    ax.set_ylabel("Эталонная разметка", fontsize=12, labelpad=14)
    ax.set_xticks(np.arange(-0.5, 2, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 2, 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)

    fig.text(
        0.02,
        0.02,
        "TP: верно найден класс; FN: класс пропущен; FP: класс предсказан ошибочно; TN: верно не отнесено к классу.",
        fontsize=10,
        color="#4b5563",
    )
    fig.tight_layout(rect=(0.02, 0.05, 0.98, 0.98))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(output_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "group",
        "group_title",
        "head",
        "head_title",
        "label",
        "label_ru",
        "total",
        "support",
        "predicted_positive",
        "tp",
        "fn",
        "fp",
        "tn",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "specificity",
        "npv",
        "csv",
        "png",
        "svg",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_index(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row)

    sections = []
    for group, folder, group_title in GROUPS:
        group_rows = by_group[group]
        sections.append(f"<h2>{html.escape(group_title)}</h2>")
        sections.append(f'<p><a href="{folder}/index.html">Открыть страницу разреза</a></p>')
        sections.append("<table><thead><tr><th>Поле</th><th>Класс</th><th>support</th><th>TP</th><th>FN</th><th>FP</th><th>TN</th><th>precision</th><th>recall</th><th>F1</th><th>PNG</th></tr></thead><tbody>")
        for row in sorted(group_rows, key=lambda r: (r["head"], r["label_ru"])):
            sections.append(
                "<tr>"
                f"<td>{html.escape(row['head_title'])}</td>"
                f"<td>{html.escape(row['label_ru'])}</td>"
                f"<td>{row['support']}</td>"
                f"<td>{row['tp']}</td>"
                f"<td>{row['fn']}</td>"
                f"<td>{row['fp']}</td>"
                f"<td>{row['tn']}</td>"
                f"<td>{row['precision']:.3f}</td>"
                f"<td>{row['recall']:.3f}</td>"
                f"<td>{row['f1']:.3f}</td>"
                f"<td><a href=\"{html.escape(row['png'])}\">PNG</a></td>"
                "</tr>"
            )
        sections.append("</tbody></table>")

    output_dir.joinpath("index.html").write_text(
        html_page("One-vs-rest матрицы по каждому классу", "".join(sections)),
        encoding="utf-8",
    )


def build_group_pages(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    by_group_head: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group_head[(row["group"], row["head"])].append(row)
        by_group[row["group"]].append(row)

    for group, folder, group_title in GROUPS:
        group_dir = output_dir / folder
        group_dir.mkdir(parents=True, exist_ok=True)
        pieces = [f"<p><a href=\"../index.html\">К общему индексу</a></p>"]
        for head in HEADS:
            head_rows = sorted(by_group_head[(group, head)], key=lambda r: r["label_ru"])
            pieces.append(f"<h2>{html.escape(HEAD_TITLES[head])}</h2>")
            for row in head_rows:
                rel_png = Path(row["png"]).relative_to(group_dir).as_posix()
                rel_csv = Path(row["csv"]).relative_to(group_dir).as_posix()
                pieces.append(
                    f"""
                    <section class="card">
                      <h3>{html.escape(row['label_ru'])}</h3>
                      <p>support={row['support']} · TP={row['tp']} · FN={row['fn']} · FP={row['fp']} · TN={row['tn']} · precision={row['precision']:.3f} · recall={row['recall']:.3f} · F1={row['f1']:.3f}</p>
                      <p><a href="{html.escape(rel_csv)}">CSV</a></p>
                      <img src="{html.escape(rel_png)}" alt="{html.escape(row['label_ru'])}">
                    </section>
                    """
                )
        group_dir.joinpath("index.html").write_text(
            html_page(f"{group_title}: one-vs-rest матрицы", "".join(pieces)),
            encoding="utf-8",
        )


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; background: #f4f7f8; color: #111827; font-family: "Segoe UI", Arial, sans-serif; }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 14px; font-size: 34px; }}
    h2 {{ margin-top: 34px; padding-top: 18px; border-top: 2px solid #d8e2e5; }}
    p, li {{ color: #4b5563; font-size: 16px; line-height: 1.5; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin: 18px 0 30px; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #e5edf0; text-align: left; font-size: 14px; }}
    th {{ background: #eaf3f6; position: sticky; top: 0; }}
    .card {{ background: white; border: 1px solid #d8e2e5; border-radius: 14px; padding: 20px; margin: 22px 0; box-shadow: 0 10px 26px rgba(16,24,32,.08); }}
    .card img {{ display: block; width: 100%; max-width: 1250px; height: auto; border: 1px solid #edf1f3; border-radius: 10px; margin-top: 12px; }}
    a {{ color: #0b6fa4; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  <p>Каждая матрица проверяет один конкретный класс против всех остальных классов того же поля.</p>
  {body}
</main>
</body>
</html>
"""


def render(args: argparse.Namespace) -> None:
    predictions_csv = Path(args.predictions_csv)
    output_dir = Path(args.output_dir)
    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    counters, group_rows, labels_by_head = read_predictions(predictions_csv)
    summary_rows: list[dict[str, Any]] = []

    for group, folder, group_title in GROUPS:
        group_dir = output_dir / folder
        for head in HEADS:
            head_dir = group_dir / f"{HEADS.index(head) + 1:02d}_{safe_name(head)}"
            labels = label_order(labels_by_head[head])
            for label in labels:
                values = one_vs_rest(counters[group][head], label)
                row_metrics = metrics(values)
                if int(row_metrics["total"]) != group_rows[group]:
                    raise RuntimeError(
                        f"Bad matrix total for {group}/{head}/{label}: "
                        f"{row_metrics['total']} != {group_rows[group]}"
                    )
                stem = f"{safe_name(label)}_one_vs_rest"
                csv_path = head_dir / f"{stem}.csv"
                png_path = head_dir / f"{stem}.png"
                svg_path = head_dir / f"{stem}.svg"
                row: dict[str, Any] = {
                    "group": group,
                    "group_title": group_title,
                    "head": head,
                    "head_title": HEAD_TITLES[head],
                    "label": label,
                    "label_ru": label_ru(label),
                    **values,
                    **row_metrics,
                    "csv": str(csv_path),
                    "png": str(png_path),
                    "svg": str(svg_path),
                }
                write_matrix_csv(csv_path, row)
                plot_matrix(png_path, svg_path, group_title, HEAD_TITLES[head], label, row, args.dpi)
                summary_rows.append(row)

    write_summary_csv(output_dir / "one_vs_rest_summary.csv", summary_rows)
    output_dir.joinpath("one_vs_rest_summary.json").write_text(
        json.dumps(
            {
                "source_predictions_csv": str(predictions_csv),
                "groups": group_rows,
                "heads": HEADS,
                "labels_by_head": {head: label_order(labels) for head, labels in labels_by_head.items()},
                "matrix_definition": {
                    "tp": "true target, predicted target",
                    "fn": "true target, predicted other",
                    "fp": "true other, predicted target",
                    "tn": "true other, predicted other",
                },
                "note": (
                    "All/silver matrices use automatic silver labels as reference; "
                    "gold_raw uses the production-approved human slice."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    build_group_pages(output_dir, summary_rows)
    build_index(output_dir, summary_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions_csv")
    parser.add_argument("output_dir")
    parser.add_argument("--dpi", type=int, default=165)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    render(parse_args())
