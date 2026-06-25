from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QMimeData,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QTimer,
    Qt,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QDrag, QFont, QImage, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from .api_client import DEFAULT_API_BASE, DEFAULT_API_KEY, ApiClient, ApiClientError
except ImportError:  # pragma: no cover - allows direct script execution
    from api_client import DEFAULT_API_BASE, DEFAULT_API_KEY, ApiClient, ApiClientError


CHART_TITLES = {
    "score_trend": "Динамика оценки ОМСУ",
    "topic_distribution": "Темы ЖКХ",
    "sentiment_balance": "Баланс тональности",
    "appeal_types": "Типы обращений",
    "negative_probability": "Вероятность негатива",
    "comment_volume": "Объем комментариев",
    "responsible_parties": "Ответственные стороны",
    "quality_mix": "Качество сообщений",
}

CHART_MIME = "application/x-omsu-chart-key"
DASHBOARD_VERSION = "0.5.5"
ASSET_DIR = Path(__file__).resolve().parent / "assets"
GEODATA_DIR = Path(__file__).resolve().parent / "assets" / "geodata"
STATIC_SNAPSHOT_PATH = ASSET_DIR / "static_dashboard_snapshot.json"

MONITORING_OBJECT_NAMES = {
    "ardatov": "Ардатовский округ",
    "arzamas": "Арзамас",
    "arzamas-district": "Арзамасский округ",
    "balakhna": "Балахнинский округ",
    "bogorodsk": "Богородский округ",
    "bolshoe-boldino": "Большеболдинский округ",
    "bolshoe-murashkino": "Большемурашкинский округ",
    "bor": "городской округ Бор",
    "buturlino": "Бутурлинский округ",
    "chkalovsk": "Чкаловский округ",
    "dalnee-konstantinovo": "Дальнеконстантиновский округ",
    "diveevo": "Дивеевский округ",
    "dzerzhinsk": "Дзержинск",
    "gagino": "Гагинский округ",
    "gorodets": "Городецкий округ",
    "knyaginino": "Княгининский округ",
    "kovernino": "Ковернинский округ",
    "krasnye-baki": "Краснобаковский округ",
    "krasny-oktyabr": "Краснооктябрьский округ",
    "kstovo": "Кстовский округ",
    "kulebaki": "Кулебакский округ",
    "lukoyanov": "Лукояновский округ",
    "lyskovo": "Лысковский округ",
    "navashino": "Навашинский округ",
    "nizhny-novgorod": "Нижний Новгород",
    "pavlovo": "Павловский округ",
    "perevoz": "Перевозский округ",
    "pervomaysk": "Первомайский округ",
    "pilna": "Пильнинский округ",
    "pochinki": "Починковский округ",
    "sarov": "Саров",
    "sechenovo": "Сеченовский округ",
    "semenov": "Семёновский округ",
    "sergach": "Сергачский округ",
    "shakhunya": "городской округ Шахунья",
    "sharanga": "Шарангский округ",
    "shatki": "Шатковский округ",
    "sokolskoye": "Сокольский округ",
    "sosnovskoe": "Сосновский округ",
    "spasskoe": "Спасский округ",
    "tonkino": "Тонкинский округ",
    "tonshaevo": "Тоншаевский округ",
    "uren": "Уренский округ",
    "vacha": "Вачский округ",
    "vad": "Вадский округ",
    "varnavino": "Варнавинский округ",
    "vetluga": "Ветлужский округ",
    "volodarsk": "Володарский округ",
    "vorotynets": "Воротынский округ",
    "voskresenskoe": "Воскресенский округ",
    "voznesenskoe": "Вознесенский округ",
    "vyksa": "городской округ Выкса",
}

MONITORING_MAP_LABELS = {
    "ardatov": "АРДАТОВ",
    "arzamas": "АРЗАМАС",
    "arzamas-district": "АРЗАМАССКИЙ",
    "balakhna": "БАЛАХНА",
    "bogorodsk": "БОГОРОДСК",
    "bolshoe-boldino": "БОЛЬШОЕ БОЛДИНО",
    "bolshoe-murashkino": "БОЛЬШОЕ МУРАШКИНО",
    "bor": "БОР",
    "buturlino": "БУТУРЛИНО",
    "chkalovsk": "ЧКАЛОВСК",
    "dalnee-konstantinovo": "ДАЛЬНЕЕ КОНСТАНТИНОВО",
    "diveevo": "ДИВЕЕВО",
    "dzerzhinsk": "ДЗЕРЖИНСК",
    "gagino": "ГАГИНО",
    "gorodets": "ГОРОДЕЦ",
    "knyaginino": "КНЯГИНИНО",
    "kovernino": "КОВЕРНИНО",
    "krasnye-baki": "КРАСНЫЕ БАКИ",
    "krasny-oktyabr": "КРАСНЫЙ ОКТЯБРЬ",
    "kstovo": "КСТОВО",
    "kulebaki": "КУЛЕБАКИ",
    "lukoyanov": "ЛУКОЯНОВ",
    "lyskovo": "ЛЫСКОВО",
    "navashino": "НАВАШИНО",
    "nizhny-novgorod": "НИЖНИЙ НОВГОРОД",
    "pavlovo": "ПАВЛОВО",
    "perevoz": "ПЕРЕВОЗ",
    "pervomaysk": "ПЕРВОМАЙСК",
    "pilna": "ПИЛЬНА",
    "pochinki": "ПОЧИНКИ",
    "sarov": "САРОВ",
    "sechenovo": "СЕЧЕНОВО",
    "semenov": "СЕМЁНОВ",
    "sergach": "СЕРГАЧ",
    "shakhunya": "ШАХУНЬЯ",
    "sharanga": "ШАРАНГА",
    "shatki": "ШАТКИ",
    "sokolskoye": "СОКОЛЬСКОЕ",
    "sosnovskoe": "СОСНОВСКОЕ",
    "spasskoe": "СПАССКОЕ",
    "tonkino": "ТОНКИНО",
    "tonshaevo": "ТОНШАЕВО",
    "uren": "УРЕНЬ",
    "vacha": "ВАЧА",
    "vad": "ВАД",
    "varnavino": "ВАРНАВИНО",
    "vetluga": "ВЕТЛУГА",
    "volodarsk": "ВОЛОДАРСК",
    "vorotynets": "ВОРОТЫНЕЦ",
    "voskresenskoe": "ВОСКРЕСЕНСКОЕ",
    "voznesenskoe": "ВОЗНЕСЕНСКОЕ",
    "vyksa": "ВЫКСА",
}

MONITORING_CENTER_COORDS = {
    "ardatov": (43.096, 55.238),
    "arzamas": (43.839, 55.395),
    "arzamas-district": (43.839, 55.395),
    "balakhna": (43.602, 56.494),
    "bogorodsk": (43.515, 56.102),
    "bolshoe-boldino": (45.314, 55.005),
    "bolshoe-murashkino": (44.775, 55.782),
    "bor": (44.064, 56.358),
    "buturlino": (44.896, 55.566),
    "chkalovsk": (43.244, 56.767),
    "dalnee-konstantinovo": (44.096, 55.808),
    "diveevo": (43.241, 55.043),
    "dzerzhinsk": (43.461, 56.238),
    "gagino": (45.033, 55.231),
    "gorodets": (43.473, 56.644),
    "knyaginino": (45.035, 55.820),
    "kovernino": (43.815, 57.129),
    "krasnye-baki": (45.159, 57.131),
    "krasny-oktyabr": (45.617, 55.405),
    "kstovo": (44.208, 56.151),
    "kulebaki": (42.512, 55.429),
    "lukoyanov": (44.493, 55.032),
    "lyskovo": (45.041, 56.032),
    "navashino": (42.196, 55.543),
    "nizhny-novgorod": (44.006, 56.327),
    "pavlovo": (43.071, 55.964),
    "perevoz": (44.544, 55.596),
    "pervomaysk": (43.802, 54.867),
    "pilna": (45.921, 55.555),
    "pochinki": (44.866, 54.697),
    "sarov": (43.344, 54.935),
    "sechenovo": (45.890, 55.224),
    "semenov": (44.490, 56.789),
    "sergach": (45.467, 55.532),
    "shakhunya": (46.612, 57.675),
    "sharanga": (46.534, 57.177),
    "shatki": (44.127, 55.188),
    "sokolskoye": (43.158, 57.144),
    "sosnovskoe": (43.167, 55.805),
    "spasskoe": (45.696, 55.863),
    "tonkino": (46.462, 57.372),
    "tonshaevo": (47.013, 57.736),
    "uren": (45.785, 57.464),
    "vacha": (42.771, 55.803),
    "vad": (44.209, 55.530),
    "varnavino": (45.091, 57.403),
    "vetluga": (45.781, 57.856),
    "volodarsk": (43.188, 56.226),
    "vorotynets": (45.863, 56.061),
    "voskresenskoe": (45.432, 56.839),
    "voznesenskoe": (42.756, 54.890),
    "vyksa": (42.174, 55.320),
}

RUSSIA_SCENE_BOUNDS = [0, 0, 1200, 720]
RUSSIA_OUTLINE = [
    (35, 185),
    (100, 155),
    (185, 168),
    (280, 145),
    (395, 158),
    (475, 132),
    (570, 150),
    (660, 130),
    (770, 160),
    (890, 152),
    (1010, 190),
    (1160, 205),
    (1125, 278),
    (1020, 300),
    (930, 345),
    (820, 332),
    (710, 370),
    (575, 360),
    (488, 395),
    (362, 370),
    (285, 415),
    (190, 392),
    (130, 430),
    (72, 395),
    (112, 330),
    (72, 278),
    (118, 238),
]
RUSSIA_FAR_EAST = [
    (1025, 330),
    (1118, 356),
    (1150, 428),
    (1082, 502),
    (1010, 470),
    (1002, 388),
]
RUSSIA_SAKHALIN = [(1090, 500), (1124, 545), (1112, 615), (1074, 574)]
NIZHNY_REGION_MARKER = [
    (248, 326),
    (286, 313),
    (324, 333),
    (316, 374),
    (268, 384),
    (232, 360),
]


