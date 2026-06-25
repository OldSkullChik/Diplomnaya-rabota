from django.conf import settings
from django.db.models import Max, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.crypto import constant_time_compare
from django.utils import timezone

from .models import OmsuArea, OmsuLatestComment


API_VERSION = "v1"
CHART_SCHEMA_VERSION = "2026-06-17"


def refresh_policy():
    return {
        "snapshot": {
            "mode": "after_hourly_monitoring_run",
            "refresh_seconds": settings.OMSU_API_SNAPSHOT_REFRESH_SECONDS,
            "description": "Scores, charts and map metrics change after the monitoring collector refreshes dashboard snapshots.",
        },
        "comments": {
            "mode": "poll_latest_comment_endpoint",
            "refresh_seconds": settings.OMSU_API_COMMENT_REFRESH_SECONDS,
            "description": "The ticker/comment stream is lightweight and may be polled more often than the full snapshot.",
        },
    }


def api_key_from_request(request):
    header_key = request.headers.get("X-OMSU-API-Key", "").strip()
    if header_key:
        return header_key
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def api_key_is_valid(candidate):
    if not getattr(settings, "OMSU_API_REQUIRE_KEY", False):
        return True
    keys = [str(key).strip() for key in getattr(settings, "OMSU_API_KEYS", ()) if str(key).strip()]
    if not candidate or not keys:
        return False
    return any(constant_time_compare(candidate, key) for key in keys)


