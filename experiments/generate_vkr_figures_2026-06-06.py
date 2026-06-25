from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns


OUT_DIR = Path("data/exports/vkr_figures_2026-06-06")
PNG_DPI = 240


sns.set_theme(
    context="talk",
    style="whitegrid",
    palette="deep",
    font="DejaVu Sans",
)

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.edgecolor": "#1f2937",
        "axes.labelcolor": "#111827",
        "xtick.color": "#111827",
        "ytick.color": "#111827",
        "text.color": "#111827",
        "axes.titleweight": "bold",
        "axes.titlesize": 20,
        "axes.labelsize": 15,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "legend.fontsize": 12,
        "svg.fonttype": "none",
    }
)


def wrap_label(label: str, width: int = 18) -> str:
    return "\n".join(wrap(label, width=width, break_long_words=False))


def format_int(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ")


def format_float(value: float) -> str:
    return f"{value:.4f}"


def save_figure(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{name}.png"
    svg = OUT_DIR / f"{name}.svg"
    fig.tight_layout()
    fig.savefig(png, dpi=PNG_DPI, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def annotate_vertical(ax, values, *, fmt="int", y_offset=0.01) -> None:
    max_value = max(values) if values else 0
    for patch, value in zip(ax.patches, values):
        label = format_int(value) if fmt == "int" else format_float(value)
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            patch.get_height() + max_value * y_offset,
            label,
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )


def annotate_horizontal(ax, values, *, fmt="int", x_offset=0.01) -> None:
    max_value = max(values) if values else 0
    for patch, value in zip(ax.patches, values):
        label = format_int(value) if fmt == "int" else format_float(value)
        ax.text(
            patch.get_width() + max_value * x_offset,
            patch.get_y() + patch.get_height() / 2,
            label,
            ha="left",
            va="center",
            fontsize=11,
            fontweight="bold",
        )


def bar_chart(
    name: str,
    title: str,
    categories: list[str],
    values: list[float],
    *,
    ylabel: str,
    xlabel: str = "",
    value_fmt: str = "int",
    color: str = "#2563eb",
    rotate: int = 0,
) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    sns.barplot(x=categories, y=values, ax=ax, color=color)
    ax.set_title(title, pad=18)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels([wrap_label(c, 16) for c in categories], rotation=rotate, ha="center")
    ax.margins(y=0.16)
    annotate_vertical(ax, values, fmt=value_fmt)
    sns.despine(ax=ax)
    save_figure(fig, name)


def horizontal_bar_chart(
    name: str,
    title: str,
    categories: list[str],
    values: list[float],
    *,
    xlabel: str,
    ylabel: str = "",
    value_fmt: str = "int",
    color: str = "#2563eb",
    sort_desc: bool = True,
) -> None:
    pairs = list(zip(categories, values))
    pairs.sort(key=lambda item: item[1], reverse=sort_desc)
    categories, values = [p[0] for p in pairs], [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=(16, 9))
    sns.barplot(x=values, y=[wrap_label(c, 34) for c in categories], ax=ax, color=color)
    ax.set_title(title, pad=18)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.margins(x=0.18)
    annotate_horizontal(ax, values, fmt=value_fmt)
    sns.despine(ax=ax)
    save_figure(fig, name)


def grouped_bar_chart(
    name: str,
    title: str,
    groups: list[str],
    series: dict[str, list[float]],
    *,
    ylabel: str,
    value_fmt: str = "float",
) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    width = 0.24
    x_positions = list(range(len(groups)))
    colors = sns.color_palette("deep", n_colors=len(series))

    for idx, (label, values) in enumerate(series.items()):
        offsets = [x + (idx - (len(series) - 1) / 2) * width for x in x_positions]
        bars = ax.bar(offsets, values, width=width, label=label, color=colors[idx])
        for bar, value in zip(bars, values):
            if value_fmt == "int":
                shown_value = format_int(value)
            elif value_fmt == "one_decimal":
                shown_value = f"{value:.1f}"
            elif value_fmt == "two_decimal":
                shown_value = f"{value:.2f}"
            else:
                shown_value = format_float(value)
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(max(v) for v in series.values()) * 0.02,
                shown_value,
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                rotation=0,
            )

    ax.set_title(title, pad=18)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    ax.set_xticks(x_positions)
    ax.set_xticklabels([wrap_label(g, 18) for g in groups])
    max_value = max(max(v) for v in series.values())
    ax.set_ylim(0, 1.08 if max_value <= 1 else max_value * 1.22)
    ax.legend(loc="upper left", frameon=True)
    sns.despine(ax=ax)
    save_figure(fig, name)


def line_chart(
    name: str,
    title: str,
    x_values: list[float],
    y_values: list[float],
    *,
    xlabel: str,
    ylabel: str,
    note: str | None = None,
) -> None:
    pairs = sorted(zip(x_values, y_values), reverse=True)
    x_values = [p[0] for p in pairs]
    y_values = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.plot(x_values, y_values, marker="o", linewidth=3, color="#2563eb")
    for x, y in zip(x_values, y_values):
        ax.text(x, y + 0.0025, f"{y:.4f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_title(title, pad=18)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xlim(min(x_values) - 0.04, max(x_values) + 0.04)
    ax.set_ylim(min(y_values) - 0.01, max(y_values) + 0.02)
    if note:
        ax.text(
            0.02,
            0.04,
            note,
            transform=ax.transAxes,
            fontsize=12,
            bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#9ca3af"},
        )
    sns.despine(ax=ax)
    save_figure(fig, name)


def generate_all() -> None:
    # G1
    bar_chart(
        "G1_corpus_structure",
        "Структура корпуса данных",
        [
            "Всего строк в объединенном корпусе",
            "Посты и wallpost",
            "Комментарии",
            "Комментарии с контекстом поста",
            "Рабочая очередь разметки",
        ],
        [413670, 144204, 269466, 265130, 265181],
        ylabel="Количество записей",
        color="#2563eb",
    )

    # G2
    bar_chart(
        "G2_production_annotation_results",
        "Итоги производственной разметки (основной срез для ВКР)",
        ["Отправлено", "Принято в датасет", "Удаленные посты", "Отклонено"],
        [6219, 4704, 749, 766],
        ylabel="Количество разметок",
        color="#0f766e",
    )

    # G3
    bar_chart(
        "G3_jkh_relevance_imbalance",
        "Дисбаланс классов по признаку ЖКХ-релевантности",
        ["Не ЖКХ", "ЖКХ", "Не уверен(а)"],
        [4073, 351, 18],
        ylabel="Количество записей",
        color="#dc2626",
    )

    # G4
    horizontal_bar_chart(
        "G4_jkh_topic_distribution",
        "Распределение основных ЖКХ-тем в silver-слое",
        [
            "Мусор и уборка",
            "Двор и придомовая территория",
            "Общее имущество МКД",
            "Холодная вода и канализация",
            "Органы власти",
            "Отопление и горячая вода",
            "Платежи и тарифы",
            "Прочее ЖКХ",
        ],
        [26637, 23354, 5254, 5043, 4938, 4695, 4679, 1071],
        xlabel="Количество записей",
        color="#2563eb",
    )

    # G5
    horizontal_bar_chart(
        "G5_rare_human_gold_classes",
        "Редкие классы в human-gold train",
        [
            "jkh_topic.house_common_property",
            "jkh_topic.management_company",
            "jkh_topic.payments_tariffs",
            "authority_aspect.tariff_policy",
            "authority_aspect.supervision",
            "authority_aspect.positive_feedback",
            "responsible_party.housing_inspection",
            "responsible_party.specific_person",
            "responsible_party.residents",
            "appeal_type.demand",
            "quality.duplicate",
        ],
        [4, 9, 10, 8, 11, 14, 9, 12, 13, 34, 3],
        xlabel="Количество примеров в gold train",
        color="#7c3aed",
        sort_desc=False,
    )

    # G6
    bar_chart(
        "G6_original_taxonomy_macro_f1_by_head",
        "Macro-F1 по осям исходной таксономии после правил согласованности",
        [
            "jkh_relevance",
            "jkh_topic",
            "authority_aspect",
            "sentiment",
            "appeal_type",
            "responsible_party",
            "sarcasm",
            "quality",
        ],
        [0.4475, 0.3106, 0.2128, 0.3710, 0.2519, 0.1495, 0.3214, 0.3612],
        ylabel="Macro-F1",
        value_fmt="float",
        color="#0f766e",
    )

    # G7
    bar_chart(
        "G7_key_ml_approaches",
        "Сравнение ключевых ML-подходов",
        [
            "Базовая tiny2",
            "Каскад original",
            "Большой RuBERT",
            "Укрупненная базовая",
            "Укрупненная с весами",
        ],
        [0.3003, 0.3032, 0.2920, 0.3544, 0.3561],
        ylabel="Средний test macro-F1",
        value_fmt="float",
        color="#2563eb",
    )

    # G8
    line_chart(
        "G8_selective_taxonomy_quality_coverage",
        "Выборочная таксономия: качество и покрытие",
        [0.8706, 0.7689, 0.7141, 0.6926, 0.6668, 0.6668, 0.5076],
        [0.3083, 0.3126, 0.3220, 0.3261, 0.3284, 0.3284, 0.3363],
        xlabel="Среднее test-покрытие",
        ylabel="Средний test macro-F1",
        note="Рост качества достигается ценой снижения покрытия.",
    )

    # G9
    bar_chart(
        "G9_omsu_impact_distribution",
        "Распределение классов влияния на оценку ОМСУ",
        ["Нейтрально/нет влияния", "Сильно негативно", "Негативно", "Позитивно"],
        [236340, 13734, 10122, 3897],
        ylabel="Количество записей",
        color="#dc2626",
    )

    # G10
    grouped_bar_chart(
        "G10_omsu_classifier_results",
        "Результаты OMSU-классификатора",
        ["Максимальная вероятность", "Порог 0.69", "Выборочная политика"],
        {
            "Macro-F1": [0.7321, 0.7635, 0.9102],
            "Weighted-F1": [0.9083, 0.9302, 0.9937],
            "F1 негативного класса": [0.5263, 0.5690, 0.8235],
        },
        ylabel="Значение метрики",
    )

    # G11a
    grouped_bar_chart(
        "G11a_load_test_requests_per_second",
        "Нагрузочное тестирование: запросов в секунду",
        ["Конкурентность 200", "Конкурентность 300", "Конкурентность 400"],
        {
            "2 worker-процесса": [644.25, 644.05, 644.74],
            "4 worker-процесса": [1061.30, 1064.77, 1064.46],
        },
        ylabel="Запросов в секунду",
        value_fmt="two_decimal",
    )

    # G11b
    grouped_bar_chart(
        "G11b_load_test_average_latency",
        "Нагрузочное тестирование: средняя задержка",
        ["Конкурентность 200", "Конкурентность 300", "Конкурентность 400"],
        {
            "2 worker-процесса": [310.437, 465.806, 620.405],
            "4 worker-процесса": [188.449, 281.752, 375.778],
        },
        ylabel="Средняя задержка, мс",
        value_fmt="two_decimal",
    )

    # G12
    bar_chart(
        "G12_economic_cost_comparison",
        "Оценочное сравнение годовых затрат",
        ["Ручной мониторинг", "Система, первый год", "Система, со второго года"],
        [2673600, 2093100, 1143100],
        ylabel="Затраты, руб.",
        color="#7c3aed",
    )

    # G13
    bar_chart(
        "G13_teacher_student_dataset_structure",
        "Структура обучающего набора teacher-student",
        ["Human-gold всего", "Silver train", "Pseudo-gold train"],
        [4365, 259728, 7134],
        ylabel="Количество строк",
        color="#0f766e",
    )

    # G14
    bar_chart(
        "G14_weight_experiments_comparison",
        "Базовая модель и эксперименты с весами",
        [
            "Базовая модель",
            "Без весов выборки",
            "Индивидуальные веса authority",
            "Original weights p075 cap4",
        ],
        [0.3003, 0.2962, 0.3000, 0.2956],
        ylabel="Средний test macro-F1",
        value_fmt="float",
        color="#dc2626",
    )


if __name__ == "__main__":
    generate_all()
    print(f"Графики сохранены в {OUT_DIR.resolve()}")
