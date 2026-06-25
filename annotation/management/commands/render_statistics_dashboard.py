import json
from html import escape
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


WIDTH = 1800
HEIGHT = 2700
MARGIN = 72
CARD = "#ffffff"
INK = "#102a43"
MUTED = "#52606d"
LINE = "#d9e2ec"
BACKGROUND = "#f5f7fa"
NAVY = "#102a43"
TEAL = "#0f766e"
CYAN = "#0ea5a8"
RED = "#d9485f"
AMBER = "#d97706"
GRAY = "#64748b"
TRACK = "#e5e7eb"


def number(value):
    return f"{value:,}".replace(",", " ")


def percentage(value, total):
    return f"{value / total * 100:.2f}%" if total else "0.00%"


class SvgDashboard:
    def __init__(self):
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BACKGROUND}"/>',
        ]

    def text(self, x, y, text, size=18, color=INK, weight=400, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{escape(str(text))}</text>'
        )

    def rect(self, x, y, w, h, fill=CARD, stroke=None, radius=8):
        stroke_attr = f' stroke="{stroke}"' if stroke else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"{stroke_attr}/>'
        )

    def line(self, x1, y1, x2, y2, color=LINE, width=1):
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'
        )

    def finish(self, path):
        self.parts.append("</svg>")
        path.write_text("\n".join(self.parts), encoding="utf-8")