class GeoProjector:
    def __init__(
        self,
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        width: float,
        height: float,
        margin: float,
        wrap_negative_lon: bool = False,
    ):
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.width = width
        self.height = height
        self.margin = margin
        self.wrap_negative_lon = wrap_negative_lon

    @property
    def usable_width(self) -> float:
        return max(1.0, self.width - self.margin * 2)

    @property
    def usable_height(self) -> float:
        return max(1.0, self.height - self.margin * 2)

    def point(self, lon: float, lat: float) -> QPointF:
        if self.wrap_negative_lon and lon < 0:
            lon += 360
        x = self.margin + ((lon - self.lon_min) / max(self.lon_max - self.lon_min, 1e-6)) * self.usable_width
        y = self.margin + ((self.lat_max - lat) / max(self.lat_max - self.lat_min, 1e-6)) * self.usable_height
        return QPointF(x, y)


def load_geojson_asset(name: str) -> dict | None:
    path = GEODATA_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def geometry_rings(geometry: dict) -> list[list[list[float]]]:
    if not geometry:
        return []
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    rings = []
    if geom_type == "Polygon":
        for ring in coordinates[:1]:
            rings.append(ring)
    elif geom_type == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon[:1]:
                rings.append(ring)
    return rings


def split_antimeridian_ring(ring: list[list[float]]) -> list[list[list[float]]]:
    if not ring:
        return []
    segments = [[]]
    previous_lon = None
    for point in ring:
        lon, lat = float(point[0]), float(point[1])
        if previous_lon is not None and abs(lon - previous_lon) > 180 and len(segments[-1]) > 1:
            segments.append([])
        segments[-1].append([lon, lat])
        previous_lon = lon
    return [segment for segment in segments if len(segment) >= 3]


def projected_polygons(geometry: dict, projector: GeoProjector, stride: int = 1) -> list[QPolygonF]:
    polygons = []
    for ring in geometry_rings(geometry):
        segments = [ring] if projector.wrap_negative_lon else split_antimeridian_ring(ring)
        for segment in segments:
            sampled = segment[::stride]
            if segment[-1] not in sampled:
                sampled.append(segment[-1])
            if len(sampled) < 3:
                continue
            polygons.append(QPolygonF([projector.point(lon, lat) for lon, lat in sampled]))
    return polygons


def geojson_bounds(data: dict, wrap_negative_lon: bool = False) -> tuple[float, float, float, float] | None:
    lon_values: list[float] = []
    lat_values: list[float] = []

    def visit(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            lon = float(coords[0])
            if wrap_negative_lon and lon < 0:
                lon += 360
            lon_values.append(lon)
            lat_values.append(float(coords[1]))
            return
        for item in coords:
            visit(item)

    for feature in data.get("features", []):
        visit((feature.get("geometry") or {}).get("coordinates") or [])
    if not lon_values or not lat_values:
        return None
    return min(lon_values), max(lon_values), min(lat_values), max(lat_values)


def feature_collection_bounds(features: list[dict]) -> tuple[float, float, float, float] | None:
    return geojson_bounds({"type": "FeatureCollection", "features": features})


def geometry_centroid(geometry: dict, projector: GeoProjector | None = None) -> QPointF | None:
    lon_values: list[float] = []
    lat_values: list[float] = []

    def visit(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            lon_values.append(float(coords[0]))
            lat_values.append(float(coords[1]))
            return
        for item in coords:
            visit(item)

    visit((geometry or {}).get("coordinates") or [])
    if not lon_values or not lat_values:
        return None
    lon = sum(lon_values) / len(lon_values)
    lat = sum(lat_values) / len(lat_values)
    if projector:
        return projector.point(lon, lat)
    return QPointF(lon, lat)


def load_monitoring_groups() -> dict:
    path = Path(__file__).resolve().parent / "assets" / "monitoring_groups.json"
    if not path.exists():
        return {"objects": []}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_nizhny_monitoring_features() -> list[dict]:
    data = load_geojson_asset("nizhny_monitored_adm2.geojson")
    if not data:
        return []
    return data.get("features", [])


def load_static_snapshot() -> dict:
    if STATIC_SNAPSHOT_PATH.exists():
        return json.loads(STATIC_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    return {
        "api_version": "static-local",
        "generated_at": "2026-06-15T00:00:00+03:00",
        "snapshot_refresh_seconds": 3600,
        "comment_refresh_seconds": 5,
        "map": {"bounds": [0, 0, 1000, 620], "focus_region": "Нижегородская область"},
        "areas": [],
        "widgets": {
            "main": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
            "spare": ["negative_probability", "comment_volume", "responsible_parties", "quality_mix"],
        },
    }


def monitoring_display_name(slug: str, fallback: str = "") -> str:
    return MONITORING_OBJECT_NAMES.get(slug) or fallback or slug


def map_label_text(slug: str, name: str) -> str:
    return MONITORING_MAP_LABELS.get(slug) or name.upper()


def center_label_text(slug: str, name: str) -> str:
    return map_label_text(slug, name).title()


def qcolor_from_hex(value: str, fallback: QColor | None = None) -> QColor:
    color = QColor(value)
    if color.isValid():
        return color
    return fallback or QColor("#d6b34a")


def mix_color(left: QColor, right: QColor, ratio: float) -> QColor:
    clamped = max(0.0, min(1.0, ratio))
    return QColor(
        round(left.red() + (right.red() - left.red()) * clamped),
        round(left.green() + (right.green() - left.green()) * clamped),
        round(left.blue() + (right.blue() - left.blue()) * clamped),
    )



def school_grade_from_score(score) -> int:
    """Convert internal OMSU score (-100..100) to a visual school grade (2..5).

    The conversion is only for display in the left territory card.
    Internal charts, colors, trends and calculations continue to use the raw -100..100 score.

    2: -100..-60
    3:  -59..-25
    4:  -24..+24
    5:  +25..+100
    """
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0.0

    if value <= -60:
        return 2
    if value <= -25:
        return 3
    if value <= 24:
        return 4
    return 5


def school_grade_text(score) -> str:
    return str(school_grade_from_score(score))

def score_color(score: int) -> QColor:
    clamped = max(-100, min(100, int(score or 0)))
    ratio = (clamped + 100) / 200
    if ratio < 0.5:
        local = ratio / 0.5
        return mix_color(QColor("#9f3f3a"), QColor("#c4a750"), local)
    local = (ratio - 0.5) / 0.5
    return mix_color(QColor("#c4a750"), QColor("#5f9853"), local)


def territory_brush(color: QColor, rect: QRectF) -> QBrush:
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, color.lighter(128))
    gradient.setColorAt(0.45, color.lighter(104))
    gradient.setColorAt(1.0, color.darker(132))
    return QBrush(gradient)


def offset_polygon(polygon: QPolygonF, dx: float, dy: float) -> QPolygonF:
    return QPolygonF([QPointF(point.x() + dx, point.y() + dy) for point in polygon])


def polygon_visual_area(polygon: QPolygonF) -> float:
    rect = polygon.boundingRect()
    return max(0.0, rect.width() * rect.height())


def largest_polygon(polygons: list[QPolygonF]) -> QPolygonF | None:
    if not polygons:
        return None
    return max(polygons, key=polygon_visual_area)


def label_point_for_polygon(polygon: QPolygonF) -> QPointF:
    rect = polygon.boundingRect()
    center = rect.center()
    if polygon.containsPoint(center, Qt.FillRule.OddEvenFill):
        return center
    best_point = center
    best_distance = float("inf")
    for row in range(1, 6):
        for column in range(1, 6):
            point = QPointF(rect.left() + rect.width() * column / 6, rect.top() + rect.height() * row / 6)
            if not polygon.containsPoint(point, Qt.FillRule.OddEvenFill):
                continue
            distance = (point.x() - center.x()) ** 2 + (point.y() - center.y()) ** 2
            if distance < best_distance:
                best_point = point
                best_distance = distance
    return best_point


def center_point_for_area(slug: str, polygon: QPolygonF, projector: GeoProjector) -> QPointF:
    coords = MONITORING_CENTER_COORDS.get(slug)
    if coords:
        lon, lat = coords
        point = projector.point(lon, lat)
        if polygon.containsPoint(point, Qt.FillRule.OddEvenFill):
            return point
    return label_point_for_polygon(polygon)


def polygon_orientation_degrees(polygon: QPolygonF) -> float:
    points = [polygon[index] for index in range(polygon.count())]
    if len(points) < 3:
        return 0.0
    mean_x = sum(point.x() for point in points) / len(points)
    mean_y = sum(point.y() for point in points) / len(points)
    xx = sum((point.x() - mean_x) ** 2 for point in points)
    yy = sum((point.y() - mean_y) ** 2 for point in points)
    xy = sum((point.x() - mean_x) * (point.y() - mean_y) for point in points)
    angle = math.degrees(0.5 * math.atan2(2 * xy, xx - yy)) if xx or yy else 0.0
    if angle > 70:
        angle -= 180
    if angle < -70:
        angle += 180
    return max(-62.0, min(62.0, angle))


def wrapped_map_label(text: str, rect: QRectF) -> str:
    words = [word for word in text.split() if word]
    compact_len = len(text.replace(" ", ""))
    should_wrap = len(words) > 1 and (compact_len >= 12 or max(rect.width(), rect.height()) < compact_len * 7)
    if not should_wrap:
        return text
    best_index = 1
    best_balance = float("inf")
    for index in range(1, len(words)):
        left = " ".join(words[:index])
        right = " ".join(words[index:])
        balance = abs(len(left.replace(" ", "")) - len(right.replace(" ", "")))
        if balance < best_balance:
            best_index = index
            best_balance = balance
    return " ".join(words[:best_index]) + "\n" + " ".join(words[best_index:])


def label_font_size(text: str, rect: QRectF) -> int:
    lines = [line for line in text.splitlines() if line] or [text]
    compact_len = max(4, max(len(line.replace(" ", "")) for line in lines))
    long_side = max(rect.width(), rect.height())
    short_side = max(1.0, min(rect.width(), rect.height()))
    by_width = long_side / (compact_len * 0.72)
    by_height = short_side / (len(lines) * 1.55)
    return max(4, min(15, round(min(by_width, by_height))))


def center_label_font_size(text: str, rect: QRectF) -> int:
    lines = [line for line in text.splitlines() if line] or [text]
    compact_len = max(4, max(len(line.replace(" ", "")) for line in lines))
    long_side = max(rect.width(), rect.height())
    by_width = long_side / (compact_len * 0.95)
    return max(7, min(12, round(by_width)))


def add_strategy_label(scene: QGraphicsScene, text: str, point: QPointF, rect: QRectF, angle: float):
    text = wrapped_map_label(text, rect)
    font = QFont("Arial", center_label_font_size(text, rect), QFont.Weight.Bold)
    item = QGraphicsSimpleTextItem(text)
    item.setFont(font)
    item.setBrush(QColor(11, 18, 32, 246))
    item.setPen(QPen(QColor(255, 252, 232, 230), max(0.42, font.pointSizeF() * 0.045)))
    item.setOpacity(0.98)
    item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
    item.setZValue(84)
    bounds = item.boundingRect()
    item.setTransformOriginPoint(bounds.center())
    item.setRotation(0)
    place_label_near_center(item, point, rect)
    scene.addItem(item)
    return item


def place_label_near_center(item: QGraphicsSimpleTextItem, point: QPointF, rect: QRectF):
    bounds = item.boundingRect()
    gap = 7.0
    prefer_left = point.x() > rect.center().x()
    x = point.x() - bounds.width() - gap if prefer_left else point.x() + gap
    y = point.y() - bounds.height() / 2
    x = max(rect.left() + 2, min(x, rect.right() - bounds.width() - 2))
    y = max(rect.top() + 2, min(y, rect.bottom() - bounds.height() - 2))
    item.setPos(x, y)


def add_polygon_shadow(scene: QGraphicsScene, polygon: QPolygonF, opacity: int = 58):
    shadow = QGraphicsPolygonItem(offset_polygon(polygon, 2.0, 3.0))
    shadow.setBrush(QColor(2, 6, 23, opacity))
    shadow.setPen(QPen(Qt.PenStyle.NoPen))
    shadow.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
    shadow.setZValue(0)
    scene.addItem(shadow)
    return shadow


def chart_values(chart_data):
    if not chart_data:
        return []
    if all(isinstance(item, (int, float)) for item in chart_data):
        return [(str(index + 1), float(value)) for index, value in enumerate(chart_data)]
    values = []
    for item in chart_data:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            values.append((str(item[0]), float(item[1])))
    return values


class AreaPolygonItem(QGraphicsPolygonItem):
    def __init__(self, area: dict, polygon: QPolygonF, on_selected):
        super().__init__(polygon)
        self.area = area
        self.on_selected = on_selected
        self.is_selected = False
        self.base_color = qcolor_from_hex(area.get("score_color", ""), score_color(area.get("score", 0)))
        self.normal_pen = QPen(QColor(12, 18, 26, 145), 0.42)
        self.hover_pen = QPen(QColor(248, 250, 252, 210), 0.72)
        self.selected_pen = QPen(QColor(252, 211, 77, 235), 1.16)
        for pen in [self.normal_pen, self.hover_pen, self.selected_pen]:
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setBrush(territory_brush(self.base_color, polygon.boundingRect()))
        self.setPen(self.normal_pen)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(self.tooltip_text())
        self.setZValue(1)
        self.setTransformOriginPoint(polygon.boundingRect().center())
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)

    def tooltip_text(self) -> str:
        latest = self.area.get("latest_comment") or {}
        return (
            f"{self.area.get('name', '')}\n"
            f"Оценка ОМСУ: {self.area.get('score', 0):+d}\n"
            f"Прошлая оценка: {self.area.get('previous_score', 0):+d}\n"
            f"Комментариев за сутки: {self.area.get('comments_last_day', 0)}\n"
            f"{latest.get('text', '')}"
        )

    def hoverEnterEvent(self, event):
        self.setScale(1.028 if self.is_selected else 1.0)
        self.setZValue(72 if self.is_selected else 24)
        self.setBrush(territory_brush(self.base_color.lighter(112), self.polygon().boundingRect()))
        self.setPen(self.hover_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.018 if self.is_selected else 1.0)
        self.setZValue(70 if self.is_selected else 1)
        brush_color = self.base_color.lighter(110) if self.is_selected else self.base_color
        self.setBrush(territory_brush(brush_color, self.polygon().boundingRect()))
        self.setPen(self.selected_pen if self.is_selected else self.normal_pen)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_selected(self.area)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.setScale(1.018 if selected else 1.0)
        self.setZValue(70 if selected else 1)
        brush_color = self.base_color.lighter(110) if selected else self.base_color
        self.setBrush(territory_brush(brush_color, self.polygon().boundingRect()))
        self.setPen(self.selected_pen if selected else self.normal_pen)
        if selected:
            effect = QGraphicsDropShadowEffect()
            effect.setBlurRadius(26)
            effect.setOffset(0, 10)
            effect.setColor(QColor(0, 0, 0, 150))
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)