def api_key_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not api_key_is_valid(api_key_from_request(request)):
            return JsonResponse(
                {
                    "status": "error",
                    "error": "invalid_api_key",
                    "message": "OMSU API key is required.",
                },
                status=401,
                json_dumps_params={"ensure_ascii": False},
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def score_to_color(score):
    clamped = max(-100, min(100, int(score or 0)))
    ratio = (clamped + 100) / 200
    if ratio < 0.5:
        local = ratio / 0.5
        red, green, blue = 220, round(38 + (180 - 38) * local), 38
    else:
        local = (ratio - 0.5) / 0.5
        red, green, blue = round(220 + (22 - 220) * local), 180, 70
    return f"#{red:02x}{green:02x}{blue:02x}"


def confidence_band(probability):
    if probability >= 0.85:
        return "high_negative"
    if probability <= 0.15:
        return "high_not_negative"
    return "low_confidence"


def serialize_comment(comment):
    if not comment:
        return None
    return {
        "id": comment.id,
        "area_slug": comment.area.slug,
        "area_name": comment.area.name,
        "text": comment.text,
        "sentiment": comment.sentiment,
        "omsu_score": comment.omsu_score,
        "source_name": comment.source_name,
        "source_url": comment.source_url,
        "published_at": comment.published_at.isoformat(),
        "received_at": comment.received_at.isoformat(),
    }


def serialize_area(area, include_detail=False):
    snapshot = getattr(area, "snapshot", None)
    latest_comment = None
    prefetched = getattr(area, "prefetched_latest_comments", None)
    if prefetched:
        latest_comment = prefetched[0]

    payload = {
        "slug": area.slug,
        "name": area.name,
        "area_type": area.area_type,
        "region": area.region,
        "score": snapshot.omsu_score if snapshot else 0,
        "previous_score": snapshot.previous_omsu_score if snapshot else 0,
        "score_color": score_to_color(snapshot.omsu_score if snapshot else 0),
        "negative_probability": snapshot.omsu_negative_probability if snapshot else 0.0,
        "confidence_band": confidence_band(snapshot.omsu_negative_probability if snapshot else 0.0),
        "comments_total": snapshot.comments_total if snapshot else 0,
        "comments_last_day": snapshot.comments_last_day if snapshot else 0,
        "negative_total": snapshot.negative_total if snapshot else 0,
        "neutral_total": snapshot.neutral_total if snapshot else 0,
        "positive_total": snapshot.positive_total if snapshot else 0,
        "top_topics": snapshot.top_topics if snapshot else [],
        "geometry": area.geometry,
        "latest_comment": serialize_comment(latest_comment),
    }

    if include_detail:
        payload.update(
            {
                "head_name": area.head_name,
                "leadership": area.leadership,
                "territory_area_km2": float(area.territory_area_km2) if area.territory_area_km2 is not None else None,
                "population": area.population,
                "image_url": area.image_url,
                "description": area.description,
                "charts": snapshot.charts if snapshot else {},
                "snapshot_generated_at": snapshot.generated_at.isoformat() if snapshot else None,
            }
        )

    return payload


@api_key_required
def manifest(request):
    return JsonResponse(
        {
            "api_version": API_VERSION,
            "domain": "zhkh_omsu_monitoring",
            "chart_schema_version": CHART_SCHEMA_VERSION,
            "chart_contract": {
                "legacy_charts": "area.charts.<chart_id> remains a simple label/value series for existing desktop clients.",
                "chart_catalog": "area.charts.chart_catalog contains typed chart descriptors for desktop and Android clients.",
                "layout": "area.charts.chart_layout and snapshot.widgets expose recommended chart groups.",
            },
            "snapshot_refresh_seconds": settings.OMSU_API_SNAPSHOT_REFRESH_SECONDS,
            "comment_refresh_seconds": settings.OMSU_API_COMMENT_REFRESH_SECONDS,
            "refresh_policy": refresh_policy(),
            "endpoints": {
                "snapshot": "/api/v1/omsu/snapshot/",
                "area_detail": "/api/v1/omsu/areas/{slug}/",
                "latest_comment": "/api/v1/omsu/latest-comment/?area={slug}&limit=1",
                "latest_comments": "/api/v1/omsu/latest-comment/?area={slug}&limit={limit}",
            },
            "served_at": timezone.now().isoformat(),
        },
        json_dumps_params={"ensure_ascii": False},
    )


@api_key_required
def snapshot(request):
    latest_prefetch = Prefetch(
        "latest_comments",
        queryset=OmsuLatestComment.objects.order_by("-published_at", "-received_at")[:1],
        to_attr="prefetched_latest_comments",
    )
    areas = (
        OmsuArea.objects.filter(is_active=True)
        .select_related("snapshot")
        .prefetch_related(latest_prefetch)
        .order_by("display_order", "name")
    )
    served_at = timezone.now()
    generated_at = (
        OmsuArea.objects.filter(is_active=True, snapshot__isnull=False)
        .aggregate(value=Max("snapshot__generated_at"))["value"]
        or served_at
    )
    return JsonResponse(
        {
            "api_version": API_VERSION,
            "chart_schema_version": CHART_SCHEMA_VERSION,
            "generated_at": generated_at.isoformat(),
            "served_at": served_at.isoformat(),
            "snapshot_refresh_seconds": settings.OMSU_API_SNAPSHOT_REFRESH_SECONDS,
            "comment_refresh_seconds": settings.OMSU_API_COMMENT_REFRESH_SECONDS,
            "refresh_policy": refresh_policy(),
            "map": {
                "projection": "normalized-local",
                "focus_region": "Нижегородская область",
                "bounds": [0, 0, 1000, 620],
                "score_scale": {"min": -100, "max": 100, "negative": "red", "positive": "green"},
            },
            "areas": [serialize_area(area) for area in areas],
            "widgets": {
                "main": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
                "spare": ["negative_probability", "comment_volume", "responsible_parties", "quality_mix"],
                "desktop": {
                    "primary": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
                    "drawer": [
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
                },
                "android": {
                    "summary": ["score_trend", "negative_probability", "sentiment_balance", "topic_distribution"],
                    "details": [
                        "appeal_types",
                        "responsible_parties",
                        "authority_aspects",
                        "decision_mix",
                        "source_contribution",
                        "topic_sentiment_heatmap",
                        "relevance_filter",
                    ],
                },
                "available": [
                    "score_trend",
                    "score_delta",
                    "negative_probability",
                    "relevance_filter",
                    "topic_distribution",
                    "negative_topics",
                    "sentiment_balance",
                    "appeal_types",
                    "responsible_parties",
                    "authority_aspects",
                    "decision_mix",
                    "impact_classes",
                    "confidence_bands",
                    "quality_mix",
                    "source_contribution",
                    "comment_volume",
                    "item_types",
                    "score_buckets",
                    "topic_sentiment_heatmap",
                    "coverage_ratio",
                ],
            },
        },
        json_dumps_params={"ensure_ascii": False},
    )


@api_key_required
def area_detail(request, slug):
    latest_prefetch = Prefetch(
        "latest_comments",
        queryset=OmsuLatestComment.objects.order_by("-published_at", "-received_at")[:1],
        to_attr="prefetched_latest_comments",
    )
    area = get_object_or_404(
        OmsuArea.objects.select_related("snapshot").prefetch_related(latest_prefetch),
        slug=slug,
        is_active=True,
    )
    return JsonResponse(
        {
            "api_version": API_VERSION,
            "chart_schema_version": CHART_SCHEMA_VERSION,
            "generated_at": timezone.now().isoformat(),
            "area": serialize_area(area, include_detail=True),
        },
        json_dumps_params={"ensure_ascii": False},
    )


@api_key_required
def latest_comment(request):
    area_slug = request.GET.get("area", "").strip()
    try:
        limit = int(request.GET.get("limit", "1"))
    except ValueError:
        limit = 1
    limit = max(1, min(limit, 20))
    comments = OmsuLatestComment.objects.select_related("area").filter(area__is_active=True)
    if area_slug:
        comments = comments.filter(area__slug=area_slug)
    latest = list(comments.order_by("-published_at", "-received_at")[:limit])
    serialized = [serialize_comment(comment) for comment in latest]
    return JsonResponse(
        {
            "api_version": API_VERSION,
            "served_at": timezone.now().isoformat(),
            "comment_refresh_seconds": settings.OMSU_API_COMMENT_REFRESH_SECONDS,
            "comment": serialized[0] if serialized else None,
            "comments": serialized,
        },
        json_dumps_params={"ensure_ascii": False},
    )
