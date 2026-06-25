from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from annotation.models import MonitoringItem, OmsuArea, OmsuDashboardSnapshot, OmsuLatestComment
from annotation.monitoring.text import clean_ticker_comment_text


def refresh_dashboard_from_monitoring(*, window_hours: int = 24, latest_per_area: int = 3) -> dict[str, int]:
    since = timezone.now() - timedelta(hours=window_hours)
    summary = {
        "snapshots_updated": 0,
        "latest_comments_created": 0,
        "items_seen": 0,
        "items_analyzed": 0,
        "items_relevant": 0,
    }
    areas = OmsuArea.objects.filter(is_active=True).order_by("display_order", "name")

    for area in areas:
        items = MonitoringItem.objects.filter(area=area, published_at__gte=since)
        analyzed = items.filter(analyzed_at__isnull=False)
        if not items.exists():
            continue
        relevant_ids = [
            item_id
            for item_id, taxonomy in analyzed.values_list("id", "taxonomy")
            if (taxonomy or {}).get("jkh_relevance") == "yes"
        ]
        relevant = analyzed.filter(id__in=relevant_ids)
        items_count = items.count()
        analyzed_count = analyzed.count()
        relevant_count = len(relevant_ids)
        summary["items_seen"] += items_count
        summary["items_analyzed"] += analyzed_count
        summary["items_relevant"] += relevant_count

        snapshot, _created = OmsuDashboardSnapshot.objects.get_or_create(area=area)
        previous = snapshot.omsu_score
        score_avg = relevant.aggregate(value=Avg("omsu_score"))["value"]
        score = int(round(score_avg or 0))
        probability_avg = relevant.aggregate(value=Avg("omsu_negative_probability"))["value"] or 0.0
        negative_total = relevant.filter(omsu_decision="negative_omsu").count()
        positive_total = relevant.filter(omsu_decision="not_negative_omsu").count()
        neutral_total = max(relevant.count() - negative_total - positive_total, 0)
        top_topics = build_top_topics(relevant)

        snapshot.previous_omsu_score = previous
        snapshot.omsu_score = score
        snapshot.omsu_negative_probability = float(probability_avg)
        snapshot.comments_total = relevant_count
        snapshot.comments_last_day = relevant_count
        snapshot.negative_total = negative_total
        snapshot.neutral_total = neutral_total
        snapshot.positive_total = positive_total
        snapshot.top_topics = top_topics
        snapshot.charts = build_charts(
            relevant,
            top_topics,
            analyzed_queryset=analyzed,
            score=score,
            previous_score=previous,
            negative_probability=float(probability_avg),
            negative_total=negative_total,
            neutral_total=neutral_total,
            positive_total=positive_total,
        )
        snapshot.generated_at = timezone.now()
        snapshot.save()
        summary["snapshots_updated"] += 1

        latest_items = list(
            relevant.order_by("-published_at", "-fetched_at")[:latest_per_area]
        )
        for item in latest_items:
            if OmsuLatestComment.objects.filter(source_url=item.source_url).exists():
                continue
            ticker_text = clean_ticker_comment_text(item.text, author_name=item.author_name)
            if not ticker_text:
                continue
            OmsuLatestComment.objects.create(
                area=area,
                text=ticker_text,
                sentiment=item.taxonomy.get("sentiment", "neutral") if item.taxonomy else "neutral",
                omsu_score=item.omsu_score,
                source_name=str(item.source),
                source_url=item.source_url,
                published_at=item.published_at or item.fetched_at,
                received_at=item.fetched_at,
            )
            summary["latest_comments_created"] += 1

    return summary


def build_top_topics(queryset) -> list[dict[str, int]]:
    counts: Counter[str] = Counter()
    for taxonomy in queryset.values_list("taxonomy", flat=True):
        topic = (taxonomy or {}).get("jkh_topic", "")
        if topic:
            counts[topic] += 1
    return [{"label": label, "value": value} for label, value in counts.most_common(6)]


