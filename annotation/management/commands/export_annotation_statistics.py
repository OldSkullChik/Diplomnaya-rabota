import csv
import json
from html import escape
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum
from django.utils import timezone

from annotation.choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_REJECTED,
    ANNOTATION_STATUS_SUBMITTED,
)
from annotation.models import Annotation, ScoreEvent, SourceRecord


REPORT_FIELDS = [
    "jkh_relevance",
    "jkh_topic",
    "authority_aspect",
    "sentiment",
    "appeal_type",
    "responsible_party",
    "sarcasm",
    "quality",
]


def format_number(value):
    return f"{value:,}".replace(",", " ")


def score_total(queryset):
    return queryset.aggregate(total=Sum("points"))["total"] or 0


def distribution(queryset, field_name):
    labels = dict(Annotation._meta.get_field(field_name).choices)
    values = (
        queryset.values(field_name)
        .annotate(count=Count("id"))
        .order_by("-count", field_name)
    )
    return [
        {
            "value": row[field_name],
            "label": labels.get(row[field_name], row[field_name]),
            "count": row["count"],
        }
        for row in values
    ]


class Command(BaseCommand):
    help = "Export cumulative annotation/review statistics and an SVG infographic."

    def add_arguments(self, parser):
        parser.add_argument("output_dir", help="Directory for report files.")

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_at = timezone.localtime().isoformat(timespec="seconds")
        annotations = Annotation.objects.all()
        approved = annotations.filter(status=ANNOTATION_STATUS_APPROVED)
        rejected = annotations.filter(status=ANNOTATION_STATUS_REJECTED)
        pending = annotations.filter(status=ANNOTATION_STATUS_SUBMITTED)
        checked = annotations.exclude(status=ANNOTATION_STATUS_SUBMITTED)

        confirmed_deleted = approved.filter(
            Q(is_deleted_post_report=True) | Q(record__is_active=False)
        ).distinct()
        approved_dataset = approved.filter(
            is_deleted_post_report=False,
            record__is_active=True,
        )
        rejected_deleted_report = rejected.filter(is_deleted_post_report=True)
        rejected_regular = rejected.filter(is_deleted_post_report=False)

        score_events = ScoreEvent.objects.all()
        manual_events = score_events.filter(annotation__isnull=True)
        review_events = score_events.filter(annotation__isnull=False)

        totals = {
            "source_records_total": SourceRecord.objects.count(),
            "source_records_active": SourceRecord.objects.filter(is_active=True).count(),
            "source_records_excluded": SourceRecord.objects.filter(is_active=False).count(),
            "annotations_submitted_all_time": annotations.count(),
            "annotations_checked": checked.count(),
            "annotations_pending": pending.count(),
            "annotations_approved_total": approved.count(),
            "annotations_approved_dataset": approved_dataset.count(),
            "deleted_posts_confirmed": confirmed_deleted.count(),
            "annotations_rejected_total": rejected.count(),
            "regular_annotations_rejected": rejected_regular.count(),
            "deleted_post_reports_rejected": rejected_deleted_report.count(),
            "unique_records_checked": checked.values("record_id").distinct().count(),
            "unique_records_approved_dataset": approved_dataset.values("record_id").distinct().count(),
        }
        scores = {
            "events_total": score_events.count(),
            "net_points": score_total(score_events),
            "positive_events": score_events.filter(points__gt=0).count(),
            "positive_points": score_total(score_events.filter(points__gt=0)),
            "negative_events": score_events.filter(points__lt=0).count(),
            "negative_points": score_total(score_events.filter(points__lt=0)),
            "review_events": review_events.count(),
            "review_points": score_total(review_events),
            "manual_adjustment_events": manual_events.count(),
            "manual_adjustment_points": score_total(manual_events),
            "annotations_with_multiple_score_events": (
                annotations.annotate(event_count=Count("score_events"))
                .filter(event_count__gt=1)
                .count()
            ),
        }

        participants = self.build_participants()
        reviewers = self.build_reviewers()
        taxonomy = {
            field_name: distribution(approved_dataset, field_name)
            for field_name in REPORT_FIELDS
        }
        payload = {
            "generated_at": generated_at,
            "scope": "Cumulative snapshot from the current production database history.",
            "definitions": {
                "annotations_checked": "Annotations currently in approved or rejected status.",
                "annotations_approved_dataset": "Approved annotations usable for training, excluding confirmed deleted posts.",
                "deleted_posts_confirmed": "Approved deleted-post decisions; excluded without score.",
                "annotations_rejected_total": "Rejected annotations; their records may later be annotated again.",
            },
            "totals": totals,
            "scores": scores,
            "reviewers": reviewers,
            "participants": participants,
            "approved_dataset_taxonomy": taxonomy,
        }

        self.write_json(output_dir / "annotation_statistics.json", payload)
        self.write_participants_csv(output_dir / "participants.csv", participants)
        self.write_reviewers_csv(output_dir / "reviewers.csv", reviewers)
        self.write_taxonomy_csv(output_dir / "approved_taxonomy.csv", taxonomy)
        self.write_markdown(output_dir / "annotation_statistics.md", payload)
        self.write_svg(output_dir / "annotation_statistics_infographic.svg", payload)

        self.stdout.write(f"generated_at={generated_at}")
        self.stdout.write(f"annotations_submitted_all_time={totals['annotations_submitted_all_time']}")
        self.stdout.write(f"annotations_checked={totals['annotations_checked']}")
        self.stdout.write(f"annotations_approved_dataset={totals['annotations_approved_dataset']}")
        self.stdout.write(f"deleted_posts_confirmed={totals['deleted_posts_confirmed']}")
        self.stdout.write(f"annotations_rejected_total={totals['annotations_rejected_total']}")
        self.stdout.write(f"annotations_pending={totals['annotations_pending']}")
        self.stdout.write(f"net_points={scores['net_points']}")
        self.stdout.write(self.style.SUCCESS(f"Report written to {output_dir}"))

    def build_participants(self):
        User = get_user_model()
        users = (
            User.objects.filter(Q(annotations__isnull=False) | Q(score_events__isnull=False))
            .select_related("profile")
            .distinct()
        )
        rows = []
        for user in users:
            user_annotations = Annotation.objects.filter(student=user)
            approved = user_annotations.filter(status=ANNOTATION_STATUS_APPROVED)
            accepted_dataset = approved.filter(
                is_deleted_post_report=False,
                record__is_active=True,
            )
            deleted_confirmed = approved.filter(
                Q(is_deleted_post_report=True) | Q(record__is_active=False)
            ).distinct()
            user_scores = ScoreEvent.objects.filter(student=user)
            rows.append(
                {
                    "username": user.username,
                    "name": user.get_full_name(),
                    "submitted": user_annotations.count(),
                    "checked": user_annotations.exclude(status=ANNOTATION_STATUS_SUBMITTED).count(),
                    "approved_dataset": accepted_dataset.count(),
                    "deleted_confirmed": deleted_confirmed.count(),
                    "rejected": user_annotations.filter(status=ANNOTATION_STATUS_REJECTED).count(),
                    "pending": user_annotations.filter(status=ANNOTATION_STATUS_SUBMITTED).count(),
                    "score": score_total(user_scores),
                }
            )
        rows.sort(key=lambda row: (-row["score"], -row["approved_dataset"], row["username"].lower()))
        return rows

    def build_reviewers(self):
        rows = (
            Annotation.objects.exclude(status=ANNOTATION_STATUS_SUBMITTED)
            .values("reviewed_by__username")
            .annotate(
                checked=Count("id"),
                approved=Count("id", filter=Q(status=ANNOTATION_STATUS_APPROVED)),
                rejected=Count("id", filter=Q(status=ANNOTATION_STATUS_REJECTED)),
            )
            .order_by("-checked", "reviewed_by__username")
        )
        return [
            {
                "reviewer": row["reviewed_by__username"] or "(unknown)",
                "checked": row["checked"],
                "approved": row["approved"],
                "rejected": row["rejected"],
            }
            for row in rows
        ]

    def write_json(self, path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_participants_csv(self, path, rows):
        fields = [
            "username",
            "name",
            "submitted",
            "checked",
            "approved_dataset",
            "deleted_confirmed",
            "rejected",
            "pending",
            "score",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def write_reviewers_csv(self, path, rows):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["reviewer", "checked", "approved", "rejected"])
            writer.writeheader()
            writer.writerows(rows)

    def write_taxonomy_csv(self, path, taxonomy):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["field", "value", "label", "count"])
            writer.writeheader()
            for field_name, entries in taxonomy.items():
                for entry in entries:
                    writer.writerow({"field": field_name, **entry})

    def write_markdown(self, path, payload):
        totals = payload["totals"]
        scores = payload["scores"]
        lines = [
            "# Сводная статистика разметки",
            "",
            f"Срез сформирован: `{payload['generated_at']}`.",
            "",
            "## Итоги проверки",
            "",
            "| Показатель | Значение |",
            "| --- | ---: |",
            f"| Всего отправлено разметок | {format_number(totals['annotations_submitted_all_time'])} |",
            f"| Проверено | {format_number(totals['annotations_checked'])} |",
            f"| Принято в обучающий набор | {format_number(totals['annotations_approved_dataset'])} |",
            f"| Подтверждено удаленных постов без баллов | {format_number(totals['deleted_posts_confirmed'])} |",
            f"| Отклонено | {format_number(totals['annotations_rejected_total'])} |",
            f"| Ожидает проверки | {format_number(totals['annotations_pending'])} |",
            "",
            "## Баллы",
            "",
            "| Показатель | Значение |",
            "| --- | ---: |",
            f"| Начислений | {format_number(scores['positive_events'])} / +{format_number(scores['positive_points'])} |",
            f"| Штрафов | {format_number(scores['negative_events'])} / {format_number(scores['negative_points'])} |",
            f"| Ручных корректировок | {format_number(scores['manual_adjustment_events'])} / {scores['manual_adjustment_points']:+d} |",
            f"| Суммарный баланс | {scores['net_points']:+d} |",
            "",
            "## Участники",
            "",
            "| Логин | Имя | Проверено | Принято | Удаленные посты | Отклонено | Балл |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in payload["participants"]:
            lines.append(
                f"| {row['username']} | {row['name']} | {row['checked']} | "
                f"{row['approved_dataset']} | {row['deleted_confirmed']} | "
                f"{row['rejected']} | {row['score']:+d} |"
            )
        lines.extend(
            [
                "",
                "Примечание: это накопительный срез текущей истории базы данных. "
                "Подтвержденные удаленные посты не входят в обучающий набор и не дают баллов.",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")

    def write_svg(self, path, payload):
        totals = payload["totals"]
        scores = payload["scores"]
        participants = payload["participants"][:10]
        submitted = max(totals["annotations_submitted_all_time"], 1)
        bars = [
            ("Принято в датасет", totals["annotations_approved_dataset"], "#0f766e"),
            ("Удаленный пост", totals["deleted_posts_confirmed"], "#0ea5a8"),
            ("Отклонено", totals["annotations_rejected_total"], "#d9485f"),
            ("Ожидает проверки", totals["annotations_pending"], "#64748b"),
        ]
        height = 800 + len(participants) * 34
        generated = escape(payload["generated_at"].replace("T", " "))
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
            '<rect width="1200" height="100%" fill="#f8fafc"/>',
            '<rect width="1200" height="124" fill="#102a43"/>',
            '<text x="54" y="54" font-family="Arial, sans-serif" font-size="32" font-weight="700" fill="#ffffff">Статистика разметки ЖКХ</text>',
            f'<text x="54" y="88" font-family="Arial, sans-serif" font-size="16" fill="#cbd5e1">Накопительный срез: {generated}</text>',
        ]
        cards = [
            ("Отправлено", totals["annotations_submitted_all_time"]),
            ("Проверено", totals["annotations_checked"]),
            ("В датасете", totals["annotations_approved_dataset"]),
            ("Баланс", f"{scores['net_points']:+d}"),
        ]
        for index, (label, value) in enumerate(cards):
            x = 54 + index * 274
            parts.extend(
                [
                    f'<rect x="{x}" y="154" width="248" height="110" rx="8" fill="#ffffff" stroke="#d9e2ec"/>',
                    f'<text x="{x + 20}" y="188" font-family="Arial, sans-serif" font-size="15" fill="#52606d">{escape(label)}</text>',
                    f'<text x="{x + 20}" y="232" font-family="Arial, sans-serif" font-size="36" font-weight="700" fill="#102a43">{escape(format_number(value) if isinstance(value, int) else value)}</text>',
                ]
            )
        parts.append('<text x="54" y="316" font-family="Arial, sans-serif" font-size="21" font-weight="700" fill="#102a43">Результаты проверки</text>')
        y = 350
        for label, value, color in bars:
            width = max(2, round(690 * value / submitted))
            parts.extend(
                [
                    f'<text x="54" y="{y + 20}" font-family="Arial, sans-serif" font-size="16" fill="#334e68">{escape(label)}</text>',
                    f'<rect x="254" y="{y + 4}" width="690" height="24" rx="4" fill="#e5e7eb"/>',
                    f'<rect x="254" y="{y + 4}" width="{width}" height="24" rx="4" fill="{color}"/>',
                    f'<text x="962" y="{y + 21}" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#102a43">{format_number(value)}</text>',
                ]
            )
            y += 48
        parts.extend(
            [
                f'<text x="54" y="{y + 34}" font-family="Arial, sans-serif" font-size="21" font-weight="700" fill="#102a43">Топ участников по баллам</text>',
                f'<text x="54" y="{y + 72}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#52606d">Участник</text>',
                f'<text x="570" y="{y + 72}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#52606d">Принято</text>',
                f'<text x="725" y="{y + 72}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#52606d">Отклонено</text>',
                f'<text x="890" y="{y + 72}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#52606d">Балл</text>',
            ]
        )
        row_y = y + 108
        for index, row in enumerate(participants, start=1):
            fill = "#ffffff" if index % 2 else "#f1f5f9"
            display_name = row["name"] or row["username"]
            name = escape(f"{index}. {display_name} ({row['username']})")
            parts.extend(
                [
                    f'<rect x="54" y="{row_y - 24}" width="944" height="32" fill="{fill}"/>',
                    f'<text x="66" y="{row_y}" font-family="Arial, sans-serif" font-size="15" fill="#102a43">{name}</text>',
                    f'<text x="570" y="{row_y}" font-family="Arial, sans-serif" font-size="15" fill="#102a43">{format_number(row["approved_dataset"])}</text>',
                    f'<text x="725" y="{row_y}" font-family="Arial, sans-serif" font-size="15" fill="#102a43">{format_number(row["rejected"])}</text>',
                    f'<text x="890" y="{row_y}" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#102a43">{row["score"]:+d}</text>',
                ]
            )
            row_y += 34
        parts.extend(
            [
                f'<text x="54" y="{height - 34}" font-family="Arial, sans-serif" font-size="13" fill="#52606d">Удаленные посты подтверждаются без начисления баллов и исключаются из обучающего набора.</text>',
                "</svg>",
            ]
        )
        path.write_text("\n".join(parts), encoding="utf-8")