class AreaMarkerItem(QGraphicsEllipseItem):
    def __init__(self, area: dict, center: QPointF, on_selected):
        size = 6
        super().__init__(-size / 2, -size / 2, size, size)
        self.area = area
        self.on_selected = on_selected
        self.is_selected = False
        self.normal_brush = QColor("#d72020")
        self.selected_brush = QColor("#f97316")
        self.hover_brush = QColor("#ff3b30")
        self.setBrush(self.normal_brush)
        self.setPen(QPen(QColor(255, 255, 248, 230), 0.85))
        self.setOpacity(0.96)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setPos(center)
        self.setToolTip(
            f"{area.get('name', '')}\n"
            f"Групп мониторинга: {area.get('monitoring_group_count', 0)}\n"
            "Нажмите, чтобы открыть аналитику"
        )
        self.setZValue(88)

    def hoverEnterEvent(self, event):
        self.setScale(1.65)
        self.setOpacity(1.0)
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.18 if self.is_selected else 1.0)
        self.setOpacity(1.0 if self.is_selected else 0.96)
        self.setBrush(self.selected_brush if self.is_selected else self.normal_brush)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_selected(self.area)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.setVisible(not selected)
        self.setScale(1.0)
        self.setOpacity(0.96)
        self.setBrush(self.normal_brush)
        self.setZValue(88)


class RussiaRegionItem(QGraphicsPolygonItem):
    def __init__(self, slug: str, name: str, polygon: QPolygonF, on_selected):
        super().__init__(polygon)
        self.slug = slug
        self.name = name
        self.on_selected = on_selected
        self.base_color = QColor("#4f8cc9")
        self.setBrush(territory_brush(self.base_color, polygon.boundingRect()))
        self.setPen(QPen(QColor(255, 255, 255, 220), 1.25))
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{name}\nНажмите, чтобы открыть мониторинг региона")
        self.setTransformOriginPoint(polygon.boundingRect().center())
        self.setZValue(10)
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)

    def hoverEnterEvent(self, event):
        self.setScale(1.035)
        self.setBrush(territory_brush(self.base_color.lighter(118), self.polygon().boundingRect()))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.0)
        self.setBrush(territory_brush(self.base_color, self.polygon().boundingRect()))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_selected(self.slug)
        super().mousePressEvent(event)