def build_charts(
    queryset,
    top_topics: list[dict[str, int]],
    *,
    analyzed_queryset=None,
    score: int = 0,
    previous_score: int = 0,
    negative_probability: float = 0.0,
    negative_total: int = 0,
    neutral_total: int = 0,
    positive_total: int = 0,
) -> dict:
    analyzed_queryset = analyzed_queryset if analyzed_queryset is not None else queryset
    analyzed_count = analyzed_queryset.count()
    relevant_count = queryset.count()
    non_relevant_count = max(analyzed_count - relevant_count, 0)

    sentiment_counts = Counter()
    appeal_counts = Counter()
    responsible_counts = Counter()
    quality_counts = Counter()
    authority_counts = Counter()
    impact_counts = Counter(queryset.values_list("omsu_impact_class", flat=True))
    decision_counts = Counter(queryset.values_list("omsu_decision", flat=True))
    confidence_counts = Counter(queryset.values_list("omsu_confidence_band", flat=True))
    type_counts = Counter(queryset.values_list("item_type", flat=True))
    source_counts = Counter(queryset.values_list("source__screen_name", flat=True))
    negative_topic_counts = Counter()
    topic_sentiment_matrix: defaultdict[tuple[str, str], int] = defaultdict(int)
    score_buckets = Counter()

    taxonomy_rows = list(queryset.values_list("taxonomy", flat=True))
    for taxonomy in taxonomy_rows:
        taxonomy = taxonomy or {}
        topic = safe_label(taxonomy.get("jkh_topic"))
        sentiment = safe_label(taxonomy.get("sentiment"))
        sentiment_counts[sentiment] += 1
        appeal_counts[safe_label(taxonomy.get("appeal_type"))] += 1
        responsible_counts[safe_label(taxonomy.get("responsible_party"))] += 1
        quality_counts[safe_label(taxonomy.get("quality"))] += 1
        authority_counts[safe_label(taxonomy.get("authority_aspect"))] += 1
        topic_sentiment_matrix[(topic, sentiment)] += 1
        if sentiment == "negative":
            negative_topic_counts[topic] += 1

    for value in queryset.values_list("omsu_score", flat=True):
        score_value = int(value or 0)
        if score_value <= -60:
            score_buckets["-100..-60"] += 1
        elif score_value <= -25:
            score_buckets["-59..-25"] += 1
        elif score_value < 25:
            score_buckets["-24..+24"] += 1
        else:
            score_buckets["+25..+100"] += 1

    score_trend = [["previous", previous_score], ["current", score]]
    comment_volume = [
        ["analyzed", analyzed_count],
        ["jkh_relevant", relevant_count],
        ["negative_omsu", negative_total],
    ]
    relevance_filter = [
        ["all_analyzed", analyzed_count],
        ["jkh_relevant", relevant_count],
        ["non_jkh_noise", non_relevant_count],
    ]
    negative_probability_chart = [["negative_probability_pct", round(float(negative_probability) * 100, 2)]]

    legacy_charts = {
        "score_trend": score_trend,
        "topic_distribution": chart_pairs(top_topics),
        "sentiment_balance": as_chart(sentiment_counts),
        "appeal_types": as_chart(appeal_counts),
        "negative_probability": negative_probability_chart,
        "comment_volume": comment_volume,
        "responsible_parties": as_chart(responsible_counts),
        "quality_mix": as_chart(quality_counts),
        "authority_aspects": as_chart(authority_counts),
        "impact_classes": as_chart(impact_counts),
        "decision_mix": as_chart(decision_counts),
        "confidence_bands": as_chart(confidence_counts),
        "source_contribution": as_chart(source_counts),
        "item_types": as_chart(type_counts),
        "negative_topics": as_chart(negative_topic_counts),
        "score_buckets": as_chart(score_buckets),
        "relevance_filter": relevance_filter,
    }

    legacy_charts["chart_catalog"] = build_chart_catalog(
        legacy_charts=legacy_charts,
        topic_sentiment_matrix=topic_sentiment_matrix,
        score=score,
        previous_score=previous_score,
        relevant_count=relevant_count,
        analyzed_count=analyzed_count,
    )
    legacy_charts["chart_layout"] = {
        "desktop_primary": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
        "desktop_drawer": [
            "negative_probability",
            "comment_volume",
            "responsible_parties",
            "quality_mix",
            "authority_aspects",
            "impact_classes",
            "decision_mix",
            "confidence_bands",
            "source_contribution",
            "negative_topics",
            "score_buckets",
            "relevance_filter",
        ],
        "android_summary": ["score_trend", "negative_probability", "sentiment_balance", "topic_distribution"],
        "android_details": [
            "appeal_types",
            "responsible_parties",
            "authority_aspects",
            "decision_mix",
            "source_contribution",
            "topic_sentiment_heatmap",
            "relevance_filter",
        ],
    }
    return legacy_charts