class Command(BaseCommand):
    help = "Render a large SVG dashboard from annotation_statistics.json."

    def add_arguments(self, parser):
        parser.add_argument("statistics_json")
        parser.add_argument("output_svg")

    def handle(self, *args, **options):
        source = Path(options["statistics_json"])
        target = Path(options["output_svg"])
        if not source.exists():
            raise CommandError(f"File not found: {source}")

        data = json.loads(source.read_text(encoding="utf-8"))
        target.parent.mkdir(parents=True, exist_ok=True)
        self.render(data, target)
        self.stdout.write(self.style.SUCCESS(f"Dashboard written to {target}"))

    def render(self, data, target):
        svg = SvgDashboard()
        totals = data["totals"]
        scores = data["scores"]
        taxonomy = data["approved_dataset_taxonomy"]

        svg.rect(0, 0, WIDTH, 154, fill=NAVY, radius=0)
        svg.text(MARGIN, 62, "Статистика разметки обращений по ЖКХ", 38, "#ffffff", 700)
        svg.text(
            MARGIN,
            104,
            f"Официальный production-срез после завершения проверки: {data['generated_at'].replace('T', ' ')}",
            18,
            "#cbd5e1",
        )

        headline_cards = [
            ("Проверено", totals["annotations_checked"], TEAL),
            ("В обучающем наборе", totals["annotations_approved_dataset"], TEAL),
            ("Удаленные посты", totals["deleted_posts_confirmed"], CYAN),
            ("Отклонено", totals["annotations_rejected_total"], RED),
            ("Ожидает проверки", totals["annotations_pending"], GRAY),
            ("Итоговый баланс", f"{scores['net_points']:+d}", AMBER),
        ]
        card_w = 264
        gap = 18
        y = 184
        for index, (label, value, color) in enumerate(headline_cards):
            x = MARGIN + index * (card_w + gap)
            svg.rect(x, y, card_w, 120, stroke=LINE)
            svg.rect(x, y, 7, 120, fill=color, radius=4)
            svg.text(x + 24, y + 37, label, 15, MUTED, 400)
            display = number(value) if isinstance(value, int) else value
            svg.text(x + 24, y + 87, display, 35, INK, 700)

        self.section_title(svg, 352, "Результат проверки за все время")
        self.outcome_panel(svg, totals, 386)
        self.dataset_panel(svg, totals, taxonomy["jkh_relevance"], 386)

        self.section_title(svg, 692, "Качество процесса и вклад проверяющих")
        self.score_panel(svg, scores, 726)
        self.reviewers_panel(svg, data["reviewers"], 726)
        self.leaderboard_panel(svg, data["participants"][:10], 726)

        self.section_title(svg, 1168, "Распределение 4 442 принятых учебных записей")
        panels = [
            ("Тональность", taxonomy["sentiment"], 118, [TEAL, RED, AMBER, CYAN]),
            ("Тип обращения", taxonomy["appeal_type"], 118, [TEAL, CYAN, AMBER, RED]),
            ("Качество", taxonomy["quality"], 100, [TEAL, AMBER, GRAY, RED]),
            ("Сарказм", taxonomy["sarcasm"], 100, [TEAL, RED, AMBER]),
            ("Тема ЖКХ", taxonomy["jkh_topic"], 106, [TEAL, CYAN, AMBER, RED]),
            ("Аспект работы власти", taxonomy["authority_aspect"], 106, [TEAL, CYAN, AMBER, RED]),
            ("Ответственная сторона", taxonomy["responsible_party"], 106, [TEAL, CYAN, AMBER, RED]),
        ]
        positions = [
            (MARGIN, 1202, 535, 315),
            (632, 1202, 535, 315),
            (1192, 1202, 535, 315),
            (MARGIN, 1540, 535, 295),
            (632, 1540, 535, 430),
            (1192, 1540, 535, 430),
            (MARGIN, 1860, 535, 430),
        ]
        for (title, rows, bar_width, colors), (x, panel_y, w, h) in zip(panels, positions):
            self.taxonomy_panel(svg, title, rows, x, panel_y, w, h, bar_width, colors)

        self.insight_panel(svg, taxonomy["jkh_relevance"], 632, 2000, 1095, 290)
        self.footer(svg, totals, data, 2360)
        svg.finish(target)

    def section_title(self, svg, y, title):
        svg.text(MARGIN, y, title, 23, INK, 700)
        svg.line(MARGIN, y + 17, WIDTH - MARGIN, y + 17, LINE)

    def outcome_panel(self, svg, totals, y):
        x, w, h = MARGIN, 520, 258
        svg.rect(x, y, w, h, stroke=LINE)
        svg.text(x + 24, y + 34, "Статусы итоговой проверки", 18, INK, 700)
        checked = totals["annotations_checked"]
        rows = [
            ("В датасет", totals["annotations_approved_dataset"], TEAL),
            ("Пост удален", totals["deleted_posts_confirmed"], CYAN),
            ("Отклонено", totals["annotations_rejected_total"], RED),
        ]
        current_y = y + 70
        for label, value, color in rows:
            svg.text(x + 24, current_y + 17, label, 15, MUTED)
            svg.rect(x + 152, current_y, 232, 22, TRACK, radius=4)
            svg.rect(x + 152, current_y, max(2, value / checked * 232), 22, color, radius=4)
            svg.text(x + 404, current_y + 17, f"{number(value)}  {percentage(value, checked)}", 15, INK, 700)
            current_y += 45
        svg.text(x + 24, y + 229, "Все отправленные ответы уже проверены, очередь пуста.", 14, MUTED)

    def dataset_panel(self, svg, totals, relevance, y):
        x, w, h = 620, 1108, 258
        svg.rect(x, y, w, h, stroke=LINE)
        svg.text(x + 24, y + 34, "Отношение к ЖКХ в принятом обучающем наборе", 18, INK, 700)
        values = {row["value"]: row["count"] for row in relevance}
        labels = [
            ("ЖКХ", values.get("yes", 0), TEAL),
            ("Не ЖКХ", values.get("no", 0), GRAY),
            ("Не уверен(а)", values.get("unsure", 0), AMBER),
        ]
        total = totals["annotations_approved_dataset"]
        current_x = x + 24
        stack_y = y + 64
        stack_w = w - 48
        for _, value, color in labels:
            segment = value / total * stack_w if total else 0
            svg.rect(current_x, stack_y, max(segment, 2), 37, color, radius=0)
            current_x += segment
        current_y = y + 133
        for label, value, color in labels:
            svg.rect(x + 24, current_y - 14, 15, 15, color, radius=2)
            svg.text(x + 53, current_y, label, 16, MUTED)
            svg.text(x + 250, current_y, number(value), 18, INK, 700)
            svg.text(x + 342, current_y, percentage(value, total), 17, MUTED, 700)
            current_y += 31
        svg.text(
            x + 530,
            y + 155,
            "Положительных ЖКХ-примеров мало:",
            18,
            RED,
            700,
        )
        svg.text(x + 530, y + 189, "для устойчивой модели потребуется", 17, MUTED)
        svg.text(x + 530, y + 218, "целенаправленный добор обращений ЖКХ.", 17, MUTED)

    def score_panel(self, svg, scores, y):
        x, w, h = MARGIN, 420, 384
        svg.rect(x, y, w, h, stroke=LINE)
        svg.text(x + 24, y + 34, "Баллы", 19, INK, 700)
        rows = [
            ("Событий всего", scores["events_total"], INK),
            ("Начислено", f"+{number(scores['positive_points'])}", TEAL),
            ("Штрафов", number(scores["negative_points"]), RED),
            ("Ручная коррекция", f"+{number(scores['manual_adjustment_points'])}", AMBER),
        ]
        current_y = y + 82
        for label, value, color in rows:
            svg.text(x + 24, current_y, label, 16, MUTED)
            svg.text(x + w - 28, current_y, str(value), 20, color, 700, "end")
            svg.line(x + 24, current_y + 18, x + w - 24, current_y + 18, "#eef2f7")
            current_y += 52
        svg.rect(x + 24, y + 302, w - 48, 56, fill="#edf7f6", radius=6)
        svg.text(x + 42, y + 337, "Итог", 18, INK, 700)
        svg.text(x + w - 44, y + 337, f"+{number(scores['net_points'])}", 27, TEAL, 700, "end")

    def reviewers_panel(self, svg, reviewers, y):
        x, w, h = 516, 474, 384
        svg.rect(x, y, w, h, stroke=LINE)
        svg.text(x + 24, y + 34, "Проверяющие", 19, INK, 700)
        headers_y = y + 75
        svg.text(x + 24, headers_y, "Логин", 14, MUTED, 700)
        svg.text(x + 255, headers_y, "Всего", 14, MUTED, 700, "end")
        svg.text(x + 350, headers_y, "Прин.", 14, MUTED, 700, "end")
        svg.text(x + 444, headers_y, "Откл.", 14, MUTED, 700, "end")
        current_y = y + 116
        for index, row in enumerate(reviewers):
            if index % 2 == 0:
                svg.rect(x + 16, current_y - 27, w - 32, 39, "#f8fafc", radius=0)
            svg.text(x + 24, current_y, row["reviewer"], 16, INK, 700 if index == 0 else 400)
            svg.text(x + 255, current_y, number(row["checked"]), 16, INK, 400, "end")
            svg.text(x + 350, current_y, number(row["approved"]), 16, TEAL, 400, "end")
            svg.text(x + 444, current_y, number(row["rejected"]), 16, RED, 400, "end")
            current_y += 44
        svg.text(x + 24, y + 292, "Большая часть контекстного аудита", 15, MUTED)
        svg.text(x + 24, y + 319, "выполнена централизованно,", 15, MUTED)
        svg.text(x + 24, y + 346, "с сохранением истории решений.", 15, MUTED)

    def leaderboard_panel(self, svg, participants, y):
        x, w, h = 1014, 714, 384
        svg.rect(x, y, w, h, stroke=LINE)
        svg.text(x + 24, y + 34, "Топ-10 участников по баллам", 19, INK, 700)
        svg.text(x + 26, y + 69, "Участник", 13, MUTED, 700)
        svg.text(x + 478, y + 69, "Принято", 13, MUTED, 700, "end")
        svg.text(x + 576, y + 69, "Брак", 13, MUTED, 700, "end")
        svg.text(x + 679, y + 69, "Балл", 13, MUTED, 700, "end")
        current_y = y + 101
        for index, row in enumerate(participants, start=1):
            if index % 2:
                svg.rect(x + 16, current_y - 22, w - 32, 29, "#f8fafc", radius=0)
            name = row["name"] or row["username"]
            if len(name) > 29:
                name = name[:27] + "..."
            svg.text(x + 26, current_y, f"{index}. {name}", 14, INK)
            svg.text(x + 478, current_y, number(row["approved_dataset"]), 14, INK, 400, "end")
            svg.text(x + 576, current_y, number(row["rejected"]), 14, RED, 400, "end")
            svg.text(x + 679, current_y, f"{row['score']:+d}", 15, TEAL, 700, "end")
            current_y += 27

    def taxonomy_panel(self, svg, title, rows, x, y, w, h, bar_width, colors):
        svg.rect(x, y, w, h, stroke=LINE)
        svg.text(x + 20, y + 31, title, 17, INK, 700)
        total = sum(row["count"] for row in rows)
        current_y = y + 65
        available = h - 78
        max_rows = max(1, available // 29)
        visible = rows[:max_rows]
        omitted = rows[max_rows:]
        if omitted:
            visible = rows[: max_rows - 1] + [
                {"label": "Остальные", "count": sum(row["count"] for row in omitted)}
            ]
        max_count = max(row["count"] for row in visible) if visible else 1
        for index, row in enumerate(visible):
            label = row["label"]
            if len(label) > 26:
                label = label[:24] + "..."
            color = colors[index % len(colors)]
            svg.text(x + 20, current_y, label, 13, MUTED)
            svg.rect(x + w - bar_width - 92, current_y - 14, bar_width, 14, TRACK, radius=3)
            svg.rect(
                x + w - bar_width - 92,
                current_y - 14,
                max(2, row["count"] / max_count * bar_width),
                14,
                color,
                radius=3,
            )
            svg.text(x + w - 20, current_y, number(row["count"]), 13, INK, 700, "end")
            current_y += 29
        svg.text(x + 20, y + h - 17, f"Всего: {number(total)}", 12, MUTED)

    def insight_panel(self, svg, relevance, x, y, w, h):
        values = {row["value"]: row["count"] for row in relevance}
        total = sum(values.values())
        svg.rect(x, y, w, h, fill="#fff7ed", stroke="#fed7aa")
        svg.text(x + 28, y + 44, "Ключевой вывод для следующего этапа", 21, INK, 700)
        svg.text(x + 28, y + 91, "Текущий верифицированный набор уже пригоден для эксперимента,", 19, MUTED)
        svg.text(x + 28, y + 124, "но для основной задачи диплома положительных примеров ЖКХ недостаточно.", 19, MUTED)
        svg.text(x + 28, y + 183, f"ЖКХ: {number(values.get('yes', 0))} ({percentage(values.get('yes', 0), total)})", 31, TEAL, 700)
        svg.text(x + 394, y + 183, f"Не ЖКХ: {number(values.get('no', 0))} ({percentage(values.get('no', 0), total)})", 31, GRAY, 700)
        svg.text(
            x + 28,
            y + 237,
            "Приоритет добора: вода, отопление, уборка, дворы, УК/ТСЖ и муниципальное благоустройство.",
            17,
            INK,
            700,
        )

    def footer(self, svg, totals, data, y):
        svg.line(MARGIN, y, WIDTH - MARGIN, y, LINE)
        svg.text(MARGIN, y + 44, "Источники отчета", 18, INK, 700)
        svg.text(MARGIN, y + 77, "annotation_statistics.json  |  participants.csv  |  reviewers.csv  |  approved_taxonomy.csv", 16, MUTED)
        svg.text(
            MARGIN,
            y + 116,
            "Подтвержденные удаленные посты исключены из обучающего набора и не начисляют баллы.",
            15,
            MUTED,
        )
        svg.text(
            MARGIN,
            y + 154,
            f"Исходных записей в очереди: {number(totals['source_records_total'])}; активных после исключений: {number(totals['source_records_active'])}.",
            15,
            MUTED,
        )
        svg.text(WIDTH - MARGIN, y + 154, "Diplomnaya rabota / ЖКХ", 15, MUTED, 700, "end")