class MapView(QGraphicsView):
    area_selected = pyqtSignal(dict)
    region_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#eef2f4"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setMinimumWidth(520)
        self.areas: list[dict] = []
        self.area_items: dict[str, list[AreaPolygonItem]] = {}
        self.area_markers: dict[str, AreaMarkerItem] = {}
        self.area_labels: dict[str, list[QGraphicsSimpleTextItem]] = {}
        self.baked_labels_item: QGraphicsPixmapItem | None = None
        self.region_items: dict[str, RussiaRegionItem] = {}
        self.selected_slug: str | None = None
        self.mode = "russia"
        self.map_content_rect: QRectF | None = None
        self.camera_bounds_rect: QRectF | None = None
        self.full_map_scale = 1.0
        self.min_zoom_scale = 0.05
        self.max_zoom_scale = 20.0
        self.pan_start: QPoint | None = None
        self.pan_last: QPoint | None = None
        self.pan_dragged = False
        self.camera_animation: QVariantAnimation | None = None
        self.navigation_restore_timer = QTimer(self)
        self.navigation_restore_timer.setSingleShot(True)
        self.navigation_restore_timer.timeout.connect(self.restore_navigation_quality)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)

    def add_text(self, text: str, x: float, y: float, size: int, weight: QFont.Weight = QFont.Weight.Normal, color="#111827"):
        item = self.scene.addText(text)
        item.setDefaultTextColor(QColor(color))
        item.setFont(QFont("Arial", size, weight))
        item.setPos(x, y)
        return item

    def set_russia_overview(self):
        self.mode = "russia"
        self.scene.clear()
        self.area_items.clear()
        self.area_markers.clear()
        self.area_labels.clear()
        self.baked_labels_item = None
        self.region_items.clear()
        self.selected_slug = None
        self.map_content_rect = None
        self.camera_bounds_rect = None
        self.scene.setSceneRect(*RUSSIA_SCENE_BOUNDS)
        self.setBackgroundBrush(QColor("#152437"))

        if not self.draw_russia_geodata():
            self.draw_russia_fallback()
        QTimer.singleShot(0, self.fit_full_map)

    def draw_russia_geodata(self) -> bool:
        adm1 = load_geojson_asset("rus_adm1_simplified.geojson")
        if not adm1:
            return False
        bounds = geojson_bounds(adm1, wrap_negative_lon=True)
        if not bounds:
            return False
        lon_min, lon_max, lat_min, lat_max = bounds
        projector = GeoProjector(
            lon_min,
            lon_max,
            lat_min,
            lat_max,
            RUSSIA_SCENE_BOUNDS[2],
            RUSSIA_SCENE_BOUNDS[3],
            48,
            wrap_negative_lon=True,
        )

        content_rect: QRectF | None = None
        for feature in adm1.get("features", []):
            props = feature.get("properties", {})
            iso = props.get("shapeISO", "")
            name = props.get("shapeName", "")
            geometry = feature.get("geometry") or {}
            is_nizhny = iso == "RU-NIZ" or name == "Nizhny Novgorod Oblast"
            polygons = projected_polygons(geometry, projector, stride=2 if not is_nizhny else 1)
            for polygon in polygons:
                content_rect = polygon.boundingRect() if content_rect is None else content_rect.united(polygon.boundingRect())
                if is_nizhny:
                    add_polygon_shadow(self.scene, polygon, opacity=72)
                    item = RussiaRegionItem("nizhny-novgorod-region", "Нижегородская область", polygon, self.region_selected.emit)
                    self.region_items[item.slug] = item
                else:
                    item = QGraphicsPolygonItem(polygon)
                    fill = QColor("#73838a") if len(name) % 3 else QColor("#677982")
                    item.setBrush(territory_brush(fill, polygon.boundingRect()))
                    item.setPen(QPen(QColor(13, 24, 38, 115), 0.45))
                    item.setToolTip(name)
                    item.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
                    item.setZValue(1)
                self.scene.addItem(item)

        self.map_content_rect = content_rect
        return bool(self.region_items)

    def draw_russia_fallback(self):
        content_rect: QRectF | None = None
        for points, color, z_value in [
            (RUSSIA_OUTLINE, QColor("#d9e4ea"), 1),
            (RUSSIA_FAR_EAST, QColor("#d1e0e7"), 1),
            (RUSSIA_SAKHALIN, QColor("#d1e0e7"), 1),
        ]:
            item = QGraphicsPolygonItem(QPolygonF([QPointF(x, y) for x, y in points]))
            item.setBrush(territory_brush(color, item.boundingRect()))
            item.setPen(QPen(QColor("#263342"), 0.8))
            item.setZValue(z_value)
            self.scene.addItem(item)
            content_rect = item.boundingRect() if content_rect is None else content_rect.united(item.boundingRect())

        marker = RussiaRegionItem(
            "nizhny-novgorod-region",
            "Нижегородская область",
            QPolygonF([QPointF(x, y) for x, y in NIZHNY_REGION_MARKER]),
            self.region_selected.emit,
        )
        self.scene.addItem(marker)
        self.region_items[marker.slug] = marker
        self.map_content_rect = content_rect

    def set_areas(self, areas: list[dict], bounds: list[int] | None = None):
        self.mode = "region"
        self.scene.clear()
        self.area_items.clear()
        self.area_markers.clear()
        self.area_labels.clear()
        self.baked_labels_item = None
        self.region_items.clear()
        self.map_content_rect = None
        self.camera_bounds_rect = None
        self.selected_slug = None
        self.areas = areas
        geojson_areas = [area for area in areas if area.get("geojson_geometry")]
        if geojson_areas and self.draw_region_geodata(geojson_areas):
            return

        bounds = bounds or [0, 0, 1000, 620]
        self.scene.setSceneRect(bounds[0], bounds[1], bounds[2], bounds[3])
        self.setBackgroundBrush(QColor("#eef2f4"))

        title = self.scene.addText("Нижегородская область")
        title.setDefaultTextColor(QColor("#111827"))
        title.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        title.setPos(28, 24)

        subtitle = self.scene.addText("цвет района зависит от оценки ОМСУ: -100 красный, +100 зеленый")
        subtitle.setDefaultTextColor(QColor("#475569"))
        subtitle.setFont(QFont("Arial", 10))
        subtitle.setPos(30, 58)

        for area in areas:
            coordinates = (area.get("geometry") or {}).get("coordinates") or []
            polygon = QPolygonF([QPointF(float(x), float(y)) for x, y in coordinates])
            item = AreaPolygonItem(area, polygon, self.area_selected.emit)
            self.scene.addItem(item)
            self.area_items.setdefault(area.get("slug", ""), []).append(item)
            self.map_content_rect = polygon.boundingRect() if self.map_content_rect is None else self.map_content_rect.united(polygon.boundingRect())

        if self.selected_slug:
            self.focus_area(self.selected_slug)
        QTimer.singleShot(0, self.fit_full_map)

    def draw_region_geodata(self, areas: list[dict]) -> bool:
        features = [{"type": "Feature", "geometry": area.get("geojson_geometry"), "properties": {}} for area in areas]
        bounds = feature_collection_bounds(features)
        if not bounds:
            return False
        lon_min, lon_max, lat_min, lat_max = bounds
        self.scene.setSceneRect(0, 0, 1000, 620)
        self.setBackgroundBrush(QColor("#070b10"))
        projector = GeoProjector(lon_min, lon_max, lat_min, lat_max, 1000, 620, 34)
        content_rect: QRectF | None = None

        for area in areas:
            polygons = projected_polygons(area.get("geojson_geometry") or {}, projector, stride=1)
            if not polygons:
                continue
            slug = area.get("slug", "")
            for polygon in polygons:
                content_rect = polygon.boundingRect() if content_rect is None else content_rect.united(polygon.boundingRect())
                add_polygon_shadow(self.scene, polygon)
                item = AreaPolygonItem(area, polygon, self.area_selected.emit)
                if area.get("monitoring_group_count", 0) <= 0:
                    item.setOpacity(0.72)
                    item.setPen(QPen(QColor(148, 163, 184, 125), 0.75))
                self.scene.addItem(item)
                self.area_items.setdefault(slug, []).append(item)

            main_polygon = largest_polygon(polygons)
            if main_polygon:
                label_rect = main_polygon.boundingRect()
                label_point = center_point_for_area(slug, main_polygon, projector)
                label_angle = polygon_orientation_degrees(main_polygon)
                label = add_strategy_label(self.scene, center_label_text(slug, area.get("name", "")), label_point, label_rect, label_angle)
                self.area_labels.setdefault(slug, []).append(label)
                marker = AreaMarkerItem(area, label_point, self.area_selected.emit)
                self.scene.addItem(marker)
                self.area_markers[slug] = marker

        self.map_content_rect = content_rect
        self.build_baked_label_layer()
        if self.selected_slug:
            self.focus_area(self.selected_slug)
        QTimer.singleShot(0, self.fit_full_map)
        return bool(self.area_items)

    def fit_full_map(self):
        if self.scene.sceneRect().isNull() or not self.viewport().width() or not self.viewport().height():
            return
        if self.mode == "region" and self.selected_slug:
            self.focus_area(self.selected_slug, animated=False)
            return
        target_rect = self.full_map_target_rect()
        self.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.full_map_scale = max(0.01, self.transform().m11())
        self.min_zoom_scale = self.full_map_scale * (0.90 if self.mode == "region" else 0.82)
        self.max_zoom_scale = self.full_map_scale * (6.0 if self.mode == "region" else 3.5)
        self.clamp_camera_to_bounds()

    def full_map_target_rect(self) -> QRectF:
        content_rect = self.map_content_rect or self.scene.itemsBoundingRect() or self.scene.sceneRect()
        if content_rect.isNull():
            content_rect = self.scene.sceneRect()
        bound_pad_x = max(80.0, content_rect.width() * 0.10)
        bound_pad_y = max(70.0, content_rect.height() * 0.12)
        self.camera_bounds_rect = content_rect.adjusted(-bound_pad_x, -bound_pad_y, bound_pad_x, bound_pad_y)
        self.scene.setSceneRect(self.camera_bounds_rect)
        if self.mode == "russia":
            return content_rect.adjusted(-10, -10, 10, 10)
        return content_rect.adjusted(-18, -18, 18, 18)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_full_map()

    def focus_area(self, slug: str, animated: bool = True):
        self.selected_slug = slug
        items = self.area_items.get(slug)
        if not items:
            return
        for area_slug, area_items in self.area_items.items():
            for area_item in area_items:
                area_item.set_selected(area_slug == slug)
        for area_slug, marker in self.area_markers.items():
            marker.set_selected(area_slug == slug)
        self.update_label_focus(slug)
        target_rect = self.area_focus_rect(items)
        if animated:
            self.animate_to_rect(target_rect)
        else:
            self.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.clamp_camera_to_bounds()

    def update_label_focus(self, selected_slug: str | None):
        if self.baked_labels_item:
            self.baked_labels_item.setVisible(not selected_slug)
        for area_slug, labels in self.area_labels.items():
            for label in labels:
                is_selected = bool(selected_slug and area_slug == selected_slug)
                label.setVisible(is_selected)
                label.setOpacity(0.96 if is_selected else 0.82)
                label.setZValue(95 if is_selected else 80)

    def build_baked_label_layer(self):
        all_labels = [label for labels in self.area_labels.values() for label in labels]
        if not all_labels:
            return
        scene_rect = self.scene.sceneRect()
        if scene_rect.isNull():
            return
        factor = 4.0
        image = QImage(
            max(1, int(scene_rect.width() * factor)),
            max(1, int(scene_rect.height() * factor)),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)

        label_scene = QGraphicsScene()
        label_scene.setSceneRect(scene_rect)
        for label in all_labels:
            clone = QGraphicsSimpleTextItem(label.text())
            clone.setFont(label.font())
            clone.setBrush(label.brush())
            clone.setPen(label.pen())
            clone.setOpacity(label.opacity())
            clone.setPos(label.pos())
            clone.setTransformOriginPoint(label.transformOriginPoint())
            clone.setRotation(label.rotation())
            clone.setZValue(label.zValue())
            label_scene.addItem(clone)
            label.setVisible(False)

        painter = QPainter(image)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        label_scene.render(painter, QRectF(0, 0, image.width(), image.height()), scene_rect)
        painter.end()

        pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
        pixmap_item.setPos(scene_rect.topLeft())
        pixmap_item.setScale(1 / factor)
        pixmap_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        pixmap_item.setZValue(82)
        self.scene.addItem(pixmap_item)
        self.baked_labels_item = pixmap_item

    def set_navigation_fast_mode(self):
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for labels in self.area_labels.values():
            for label in labels:
                label.setVisible(False)
        self.navigation_restore_timer.start(140)

    def restore_navigation_quality(self):
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.update_label_focus(self.selected_slug)

    def clear_area_selection(self, animated: bool = False):
        self.selected_slug = None
        for area_items in self.area_items.values():
            for area_item in area_items:
                area_item.set_selected(False)
        for marker in self.area_markers.values():
            marker.setVisible(True)
            marker.set_selected(False)
        self.update_label_focus(None)
        target_rect = self.full_map_target_rect()
        if animated:
            self.animate_to_rect(target_rect, duration=680)
        else:
            self.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.clamp_camera_to_bounds()

    def area_focus_rect(self, items: list[AreaPolygonItem]) -> QRectF:
        rect: QRectF | None = None
        for item in items:
            item_rect = item.sceneBoundingRect()
            rect = item_rect if rect is None else rect.united(item_rect)
        rect = rect or self.scene.sceneRect()
        content_rect = self.map_content_rect or self.scene.itemsBoundingRect() or self.scene.sceneRect()
        pad_x = max(38.0, rect.width() * 0.28)
        pad_y = max(32.0, rect.height() * 0.32)
        target = rect.adjusted(-pad_x, -pad_y, pad_x, pad_y)
        min_width = max(170.0, content_rect.width() * 0.28)
        min_height = max(130.0, content_rect.height() * 0.28)
        if target.width() < min_width:
            delta = (min_width - target.width()) / 2
            target.adjust(-delta, 0, delta, 0)
        if target.height() < min_height:
            delta = (min_height - target.height()) / 2
            target.adjust(0, -delta, 0, delta)
        return target

    def current_view_rect(self) -> QRectF:
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def clamp_camera_to_bounds(self):
        bounds = self.camera_bounds_rect or self.scene.sceneRect()
        if bounds.isNull():
            return
        visible = self.current_view_rect()
        center = visible.center()
        if visible.width() < bounds.width():
            if visible.left() < bounds.left():
                center.setX(center.x() + (bounds.left() - visible.left()))
            elif visible.right() > bounds.right():
                center.setX(center.x() - (visible.right() - bounds.right()))
        else:
            center.setX(bounds.center().x())
        if visible.height() < bounds.height():
            if visible.top() < bounds.top():
                center.setY(center.y() + (bounds.top() - visible.top()))
            elif visible.bottom() > bounds.bottom():
                center.setY(center.y() - (visible.bottom() - bounds.bottom()))
        else:
            center.setY(bounds.center().y())
        if center != visible.center():
            self.centerOn(center)

    def animate_to_rect(self, target_rect: QRectF, duration: int = 520):
        if self.camera_animation:
            self.camera_animation.stop()
        start_rect = self.current_view_rect()
        self.camera_animation = QVariantAnimation(self)
        self.camera_animation.setStartValue(start_rect)
        self.camera_animation.setEndValue(target_rect)
        self.camera_animation.setDuration(duration)
        self.camera_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.camera_animation.valueChanged.connect(
            lambda rect: (self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio), self.clamp_camera_to_bounds())
        )
        self.camera_animation.start()

    def wheelEvent(self, event):
        if self.scene.sceneRect().isNull():
            super().wheelEvent(event)
            return
        current_scale = max(0.001, self.transform().m11())
        wheel_delta = event.angleDelta().y()
        if wheel_delta == 0:
            event.ignore()
            return
        zoom_factor = 1.16 if wheel_delta > 0 else 1 / 1.16
        target_scale = max(self.min_zoom_scale, min(self.max_zoom_scale, current_scale * zoom_factor))
        real_factor = target_scale / current_scale
        if abs(real_factor - 1.0) < 0.002:
            event.accept()
            return
        self.set_navigation_fast_mode()
        old_anchor = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(real_factor, real_factor)
        self.setTransformationAnchor(old_anchor)
        self.clamp_camera_to_bounds()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton}:
            self.pan_start = event.position().toPoint()
            self.pan_last = self.pan_start
            self.pan_dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pan_start is None or self.pan_last is None:
            super().mouseMoveEvent(event)
            return
        pos = event.position().toPoint()
        if not self.pan_dragged and (pos - self.pan_start).manhattanLength() < 7:
            event.accept()
            return
        self.pan_dragged = True
        self.set_navigation_fast_mode()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        delta = pos - self.pan_last
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        self.pan_last = pos
        self.clamp_camera_to_bounds()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.pan_start is not None and event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton}:
            was_dragged = self.pan_dragged
            release_pos = event.position().toPoint()
            self.pan_start = None
            self.pan_last = None
            self.pan_dragged = False
            self.unsetCursor()
            if not was_dragged and event.button() == Qt.MouseButton.LeftButton:
                self.handle_map_click(release_pos)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def handle_map_click(self, view_pos: QPoint):
        for item in self.items(view_pos):
            if isinstance(item, AreaMarkerItem) or isinstance(item, AreaPolygonItem):
                self.area_selected.emit(item.area)
                return
            if isinstance(item, RussiaRegionItem):
                self.region_selected.emit(item.slug)
                return

    def animate_to_region(self, region_slug: str, finished):
        item = self.region_items.get(region_slug)
        if not item:
            finished()
            return
        start_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        target_rect = item.sceneBoundingRect().adjusted(-110, -90, 110, 90)
        self.camera_animation = QVariantAnimation(self)
        self.camera_animation.setStartValue(start_rect)
        self.camera_animation.setEndValue(target_rect)
        self.camera_animation.setDuration(850)
        self.camera_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.camera_animation.valueChanged.connect(
            lambda rect: (self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio), self.clamp_camera_to_bounds())
        )
        self.camera_animation.finished.connect(finished)
        self.camera_animation.start()


