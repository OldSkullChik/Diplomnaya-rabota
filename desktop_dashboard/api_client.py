from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE = os.environ.get("OMSU_API_BASE", "http://127.0.0.1:8000/api/v1/omsu")
DEFAULT_API_KEY = os.environ.get("OMSU_API_KEY", "").strip()


class ApiClientError(RuntimeError):
    pass


@dataclass
class ApiClient:
    base_url: str = DEFAULT_API_BASE
    api_key: str = DEFAULT_API_KEY
    timeout: float = 4.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.api_key = (self.api_key or "").strip()

    def get_json(self, path: str, params: dict[str, str] | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-OMSU-API-Key"] = self.api_key
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise ApiClientError(str(exc)) from exc

    def manifest(self) -> dict:
        return self.get_json("manifest/")

    def snapshot(self) -> dict:
        return self.get_json("snapshot/")

    def area_detail(self, slug: str) -> dict:
        return self.get_json(f"areas/{slug}/")

    def latest_comment(self, area_slug: str | None = None) -> dict:
        params = {"area": area_slug} if area_slug else None
        return self.get_json("latest-comment/", params=params)


def fallback_snapshot() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    areas = [
        {
            "slug": "nizhny-novgorod",
            "name": "Нижний Новгород",
            "area_type": "городской округ",
            "score": -34,
            "previous_score": -41,
            "score_color": "#c95326",
            "negative_probability": 0.72,
            "confidence_band": "low_confidence",
            "comments_total": 2440,
            "comments_last_day": 124,
            "negative_total": 1190,
            "neutral_total": 840,
            "positive_total": 410,
            "top_topics": [["Канализация", 38], ["Дворы", 27], ["Мусор", 19], ["Отопление", 16]],
            "geometry": {"type": "Polygon", "coordinates": [[430, 225], [560, 210], [615, 280], [585, 355], [470, 370], [405, 300]]},
            "latest_comment": {"text": "Демо: жалоба на запах канализации и сроки реакции служб.", "area_name": "Нижний Новгород", "omsu_score": -34},
        },
        {
            "slug": "dzherzhinsk",
            "name": "Дзержинск",
            "area_type": "городской округ",
            "score": -18,
            "previous_score": -22,
            "score_color": "#da8226",
            "negative_probability": 0.58,
            "confidence_band": "low_confidence",
            "comments_total": 1840,
            "comments_last_day": 82,
            "negative_total": 760,
            "neutral_total": 730,
            "positive_total": 350,
            "top_topics": [["Вода", 44], ["Отопление", 25], ["Дворы", 18], ["Мусор", 13]],
            "geometry": {"type": "Polygon", "coordinates": [[275, 265], [405, 245], [430, 330], [365, 405], [255, 385], [230, 310]]},
            "latest_comment": {"text": "Демо: вопросы по напору воды после ремонтных работ.", "area_name": "Дзержинск", "omsu_score": -18},
        },
        {
            "slug": "bor",
            "name": "Бор",
            "area_type": "городской округ",
            "score": 12,
            "previous_score": 4,
            "score_color": "#acc646",
            "negative_probability": 0.21,
            "confidence_band": "low_confidence",
            "comments_total": 1580,
            "comments_last_day": 64,
            "negative_total": 420,
            "neutral_total": 790,
            "positive_total": 370,
            "top_topics": [["Благоустройство", 36], ["Дворы", 31], ["Мусор", 22], ["Вода", 11]],
            "geometry": {"type": "Polygon", "coordinates": [[455, 95], [610, 115], [655, 205], [560, 210], [430, 225], [395, 145]]},
            "latest_comment": {"text": "Демо: отмечают уборку снега на центральных улицах.", "area_name": "Бор", "omsu_score": 12},
        },
        {
            "slug": "kstovo",
            "name": "Кстовский округ",
            "area_type": "муниципальный округ",
            "score": -63,
            "previous_score": -57,
            "score_color": "#a92727",
            "negative_probability": 0.91,
            "confidence_band": "high_negative",
            "comments_total": 2140,
            "comments_last_day": 141,
            "negative_total": 1320,
            "neutral_total": 610,
            "positive_total": 210,
            "top_topics": [["Мусор", 52], ["Дворы", 20], ["Власть", 16], ["Другое ЖКХ", 12]],
            "geometry": {"type": "Polygon", "coordinates": [[585, 355], [735, 325], [805, 425], [715, 515], [570, 480], [525, 405]]},
            "latest_comment": {"text": "Демо: поток жалоб на переполненные контейнерные площадки.", "area_name": "Кстовский округ", "omsu_score": -63},
        },
        {
            "slug": "arzamas",
            "name": "Арзамас",
            "area_type": "городской округ",
            "score": 28,
            "previous_score": 19,
            "score_color": "#7fb646",
            "negative_probability": 0.12,
            "confidence_band": "high_not_negative",
            "comments_total": 1340,
            "comments_last_day": 58,
            "negative_total": 260,
            "neutral_total": 620,
            "positive_total": 460,
            "top_topics": [["Мусор", 46], ["Благоустройство", 28], ["Дворы", 16], ["Тарифы", 10]],
            "geometry": {"type": "Polygon", "coordinates": [[320, 455], [470, 430], [570, 480], [535, 570], [380, 585], [295, 525]]},
            "latest_comment": {"text": "Демо: обсуждают новые правила вывоза растительных отходов.", "area_name": "Арзамас", "omsu_score": 28},
        },
    ]
    return {
        "api_version": "fallback",
        "generated_at": now,
        "snapshot_refresh_seconds": 3600,
        "comment_refresh_seconds": 5,
        "map": {"bounds": [0, 0, 1000, 620], "focus_region": "Нижегородская область"},
        "areas": areas,
        "widgets": {
            "main": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
            "spare": ["negative_probability", "comment_volume", "responsible_parties", "quality_mix"],
        },
    }