def as_chart(counter: Counter[str]) -> list[list]:
    return [[label or "unknown", value] for label, value in counter.most_common() if label]


def chart_pairs(items) -> list[list]:
    pairs = []
    for item in items or []:
        if isinstance(item, dict):
            pairs.append([item.get("label", "unknown"), item.get("value", 0)])
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append([item[0], item[1]])
    return pairs


def safe_label(value) -> str:
    return str(value or "unknown").strip() or "unknown"


def points(pairs: list[list]) -> list[dict[str, int | float | str]]:
    return [{"label": str(label), "value": value} for label, value in pairs]


def chart(
    *,
    chart_id: str,
    title: str,
    chart_type: str,
    meaning: str,
    weight: int,
    data,
    priority: int,
    unit: str = "count",
    client_hints: dict | None = None,
):
    return {
        "id": chart_id,
        "title": title,
        "type": chart_type,
        "meaning": meaning,
        "weight": weight,
        "priority": priority,
        "unit": unit,
        "data": data,
        "client_hints": client_hints or {},
    }


def build_chart_catalog(
    *,
    legacy_charts: dict,
    topic_sentiment_matrix: dict[tuple[str, str], int],
    score: int,
    previous_score: int,
    relevant_count: int,
    analyzed_count: int,
) -> list[dict]:
    delta = score - previous_score
    matrix_data = [
        {"x": topic, "y": sentiment, "value": value}
        for (topic, sentiment), value in sorted(topic_sentiment_matrix.items())
    ]
    catalog = [
        chart(
            chart_id="score_trend",
            title="Динамика оценки ОМСУ",
            chart_type="line",
            meaning="Показывает изменение интегральной оценки территории относительно предыдущего среза.",
            weight=100,
            priority=1,
            unit="score",
            data=points(legacy_charts["score_trend"]),
            client_hints={"desktop": "main", "android": "summary"},
        ),
        chart(
            chart_id="score_delta",
            title="Изменение оценки",
            chart_type="delta",
            meaning="Быстро показывает, ухудшилась или улучшилась оценка с прошлого обновления.",
            weight=94,
            priority=2,
            unit="score_delta",
            data={"previous": previous_score, "current": score, "delta": delta},
            client_hints={"desktop": "badge", "android": "summary_card"},
        ),
        chart(
            chart_id="negative_probability",
            title="Вероятность негативного сигнала",
            chart_type="gauge",
            meaning="Оценивает риск того, что текущий поток сообщений содержит значимый негатив к работе ОМСУ.",
            weight=92,
            priority=3,
            unit="percent",
            data=points(legacy_charts["negative_probability"]),
            client_hints={"desktop": "drawer", "android": "summary"},
        ),
        chart(
            chart_id="relevance_filter",
            title="Фильтр ЖКХ-сигналов",
            chart_type="funnel",
            meaning="Показывает, сколько сообщений было проанализировано и сколько из них реально относится к ЖКХ.",
            weight=90,
            priority=4,
            data=points(legacy_charts["relevance_filter"]),
            client_hints={"desktop": "drawer", "android": "diagnostic"},
        ),
        chart(
            chart_id="topic_distribution",
            title="Темы ЖКХ",
            chart_type="bar",
            meaning="Показывает основные темы обращений: мусор, вода, дворы, отопление, тарифы и другие направления.",
            weight=88,
            priority=5,
            data=points(legacy_charts["topic_distribution"]),
            client_hints={"desktop": "main", "android": "summary"},
        ),
        chart(
            chart_id="negative_topics",
            title="Темы негативных сообщений",
            chart_type="horizontal_bar",
            meaning="Помогает понять, какие темы дают именно негативный вклад в оценку территории.",
            weight=86,
            priority=6,
            data=points(legacy_charts["negative_topics"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="sentiment_balance",
            title="Баланс тональности",
            chart_type="donut",
            meaning="Показывает соотношение негативных, нейтральных и позитивных ЖКХ-сообщений.",
            weight=84,
            priority=7,
            data=points(legacy_charts["sentiment_balance"]),
            client_hints={"desktop": "main", "android": "summary"},
        ),
        chart(
            chart_id="appeal_types",
            title="Типы обращений",
            chart_type="bar",
            meaning="Разделяет поток на жалобы, вопросы, просьбы, предложения, мнения и благодарности.",
            weight=82,
            priority=8,
            data=points(legacy_charts["appeal_types"]),
            client_hints={"desktop": "main", "android": "details"},
        ),
        chart(
            chart_id="responsible_parties",
            title="Ответственные стороны",
            chart_type="bar",
            meaning="Показывает, с кем чаще всего связывают проблему: администрация, УК, ресурсники, оператор ТКО и т.д.",
            weight=80,
            priority=9,
            data=points(legacy_charts["responsible_parties"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="authority_aspects",
            title="Аспекты работы власти",
            chart_type="bar",
            meaning="Показывает, какие аспекты управления упоминаются: бездействие, контроль, коммуникация, сроки реакции.",
            weight=78,
            priority=10,
            data=points(legacy_charts["authority_aspects"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="decision_mix",
            title="Решения OMSU-модели",
            chart_type="pie",
            meaning="Показывает доли negative_omsu, not_negative_omsu и low_confidence среди ЖКХ-сообщений.",
            weight=76,
            priority=11,
            data=points(legacy_charts["decision_mix"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="impact_classes",
            title="Классы влияния на оценку",
            chart_type="stacked_bar",
            meaning="Показывает распределение сильного негатива, умеренного негатива, нейтрали и позитива.",
            weight=74,
            priority=12,
            data=points(legacy_charts["impact_classes"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="confidence_bands",
            title="Уверенность модели",
            chart_type="bar",
            meaning="Показывает, насколько надежны решения модели по негативному сигналу ОМСУ.",
            weight=72,
            priority=13,
            data=points(legacy_charts["confidence_bands"]),
            client_hints={"desktop": "drawer", "android": "diagnostic"},
        ),
        chart(
            chart_id="quality_mix",
            title="Качество сообщений",
            chart_type="donut",
            meaning="Отделяет нормальные сообщения от сложных, дублей, спама и низкокачественного текста.",
            weight=70,
            priority=14,
            data=points(legacy_charts["quality_mix"]),
            client_hints={"desktop": "drawer", "android": "diagnostic"},
        ),
        chart(
            chart_id="source_contribution",
            title="Вклад источников",
            chart_type="horizontal_bar",
            meaning="Показывает, какие VK-группы дают больше всего ЖКХ-релевантных сигналов.",
            weight=68,
            priority=15,
            data=points(legacy_charts["source_contribution"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="comment_volume",
            title="Воронка объема сообщений",
            chart_type="line",
            meaning="Сравнивает общий анализируемый поток, ЖКХ-релевантную часть и негативные сигналы.",
            weight=66,
            priority=16,
            data=points(legacy_charts["comment_volume"]),
            client_hints={"desktop": "drawer", "android": "summary"},
        ),
        chart(
            chart_id="item_types",
            title="Посты и комментарии",
            chart_type="stacked_bar",
            meaning="Показывает, откуда поступают ЖКХ-сигналы: из самостоятельных постов или из комментариев.",
            weight=64,
            priority=17,
            data=points(legacy_charts["item_types"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="score_buckets",
            title="Распределение оценок",
            chart_type="histogram",
            meaning="Показывает, насколько много сообщений дают сильный негатив, умеренный негатив, нейтральный или позитивный вклад.",
            weight=62,
            priority=18,
            data=points(legacy_charts["score_buckets"]),
            client_hints={"desktop": "drawer", "android": "details"},
        ),
        chart(
            chart_id="topic_sentiment_heatmap",
            title="Тема x тональность",
            chart_type="heatmap",
            meaning="Показывает, какие темы чаще всего связаны с негативной, нейтральной или позитивной тональностью.",
            weight=60,
            priority=19,
            data=matrix_data,
            client_hints={"desktop": "advanced", "android": "details"},
        ),
        chart(
            chart_id="coverage_ratio",
            title="Доля ЖКХ в общем потоке",
            chart_type="ratio",
            meaning="Показывает, какую часть общего городского шума составляют сообщения по ЖКХ.",
            weight=58,
            priority=20,
            unit="percent",
            data={
                "analyzed": analyzed_count,
                "relevant": relevant_count,
                "ratio": round((relevant_count / analyzed_count * 100), 2) if analyzed_count else 0.0,
            },
            client_hints={"desktop": "diagnostic", "android": "summary_card"},
        ),
    ]
    return sorted(catalog, key=lambda item: item["priority"])