class MiniChart(QWidget):
    def __init__(self, chart_key: str, compact: bool = False):
        super().__init__()
        self.chart_key = chart_key
        self.compact = compact
        self.data = []
        self.raw_data = []
        self.setMinimumHeight(52 if compact else 150)

    def set_data(self, data):
        self.raw_data = data or []
        self.data = chart_values(data)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.data:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "нет данных")
            return

        # PyQt6 is strict about QRect (integer geometry) vs QRectF (floating-point geometry).
        # MiniChart calculations use floats, so keep the drawing area as QRectF.
        base_rect = self.rect().adjusted(7, 7, -7, -7) if self.compact else self.rect().adjusted(12, 10, -12, -34)
        rect = QRectF(base_rect)
        if self.chart_key in {"negative_probability", "coverage_ratio"}:
            self.draw_gauge(painter, rect)
            return
        if self.chart_key in {"sentiment_balance", "quality_mix", "decision_mix"} and len(self.data) > 1:
            self.draw_donut(painter, rect)
            return
        if self.chart_key in {"score_trend", "comment_volume"}:
            self.draw_line(painter, rect)
            return
        self.draw_bars(painter, rect)
        return

        values = [value for _, value in self.data]
        min_value = min(values + [0])
        max_value = max(values + [1])
        span = max(max_value - min_value, 1)
        width = rect.width()
        height = rect.height()

        if self.chart_key in {"score_trend", "comment_volume"}:
            points = []
            for index, (_, value) in enumerate(self.data):
                x = rect.left() + (width * index / max(len(self.data) - 1, 1))
                y = rect.bottom() - ((value - min_value) / span) * height
                points.append(QPointF(x, y))
            painter.setPen(QPen(QColor("#2563eb"), 3))
            for index in range(len(points) - 1):
                painter.drawLine(points[index], points[index + 1])
            painter.setBrush(QColor("#2563eb"))
            for point in points:
                painter.drawEllipse(point, 4, 4)
        else:
            gap = 8
            bar_width = max(10, (width - gap * (len(self.data) - 1)) / len(self.data))
            colors = [QColor("#dc2626"), QColor("#eab308"), QColor("#16a34a"), QColor("#2563eb"), QColor("#7c3aed")]
            for index, (label, value) in enumerate(self.data):
                bar_height = ((value - min_value) / span) * height if span else 0
                x = rect.left() + index * (bar_width + gap)
                y = rect.bottom() - bar_height
                painter.setBrush(colors[index % len(colors)])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(int(x), int(y), int(bar_width), int(max(bar_height, 2)), 4, 4)
                if self.compact:
                    continue
                painter.setPen(QColor("#111827"))
                painter.setFont(QFont("Arial", 8))
                text = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(bar_width))
                label_rect = QRectF(x, rect.bottom() + 6, bar_width, 30)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)


    def palette(self) -> list[QColor]:
        return [
            QColor("#dc2626"),
            QColor("#eab308"),
            QColor("#16a34a"),
            QColor("#2563eb"),
            QColor("#7c3aed"),
            QColor("#0891b2"),
        ]

    def draw_axis(self, painter: QPainter, rect: QRectF):
        painter.setPen(QPen(QColor("#e5e7eb"), 1))
        painter.drawLine(QPointF(float(rect.left()), float(rect.bottom())), QPointF(float(rect.right()), float(rect.bottom())))

    def draw_line(self, painter: QPainter, rect: QRectF):
        values = [value for _, value in self.data]
        if self.chart_key == "score_trend":
            min_value, max_value = -100, 100
        else:
            min_value = min(values + [0])
            max_value = max(values + [1])
        span = max(max_value - min_value, 1)
        self.draw_axis(painter, rect)
        painter.setPen(QPen(QColor("#eef2f7"), 1))
        for ratio in (0.25, 0.5, 0.75):
            y = rect.top() + rect.height() * ratio
            painter.drawLine(QPointF(float(rect.left()), float(y)), QPointF(float(rect.right()), float(y)))

        points = []
        for index, (_, value) in enumerate(self.data):
            x = rect.left() + (rect.width() * index / max(len(self.data) - 1, 1))
            y = rect.bottom() - ((value - min_value) / span) * rect.height()
            points.append(QPointF(x, y))
        painter.setPen(QPen(QColor("#2563eb"), 3 if not self.compact else 2))
        for index in range(len(points) - 1):
            painter.drawLine(points[index], points[index + 1])
        painter.setBrush(QColor("#2563eb"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        radius = 5 if not self.compact else 3
        for point in points:
            painter.drawEllipse(point, radius, radius)
        if not self.compact and values:
            painter.setPen(QColor("#334155"))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(rect.right() - 58, rect.top(), 58, 22), Qt.AlignmentFlag.AlignRight, f"{values[-1]:+.0f}")

    def draw_bars(self, painter: QPainter, rect: QRectF):
        values = [max(0.0, value) for _, value in self.data]
        max_value = max(values + [1])
        gap = 9 if not self.compact else 5
        bar_width = max(10, (rect.width() - gap * (len(self.data) - 1)) / len(self.data))
        colors = self.palette()
        self.draw_axis(painter, rect)
        painter.setFont(QFont("Arial", 8 if self.compact else 9))
        for index, (label, value) in enumerate(self.data):
            value = max(0.0, value)
            bar_height = (value / max_value) * rect.height() if max_value else 0
            x = rect.left() + index * (bar_width + gap)
            y = rect.bottom() - bar_height
            color = colors[index % len(colors)]
            gradient = QLinearGradient(QPointF(x, y), QPointF(x, rect.bottom()))
            gradient.setColorAt(0.0, color.lighter(112))
            gradient.setColorAt(1.0, color.darker(106))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(bar_height, 3)), 4, 4)
            if self.compact:
                continue
            painter.setPen(QColor("#111827"))
            painter.drawText(QRectF(x, max(rect.top(), y - 20), bar_width, 18), Qt.AlignmentFlag.AlignHCenter, f"{value:.0f}")
            text = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(bar_width + 6))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(QRectF(x - 3, rect.bottom() + 6, bar_width + 6, 26), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)

    def draw_gauge(self, painter: QPainter, rect: QRectF):
        value = self.data[0][1] if self.data else 0
        percent = max(0.0, min(100.0, value))
        if self.chart_key == "coverage_ratio" and isinstance(self.raw_data, dict):
            percent = max(0.0, min(100.0, float(self.raw_data.get("ratio", percent) or 0)))
        color = QColor("#16a34a") if percent < 35 else QColor("#eab308") if percent < 65 else QColor("#dc2626")
        track = rect.adjusted(4, rect.height() * 0.38, -4, -rect.height() * 0.38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e5e7eb"))
        painter.drawRoundedRect(track, 10, 10)
        fill = QRectF(track.left(), track.top(), track.width() * percent / 100.0, track.height())
        painter.setBrush(color)
        painter.drawRoundedRect(fill, 10, 10)
        if not self.compact:
            painter.setPen(QColor("#111827"))
            painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            painter.drawText(rect.adjusted(0, -8, 0, -track.height()), Qt.AlignmentFlag.AlignCenter, f"{percent:.0f}%")
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(rect.left(), track.bottom() + 7, rect.width(), 22), Qt.AlignmentFlag.AlignCenter, self.data[0][0])

    def draw_donut(self, painter: QPainter, rect: QRectF):
        values = [max(0.0, value) for _, value in self.data]
        total = sum(values)
        if total <= 0:
            self.draw_bars(painter, rect)
            return
        side = min(rect.width(), rect.height()) * (0.82 if not self.compact else 0.92)
        donut = QRectF(rect.center().x() - side / 2, rect.top() + (rect.height() - side) / 2, side, side)
        start = 90 * 16
        colors = self.palette()
        painter.setPen(Qt.PenStyle.NoPen)
        for index, value in enumerate(values):
            span = -round(value / total * 360 * 16)
            painter.setBrush(colors[index % len(colors)])
            painter.drawPie(donut, start, span)
            start += span
        inner = donut.adjusted(side * 0.24, side * 0.24, -side * 0.24, -side * 0.24)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(inner)
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Arial", 14 if not self.compact else 9, QFont.Weight.Bold))
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, str(int(total)))
        if self.compact:
            return
        legend_x = rect.left()
        legend_y = rect.bottom() + 5
        painter.setFont(QFont("Arial", 8))
        for index, (label, value) in enumerate(self.data[:3]):
            x = legend_x + index * max(74, rect.width() / 3)
            painter.setBrush(colors[index % len(colors)])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, legend_y + 4, 9, 9), 2, 2)
            painter.setPen(QColor("#111827"))
            text = painter.fontMetrics().elidedText(f"{label} {value:.0f}", Qt.TextElideMode.ElideRight, 70)
            painter.drawText(QRectF(x + 13, legend_y, 70, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class ChartCard(QFrame):
    def __init__(self, chart_key: str, compact: bool = False):
        super().__init__()
        self.chart_key = chart_key
        self.compact = compact
        self.drag_start: QPoint | None = None
        self.setAcceptDrops(False)
        self.setObjectName("compactChartCard" if compact else "chartCard")
        if compact:
            self.setFixedHeight(92)
        else:
            self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 7, 9, 7) if compact else layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4 if compact else 8)
        self.title = QLabel(CHART_TITLES.get(chart_key, chart_key))
        self.title.setObjectName("compactChartTitle" if compact else "chartTitle")
        self.title.setWordWrap(True)
        self.chart = MiniChart(chart_key, compact=compact)
        layout.addWidget(self.title)
        layout.addWidget(self.chart, 1)
        if compact:
            self.setToolTip("Перетащите карточку на главный экран")

    def set_data(self, data):
        self.chart.set_data(data)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.drag_start:
            return
        if (event.position().toPoint() - self.drag_start).manhattanLength() < 8:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(CHART_MIME, QByteArray(self.chart_key.encode("utf-8")))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)
        self.drag_start = None


