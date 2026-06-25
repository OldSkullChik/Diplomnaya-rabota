from __future__ import annotations

import html
import re
from datetime import timedelta
from urllib.parse import urlparse

from django.utils import timezone


MONTHS_RU = {
    "янв": 1,
    "января": 1,
    "фев": 2,
    "февраля": 2,
    "мар": 3,
    "марта": 3,
    "апр": 4,
    "апреля": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июня": 6,
    "июл": 7,
    "июля": 7,
    "авг": 8,
    "августа": 8,
    "сен": 9,
    "сентября": 9,
    "окт": 10,
    "октября": 10,
    "ноя": 11,
    "ноября": 11,
    "дек": 12,
    "декабря": 12,
}

NUMBER_WORDS_RU = {
    "одна": 1,
    "один": 1,
    "одно": 1,
    "две": 2,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
}

MOJIBAKE_MARKERS = ("Р", "С", "Ѓ", "Њ", "Ћ", "Џ", "В«", "В»", "в„", "ў")


SERVICE_TEXT_PATTERNS = [
    r"\bпоказать полностью\b",
    r"\bпоказать ещё\b",
    r"\bпоказать еще\b",
    r"\bответить\b",
    r"\bподелиться\b",
    r"\bлайк\b",
    r"\bнравится\b",
    r"\bпросмотров?\b",
    r"\bгеолокация\b",
    r"\b\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430\b",
    r"\d+\s*/\s*\d+",
    r"\d+\s+просмотров?",
    r"\d+\s+\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430",
]

COMMENT_DATE_LINE_RE = re.compile(
    r"^(?:сегодня|вчера)\s+в\s+\d{1,2}:\d{2}$"
    r"|^\d{1,2}\s+[а-яё]+(?:\s+\d{4})?(?:\s+в\s+\d{1,2}:\d{2})?$",
    flags=re.I,
)

COMMENT_SERVICE_LINES = {
    "показать все комментарии",
    "показать следующие комментарии",
    "показать предыдущие комментарии",
    "ответить",
    "лайк",
    "нравится",
}

PERSON_NAME_LINE_RE = re.compile(
    r"^[А-ЯЁ][а-яё]{1,24}(?:\s+[А-ЯЁ][а-яё]{1,24}){1,2}$"
)


def mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def repair_mojibake(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    try:
        repaired = text.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return text
    if mojibake_score(repaired) < mojibake_score(text):
        return repaired
    return text


def clean_vk_text(value: str) -> str:
    text = html.unescape(repair_mojibake(str(value or "")))
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = []
    skip_next_small_number = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(re.fullmatch(pattern, lowered, flags=re.I) for pattern in SERVICE_TEXT_PATTERNS):
            if lowered in {"лайк", "нравится"}:
                skip_next_small_number = True
            continue
        if skip_next_small_number and re.fullmatch(r"\d{1,5}", lowered):
            skip_next_small_number = False
            continue
        skip_next_small_number = False
        lines.append(stripped)
    return "\n".join(lines).strip()


def clean_ticker_comment_text(value: str, *, author_name: str = "", max_length: int = 420) -> str:
    text = clean_vk_text(value)
    author = clean_vk_text(author_name).strip().lower()
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = []
    for stripped in raw_lines:
        lowered = stripped.lower()
        if author and lowered == author:
            continue
        if looks_like_person_name(stripped):
            continue
        if lowered in COMMENT_SERVICE_LINES:
            continue
        if COMMENT_DATE_LINE_RE.fullmatch(lowered):
            continue
        if re.fullmatch(r"\d{1,5}", stripped):
            continue
        lines.append(stripped)
    cleaned = "\n".join(lines).strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1].rstrip() + "…"
    return cleaned


def looks_like_person_name(value: str) -> bool:
    text = value.strip()
    if not PERSON_NAME_LINE_RE.fullmatch(text):
        return False
    service_words = {"Добрый", "Доброе", "Здравствуйте", "Админ", "Анонимно"}
    return not any(word in service_words for word in text.split())


def screen_name_from_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    path = parsed.path.strip("/")
    if not path:
        return ""
    return path.split("/")[0]


def absolute_vk_url(base_url: str, href: str) -> str:
    href = str(href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    base = base_url.rstrip("/")
    if href.startswith("/"):
        return base + href
    return base + "/" + href


def wall_id_from_url(url: str) -> str:
    match = re.search(r"wall(-?\d+_\d+)", str(url or ""))
    return match.group(1) if match else ""


def reply_id_from_url(url: str) -> str:
    text = str(url or "")
    match = re.search(r"(?:reply=|_r)(\d+)", text)
    return match.group(1) if match else ""


def parse_vk_datetime(value: str, now=None):
    raw = clean_vk_text(value).lower()
    if not raw:
        return None
    now = now or timezone.now()
    tz = timezone.get_current_timezone()

    if "только что" in raw or raw in {"сейчас", "now"}:
        return now

    minute_match = re.search(r"(\d+)\s*(?:м|мин|минут)", raw)
    if minute_match and "назад" in raw:
        return now - timedelta(minutes=int(minute_match.group(1)))
    word_minute_match = re.search(
        r"\b(" + "|".join(NUMBER_WORDS_RU) + r")\s+(?:м|мин|минута|минуты|минут)\s+назад\b",
        raw,
    )
    if word_minute_match:
        return now - timedelta(minutes=NUMBER_WORDS_RU[word_minute_match.group(1)])

    if re.search(r"\bчас назад\b", raw):
        return now - timedelta(hours=1)
    hour_match = re.search(r"(\d+)\s*(?:ч|час|часа|часов)", raw)
    if hour_match and "назад" in raw:
        return now - timedelta(hours=int(hour_match.group(1)))
    word_hour_match = re.search(
        r"\b(" + "|".join(NUMBER_WORDS_RU) + r")\s+(?:ч|час|часа|часов)\s+назад\b",
        raw,
    )
    if word_hour_match:
        return now - timedelta(hours=NUMBER_WORDS_RU[word_hour_match.group(1)])

    hm = re.search(r"(\d{1,2}):(\d{2})", raw)
    if "сегодня" in raw and hm:
        return now.replace(hour=int(hm.group(1)), minute=int(hm.group(2)), second=0, microsecond=0)
    if "вчера" in raw and hm:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=int(hm.group(1)), minute=int(hm.group(2)), second=0, microsecond=0)

    date_match = re.search(
        r"(\d{1,2})\s+([а-яё.]+)(?:\s+(\d{4}))?(?:\s+в\s+(\d{1,2}):(\d{2}))?",
        raw,
    )
    if date_match:
        day = int(date_match.group(1))
        month_name = date_match.group(2).rstrip(".")
        month = MONTHS_RU.get(month_name)
        if month:
            year = int(date_match.group(3) or now.year)
            hour = int(date_match.group(4) or 0)
            minute = int(date_match.group(5) or 0)
            parsed = timezone.datetime(year, month, day, hour, minute, tzinfo=tz)
            if parsed > now + timedelta(days=2) and not date_match.group(3):
                parsed = parsed.replace(year=year - 1)
            return parsed

    dot_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?", raw)
    if dot_match:
        day = int(dot_match.group(1))
        month = int(dot_match.group(2))
        year = int(dot_match.group(3))
        if year < 100:
            year += 2000
        hour = int(dot_match.group(4) or 0)
        minute = int(dot_match.group(5) or 0)
        return timezone.datetime(year, month, day, hour, minute, tzinfo=tz)

    return None