class DropArea(QFrame):
    chart_dropped = pyqtSignal(str, str)

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(CHART_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        key = bytes(event.mimeData().data(CHART_MIME)).decode("utf-8")
        self.chart_dropped.emit(key, self.name)
        event.acceptProposedAction()


class SpareHeader(DropArea):
    def __init__(self):
        super().__init__("spare")
        self.expanded = False
        self.cards: list[ChartCard] = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.expand)

        self.setObjectName("spareHeader")
        self.setFixedHeight(42)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(14, 7, 14, 7)
        self.layout.setSpacing(10)
        self.label = QLabel("Панель дашборда: наведите на секунду, чтобы открыть запасные графики")
        self.label.setObjectName("headerLabel")
        self.label.setMinimumWidth(430)
        self.layout.addWidget(self.label)
        self.layout.addStretch(1)

    def enterEvent(self, event):
        self.timer.start(1000)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.timer.stop()
        if not self.underMouse():
            self.collapse()
        super().leaveEvent(event)

    def expand(self):
        self.expanded = True
        self.setFixedHeight(116)
        self.label.setText("Запасные графики: перетащите карточку на главный экран")
        for card in self.cards:
            card.show()

    def collapse(self):
        self.expanded = False
        self.setFixedHeight(42)
        self.label.setText("Панель дашборда: наведите на секунду, чтобы открыть запасные графики")
        for card in self.cards:
            card.hide()

    def set_spare_cards(self, keys: list[str], charts: dict):
        self.cards = []
        while self.layout.count() > 2:
            item = self.layout.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for key in keys:
            card = ChartCard(key, compact=True)
            card.setFixedWidth(188)
            card.set_data(charts.get(key, []))
            card.setVisible(self.expanded)
            self.cards.append(card)
            self.layout.insertWidget(self.layout.count() - 1, card)


class DashboardGrid(DropArea):
    def __init__(self):
        super().__init__("main")
        self.setObjectName("dashboardOverlay")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(16, 16, 16, 16)
        self.grid.setSpacing(14)

    def set_cards(self, keys: list[str], charts: dict):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for index, key in enumerate(keys[:4]):
            card = ChartCard(key)
            card.set_data(charts.get(key, []))
            self.grid.addWidget(card, index // 2, index % 2)
            card.show()
        self.grid.activate()


class InfoPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("infoPanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.image = QLabel("Территория")
        self.image.setObjectName("territoryImage")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumHeight(150)
        self.image.setWordWrap(True)

        self.title = QLabel("Выберите округ")
        self.title.setObjectName("areaTitle")
        self.title.setWordWrap(True)
        self.info = QLabel("Наведение покажет подсказку, клик откроет подробный дашборд.")
        self.info.setWordWrap(True)
        self.info.setObjectName("areaInfo")

        layout.addWidget(self.image)
        layout.addWidget(self.title)
        layout.addWidget(self.info)
        layout.addStretch(1)

    def set_area(self, area: dict):
        color = qcolor_from_hex(area.get("score_color", ""), score_color(area.get("score", 0)))
        self.image.setStyleSheet(
            f"background: {color.name()}; border: 1px solid #111827; border-radius: 8px; color: white; font-weight: 700;"
        )
        self.image.setText(f"{area.get('name', '')}\nОценка {school_grade_text(area.get('score', 0))}")
        detail_lines = [
            f"Тип: {area.get('area_type', 'муниципальное образование')}",
            f"Оценка: {school_grade_text(area.get('score', 0))}",
            f"Прошлая оценка: {school_grade_text(area.get('previous_score', 0))}",
            f"Комментариев всего: {area.get('comments_total', 0)}",
            f"За сутки: {area.get('comments_last_day', 0)}",
        ]
        if "monitoring_group_count" in area:
            detail_lines.append(f"Групп мониторинга: {area.get('monitoring_group_count', 0)}")
        if area.get("territory_area_km2"):
            detail_lines.append(f"Площадь: {area['territory_area_km2']} км²")
        if area.get("population"):
            detail_lines.append(f"Население: {area['population']:,}".replace(",", " "))
        if area.get("head_name"):
            detail_lines.append(area["head_name"])
        self.title.setText(area.get("name", ""))
        self.info.setText("\n".join(detail_lines))


class ScrollingTicker(QWidget):
    def __init__(self, text: str = ""):
        super().__init__()
        self._text = text
        self.offset = 0.0
        self.direction = 1.0
        self.pause_ticks = 28
        self.setObjectName("ticker")
        self.setMinimumHeight(52)
        self.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.advance_scroll)
        self.scroll_timer.start(33)

    def setText(self, text: str):
        text = str(text or "")
        if text == self._text:
            return
        self._text = text
        self.offset = 0.0
        self.direction = 1.0
        self.pause_ticks = 28
        self.update()

    def text(self) -> str:
        return self._text

    def content_height(self) -> int:
        width = max(80, self.width() - 36)
        metrics = self.fontMetrics()
        bounds = metrics.boundingRect(
            QRect(0, 0, width, 10000),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            self._text,
        )
        return max(metrics.height(), bounds.height())

    def advance_scroll(self):
        if not self.isVisible() or not self._text:
            return
        viewport_height = max(12, self.height() - 14)
        max_scroll = max(0.0, float(self.content_height() - viewport_height))
        if max_scroll <= 1:
            if self.offset:
                self.offset = 0.0
                self.update()
            return
        if self.pause_ticks > 0:
            self.pause_ticks -= 1
            return
        self.offset += self.direction * 0.55
        if self.offset >= max_scroll:
            self.offset = max_scroll
            self.direction = -1.0
            self.pause_ticks = 46
        elif self.offset <= 0:
            self.offset = 0.0
            self.direction = 1.0
            self.pause_ticks = 32
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#facc15"))
        painter.setPen(QPen(QColor("#eab308"), 1))
        painter.drawLine(0, 0, self.width(), 0)
        painter.setPen(QColor("#171717"))
        painter.setFont(self.font())
        text_rect = QRectF(18, 7 - self.offset, max(40, self.width() - 36), max(self.content_height(), self.height() - 14))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            self._text,
        )


class MapWorkspace(QWidget):
    region_back_requested = pyqtSignal(str)

    def __init__(self, map_view: MapView, info_panel: InfoPanel, dashboard: DashboardGrid, ticker: QLabel):
        super().__init__()
        self.map_view = map_view
        self.info_panel = info_panel
        self.dashboard = dashboard
        self.ticker = ticker

        self.map_view.setParent(self)
        self.info_panel.setParent(self)
        self.dashboard.setParent(self)
        self.ticker.setParent(self)

        self.back_target = "russia"
        self.back_button = QPushButton("← Россия", self)
        self.back_button.setObjectName("backButton")
        self.back_button.clicked.connect(self.handle_back_button)

        self.hint = QLabel("Выберите субъект на карте России", self)
        self.hint.setObjectName("mapHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analytics_visible = False
        self.panel_animations: list[QVariantAnimation] = []

        self.map_view.lower()
        self.set_overview_mode()

    def set_overview_mode(self):
        self.analytics_visible = False
        self.panel_animations.clear()
        self.info_panel.hide()
        self.dashboard.hide()
        self.back_button.hide()
        self.back_target = "russia"
        self.hint.show()
        self.hint.setText("Выберите субъект на карте России")
        self.ticker.setText("Карта России · выберите субъект для мониторинга ЖКХ и оценки ОМСУ")
        self.ticker.show()
        self.reposition_overlays()

    def set_region_map_mode(self):
        self.analytics_visible = False
        self.panel_animations.clear()
        self.info_panel.hide()
        self.dashboard.hide()
        self.back_button.show()
        self.back_target = "russia"
        self.back_button.setText("← Россия")
        self.hint.show()
        self.hint.setText("Выберите округ")
        self.ticker.setText("Нижегородская область · карта объектов мониторинга ЖКХ")
        self.ticker.show()
        self.reposition_overlays()

    def set_region_mode(self, animated: bool = False):
        self.analytics_visible = True
        self.info_panel.show()
        self.dashboard.show()
        self.back_button.show()
        self.back_target = "region"
        self.back_button.setText("← Область")
        self.hint.hide()
        self.ticker.show()
        self.reposition_overlays(animate_panels=animated)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.map_view.setGeometry(self.rect())
        self.map_view.lower()
        self.reposition_overlays()

    def target_geometries(self) -> tuple[QRect, QRect, QRect, QRect, QRect]:
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        ticker_height = 52

        hint_width = min(480, max(260, width - 48))

        panel_top = 62
        panel_bottom = ticker_height + 18
        available_height = max(360, height - panel_top - panel_bottom)
        info_width = 300
        dashboard_width = min(640, max(520, width // 2 - 36))

        ticker_rect = QRect(0, max(0, height - ticker_height), width, ticker_height)
        hint_rect = QRect((width - hint_width) // 2, 20, hint_width, 42)
        back_rect = QRect(18, 18, 118, 34)
        info_rect = QRect(18, panel_top, info_width, min(available_height, 560))
        dashboard_rect = QRect(
            max(info_width + 36, width - dashboard_width - 18),
            panel_top,
            dashboard_width,
            available_height,
        )
        return ticker_rect, hint_rect, back_rect, info_rect, dashboard_rect

    def reposition_overlays(self, animate_panels: bool = False):
        ticker_rect, hint_rect, back_rect, info_rect, dashboard_rect = self.target_geometries()

        self.map_view.lower()
        self.ticker.setGeometry(ticker_rect)
        self.hint.setGeometry(hint_rect)
        self.back_button.setGeometry(back_rect)

        if self.analytics_visible:
            if animate_panels:
                self.slide_widget(self.info_panel, QRect(-info_rect.width() - 24, info_rect.y(), info_rect.width(), info_rect.height()), info_rect)
                self.slide_widget(
                    self.dashboard,
                    QRect(self.width() + 24, dashboard_rect.y(), dashboard_rect.width(), dashboard_rect.height()),
                    dashboard_rect,
                )
            else:
                self.info_panel.setGeometry(info_rect)
                self.dashboard.setGeometry(dashboard_rect)
        self.info_panel.raise_()
        self.dashboard.raise_()
        self.back_button.raise_()
        self.hint.raise_()
        self.ticker.raise_()

    def slide_widget(self, widget: QWidget, start_rect: QRect, end_rect: QRect):
        self.map_view.lower()
        widget.setGeometry(start_rect)
        widget.show()
        widget.raise_()
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(430)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def move(value):
            progress = float(value)
            x = round(start_rect.x() + (end_rect.x() - start_rect.x()) * progress)
            y = round(start_rect.y() + (end_rect.y() - start_rect.y()) * progress)
            width = round(start_rect.width() + (end_rect.width() - start_rect.width()) * progress)
            height = round(start_rect.height() + (end_rect.height() - start_rect.height()) * progress)
            widget.setGeometry(x, y, width, height)

        animation.valueChanged.connect(move)
        animation.finished.connect(
            lambda: (
                widget.setGeometry(end_rect),
                widget.raise_(),
                self.map_view.lower(),
                self.panel_animations.remove(animation) if animation in self.panel_animations else None,
            )
        )
        self.panel_animations.append(animation)
        animation.start()
        QTimer.singleShot(animation.duration() + 40, lambda: (self.map_view.lower(), widget.setGeometry(end_rect), widget.raise_()))

    def handle_back_button(self):
        self.region_back_requested.emit(self.back_target)


class MainWindow(QMainWindow):
    def __init__(self, api_base: str | None = None, api_key: str | None = None, use_api: bool = False):
        super().__init__()
        self.use_api = use_api
        self.client = (
            ApiClient(api_base or DEFAULT_API_BASE, api_key=api_key if api_key is not None else DEFAULT_API_KEY)
            if use_api
            else None
        )
        self.snapshot_data: dict = {}
        self.areas: dict[str, dict] = {}
        self.selected_slug: str | None = None
        self.main_widgets: list[str] = []
        self.spare_widgets: list[str] = []
        self.current_charts: dict = {}

        self.setWindowTitle("Мониторинг ЖКХ и оценка ОМСУ")
        self.setMinimumSize(1180, 720)
        self.resize(1440, 900)

        self.header = SpareHeader()
        self.header.chart_dropped.connect(self.move_chart)
        self.map_view = MapView()
        self.map_view.area_selected.connect(self.select_area)
        self.map_view.region_selected.connect(self.open_region)
        self.info_panel = InfoPanel()
        self.dashboard = DashboardGrid()
        self.dashboard.chart_dropped.connect(self.move_chart)

        self.ticker = QLabel("Локальная статическая витрина готовится к загрузке")
        self.ticker.setObjectName("ticker")
        self.ticker.setMinimumHeight(34)
        self.workspace = MapWorkspace(self.map_view, self.info_panel, self.dashboard, self.ticker)
        self.workspace.region_back_requested.connect(self.handle_back_request)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.header)
        root_layout.addWidget(self.workspace, 1)
        self.setCentralWidget(root)
        self.apply_styles()
        self.statusBar().hide()

        self.snapshot_timer = QTimer(self)
        self.snapshot_timer.timeout.connect(self.load_snapshot)
        self.comment_timer = QTimer(self)
        self.comment_timer.timeout.connect(self.refresh_latest_comment)

        self.load_snapshot(initial=True)

    def apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #ffffff; color: #111827; font-family: Arial; }
            #spareHeader { background: #111827; border-bottom: 1px solid #0f172a; }
            #headerLabel { background: transparent; color: #f8fafc; font-size: 14px; font-weight: 700; }
            #mapHint {
                background: rgba(15, 23, 42, 0.86);
                color: #f8fafc;
                border: 1px solid rgba(148, 163, 184, 0.5);
                border-radius: 8px;
                font-size: 15px;
                font-weight: 800;
            }
            #backButton {
                background: rgba(15, 23, 42, 0.90);
                color: #ffffff;
                border: 1px solid rgba(148, 163, 184, 0.55);
                border-radius: 8px;
                font-size: 14px;
                font-weight: 800;
            }
            #backButton:hover { background: #1d4ed8; }
            #infoPanel {
                background: rgba(248, 250, 252, 0.94);
                border: 1px solid rgba(148, 163, 184, 0.55);
                border-radius: 10px;
            }
            #territoryImage { font-size: 22px; }
            #areaTitle { font-size: 22px; font-weight: 800; }
            #areaInfo { color: #334155; font-size: 14px; line-height: 1.35; }
            #dashboardOverlay {
                background: rgba(248, 250, 252, 0.90);
                border: 1px solid rgba(148, 163, 184, 0.45);
                border-radius: 10px;
            }
            #chartCard { background: #ffffff; border: 1px solid #d8dee8; border-radius: 8px; }
            #chartCard:hover { border: 1px solid #2563eb; }
            #chartTitle { font-size: 15px; font-weight: 800; color: #111827; }
            #compactChartCard { background: #ffffff; border: 1px solid #334155; border-radius: 6px; }
            #compactChartCard:hover { border: 1px solid #60a5fa; }
            #compactChartTitle { font-size: 12px; font-weight: 800; color: #111827; }
            #ticker {
                background: #facc15;
                color: #171717;
                font-size: 14px;
                font-weight: 700;
                padding-left: 14px;
                border-top: 1px solid #eab308;
            }
            """
        )

    def load_snapshot(self, initial: bool = False):
        previous_mode = getattr(self.map_view, "mode", "russia")
        previous_slug = self.selected_slug
        if self.use_api and self.client:
            try:
                self.snapshot_data = self.client.snapshot()
            except ApiClientError:
                self.snapshot_data = load_static_snapshot()
        else:
            self.snapshot_data = load_static_snapshot()

        self.areas = self.build_region_areas(self.snapshot_data.get("areas", []))

        widgets = self.snapshot_data.get("widgets", {})
        desktop_widgets = widgets.get("desktop") or {}
        self.main_widgets = list(
            desktop_widgets.get("primary")
            or widgets.get("main")
            or ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"]
        )
        self.spare_widgets = list(
            desktop_widgets.get("drawer")
            or widgets.get("spare")
            or ["negative_probability", "comment_volume", "responsible_parties", "quality_mix"]
        )

        snapshot_refresh = int(self.snapshot_data.get("snapshot_refresh_seconds") or 3600)
        comment_refresh = int(self.snapshot_data.get("comment_refresh_seconds") or 5)
        self.snapshot_timer.start(max(snapshot_refresh, 30) * 1000)
        self.comment_timer.start(max(comment_refresh, 1) * 1000)

        if initial or previous_mode == "russia":
            self.map_view.set_russia_overview()
            self.workspace.set_overview_mode()
            return

        bounds = self.snapshot_data.get("map", {}).get("bounds")
        self.map_view.set_areas(list(self.areas.values()), bounds=bounds)
        self.workspace.set_region_map_mode()
        if previous_slug and previous_slug in self.areas:
            self.selected_slug = previous_slug
            self.show_area_detail(self.areas[previous_slug], animated=False)

    def build_region_areas(self, api_areas: list[dict]) -> dict[str, dict]:
        api_by_slug = {area.get("slug"): area for area in api_areas if area.get("slug")}
        groups_payload = load_monitoring_groups()
        groups_by_slug = {
            item.get("slug"): item.get("groups", [])
            for item in groups_payload.get("objects", [])
            if item.get("slug")
        }
        features = load_nizhny_monitoring_features()
        if not features:
            return api_by_slug

        areas: dict[str, dict] = {}
        for index, feature in enumerate(features, start=1):
            props = feature.get("properties", {})
            slug = props.get("monitoringSlug") or props.get("shapeID") or f"area-{index}"
            base = dict(api_by_slug.get(slug, {}))
            display_name = monitoring_display_name(slug, props.get("displayName") or props.get("shapeName") or base.get("name") or slug)
            groups = groups_by_slug.get(slug, [])
            if not base:
                base = self.synthetic_area(slug, display_name, index, groups)
            base.update(
                {
                    "slug": slug,
                    "name": monitoring_display_name(slug, base.get("name") or display_name),
                    "shape_name": props.get("shapeName"),
                    "geojson_geometry": feature.get("geometry"),
                    "monitoring_groups": groups,
                    "monitoring_group_count": len(groups),
                    "is_monitoring_object": len(groups) > 0,
                    "display_order": index,
                }
            )
            if not base.get("head_name"):
                base["head_name"] = "Глава округа: требует подтверждения"
            areas[slug] = base
        return areas

    def synthetic_area(self, slug: str, name: str, index: int, groups: list[str]) -> dict:
        seed = sum(ord(char) for char in slug)
        score = ((seed * 37 + index * 19) % 181) - 90
        previous = max(-100, min(100, score + ((seed % 55) - 27)))
        negative = max(10, round(150 - score * 1.35 + len(groups) * 7))
        neutral = 34 + (seed % 34)
        positive = max(10, round(135 + score * 1.25 - len(groups) * 2))
        topic_leader = 76 + (seed % 38) + len(groups) * 2
        topic_second = 24 + (index % 17)
        topic_third = 10 + (seed % 12)
        topic_fourth = 4 + (len(groups) % 9)
        return {
            "slug": slug,
            "name": name,
            "area_type": "муниципальный объект мониторинга",
            "head_name": "Глава округа: требует подтверждения",
            "score": score,
            "previous_score": previous,
            "score_color": score_color(score).name(),
            "negative_probability": max(0.05, min(0.95, (100 - score) / 200)),
            "comments_total": negative + neutral + positive,
            "comments_last_day": 20 + (seed % 95),
            "negative_total": negative,
            "neutral_total": neutral,
            "positive_total": positive,
            "top_topics": [["ЖКХ", topic_leader], ["Вода", topic_second], ["Дворы", topic_third], ["Мусор", topic_fourth]],
            "latest_comment": {
                "text": f"Мониторинговый объект: {name}. Групп в списке: {len(groups)}.",
                "area_name": name,
                "omsu_score": score,
            },
        }

    def open_region(self, region_slug: str):
        def finish_open():
            bounds = self.snapshot_data.get("map", {}).get("bounds")
            self.selected_slug = None
            self.current_charts = {}
            self.map_view.set_areas(list(self.areas.values()), bounds=bounds)
            self.header.set_spare_cards(self.spare_widgets, {})
            self.workspace.set_region_map_mode()

        self.map_view.animate_to_region(region_slug, finish_open)

    def handle_back_request(self, target: str):
        if target == "region":
            self.back_to_region_map()
        else:
            self.back_to_russia()

    def back_to_region_map(self):
        self.selected_slug = None
        self.current_charts = {}
        self.header.set_spare_cards(self.spare_widgets, {})
        self.workspace.set_region_map_mode()
        self.map_view.clear_area_selection(animated=True)

    def back_to_russia(self):
        self.selected_slug = None
        self.current_charts = {}
        self.map_view.set_russia_overview()
        self.workspace.set_overview_mode()

    def select_area(self, area: dict):
        slug = area.get("slug")
        if not slug:
            return
        self.show_area_detail(area, animated=True)

    def show_area_detail(self, area: dict, animated: bool = True):
        slug = area.get("slug")
        if not slug:
            return
        self.selected_slug = slug
        detail_area = area
        if self.use_api and self.client:
            try:
                detail_area = {**area, **self.client.area_detail(slug).get("area", area)}
            except ApiClientError:
                detail_area = {**area, "charts": self.demo_charts_for_area(area)}
        else:
            detail_area = {**area, "charts": self.demo_charts_for_area(area)}
        self.areas[slug] = detail_area
        self.current_charts = detail_area.get("charts") or self.demo_charts_for_area(detail_area)
        self.info_panel.set_area(detail_area)
        self.dashboard.set_cards(self.main_widgets, self.current_charts)
        self.header.set_spare_cards(self.spare_widgets, self.current_charts)
        self.workspace.set_region_mode(animated=animated)
        self.map_view.focus_area(slug, animated=animated)
        QTimer.singleShot(520, lambda: self.workspace.reposition_overlays(False))
        QTimer.singleShot(560, self.refresh_latest_comment)

    def demo_charts_for_area(self, area: dict) -> dict:
        score = area.get("score", 0)
        previous = area.get("previous_score", 0)
        negative = area.get("negative_total", max(0, 100 - score))
        neutral = area.get("neutral_total", 80)
        positive = area.get("positive_total", max(0, 100 + score))
        seed = sum(ord(char) for char in str(area.get("slug", "")))
        if abs(score - previous) < 24:
            direction = 1 if score >= 0 else -1
            previous = max(-100, min(100, score - direction * (28 + seed % 18)))
        comments_last_day = int(area.get("comments_last_day", 40) or 40)
        comments_total = int(area.get("comments_total", 200) or 200)
        return {
            "score_trend": [previous, round((previous + score) / 2), score],
            "topic_distribution": area.get("top_topics") or [["ЖКХ", 1]],
            "sentiment_balance": [["Негатив", negative], ["Нейтрально", neutral], ["Позитив", positive]],
            "appeal_types": [["Жалобы", 82], ["Вопросы", 24], ["Просьбы", 13], ["Благодарности", 4]],
            "negative_probability": [["Вероятность", round(area.get("negative_probability", 0) * 100)]],
            "comment_volume": [max(6, comments_last_day // 3), max(12, comments_last_day), max(24, comments_total // 6), max(10, comments_last_day // 2)],
            "responsible_parties": [["Администрация", 78], ["УК/ТСЖ", 22], ["РСО", 12], ["ТКО", 5]],
            "quality_mix": [["Обычные", 90], ["Сложные", 8], ["Дубли", 2]],
        }

    def move_chart(self, key: str, target: str):
        if target == "spare":
            if key in self.main_widgets:
                self.main_widgets.remove(key)
            if key not in self.spare_widgets:
                self.spare_widgets.append(key)
        else:
            if key in self.spare_widgets:
                self.spare_widgets.remove(key)
            if key not in self.main_widgets:
                if len(self.main_widgets) >= 4:
                    moved = self.main_widgets.pop()
                    if moved not in self.spare_widgets:
                        self.spare_widgets.insert(0, moved)
                self.main_widgets.append(key)
        self.dashboard.set_cards(self.main_widgets, self.current_charts)
        self.header.set_spare_cards(self.spare_widgets, self.current_charts)

    def refresh_latest_comment(self):
        if self.map_view.mode == "russia":
            self.ticker.setText("Карта России · выберите субъект для мониторинга ЖКХ и оценки ОМСУ")
            return
        area_slug = self.selected_slug
        if self.use_api and self.client:
            try:
                payload = self.client.latest_comment(area_slug)
                comment = payload.get("comment")
            except ApiClientError:
                area = self.areas.get(area_slug or "", {})
                comment = area.get("latest_comment")
        else:
            area = self.areas.get(area_slug or "", {})
            comment = area.get("latest_comment")
        if not comment:
            if self.map_view.mode == "russia":
                self.ticker.setText("Карта России · выберите субъект для мониторинга ЖКХ и оценки ОМСУ")
            else:
                self.ticker.setText("Последний комментарий: данных пока нет")
            return
        area_name = comment.get("area_name") or self.areas.get(area_slug or "", {}).get("name", "")
        text = comment.get("text", "")
        score = comment.get("omsu_score", 0)
        self.ticker.setText(f"Последний комментарий · {area_name} · оценка {score:+d}: {text}")


def main():
    app = QApplication(sys.argv)
    env_use_api = os.environ.get("OMSU_DASHBOARD_USE_API", "").strip().lower() in {"1", "true", "yes", "on"}
    api_base = sys.argv[1] if len(sys.argv) > 1 else (DEFAULT_API_BASE if env_use_api else None)
    api_key = sys.argv[2] if len(sys.argv) > 2 else None
    window = MainWindow(api_base=api_base, api_key=api_key, use_api=bool(api_base))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
