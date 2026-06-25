#!/usr/bin/env python
"""Interpretable OMSU impact scoring from the existing taxonomy labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class OmsuScore:
    score: int
    impact_class: str
    negative_signal: str
    confidence_weight: float
    scope_weight: float
    reason: str


SENTIMENT_BASE = {
    "negative": -38.0,
    "mixed": -18.0,
    "neutral": 0.0,
    "positive": 34.0,
}

APPEAL_MODIFIER = {
    "complaint": -22.0,
    "demand": -16.0,
    "request": -10.0,
    "question": -7.0,
    "suggestion": -3.0,
    "opinion": 0.0,
    "info": 0.0,
    "other": 0.0,
    "gratitude": 28.0,
}

AUTHORITY_MODIFIER = {
    "no_action": -36.0,
    "poor_quality": -32.0,
    "slow_response": -24.0,
    "tariff_policy": -18.0,
    "communication": -12.0,
    "supervision": -10.0,
    "other": -8.0,
    "not_applicable": 0.0,
    "positive_feedback": 34.0,
}

RESPONSIBLE_SCOPE = {
    "local_administration": 1.0,
    "housing_inspection": 0.78,
    "unknown": 0.58,
    "waste_operator": 0.46,
    "resource_provider": 0.42,
    "management_company": 0.35,
    "specific_person": 0.30,
    "residents": 0.12,
    "not_applicable": 0.0,
}

TOPIC_SCOPE = {
    "public_authorities": 1.0,
    "yard_area": 0.86,
    "waste_cleaning": 0.78,
    "other_jkh": 0.58,
    "cold_water_sewerage": 0.55,
    "heating_hot_water": 0.55,
    "payments_tariffs": 0.48,
    "management_company": 0.40,
    "house_common_property": 0.35,
    "not_jkh": 0.0,
}

AUTHORITY_SCOPE = {
    "no_action": 1.0,
    "poor_quality": 0.95,
    "slow_response": 0.92,
    "communication": 0.78,
    "supervision": 0.78,
    "tariff_policy": 0.72,
    "positive_feedback": 0.85,
    "other": 0.55,
    "not_applicable": 0.0,
}

QUALITY_WEIGHT = {
    "normal": 1.0,
    "difficult": 0.55,
    "spam": 0.0,
    "duplicate": 0.0,
}


def clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def normalized_label(row: Mapping[str, str], name: str, prefix: str = "") -> str:
    return str(row.get(f"{prefix}{name}", "") or "").strip()


def score_to_impact_class(score: int) -> str:
    if score <= -60:
        return "strong_negative"
    if score <= -25:
        return "negative"
    if score >= 25:
        return "positive"
    return "neutral_or_no_impact"


def score_to_negative_signal(score: int) -> str:
    return "negative_omsu" if score <= -25 else "not_negative_omsu"


def calculate_omsu_score(row: Mapping[str, str], prefix: str = "") -> OmsuScore:
    relevance = normalized_label(row, "jkh_relevance", prefix)
    topic = normalized_label(row, "jkh_topic", prefix)
    authority = normalized_label(row, "authority_aspect", prefix)
    sentiment = normalized_label(row, "sentiment", prefix)
    appeal = normalized_label(row, "appeal_type", prefix)
    responsible = normalized_label(row, "responsible_party", prefix)
    sarcasm = normalized_label(row, "sarcasm", prefix)
    quality = normalized_label(row, "quality", prefix)

    reasons: list[str] = []
    quality_weight = QUALITY_WEIGHT.get(quality, 0.75)
    if relevance != "yes":
        return OmsuScore(
            score=0,
            impact_class="neutral_or_no_impact",
            negative_signal="not_negative_omsu",
            confidence_weight=quality_weight,
            scope_weight=0.0,
            reason="not_jkh",
        )
    if quality_weight <= 0:
        return OmsuScore(
            score=0,
            impact_class="neutral_or_no_impact",
            negative_signal="not_negative_omsu",
            confidence_weight=quality_weight,
            scope_weight=0.0,
            reason=f"excluded_quality:{quality}",
        )

    responsible_scope = RESPONSIBLE_SCOPE.get(responsible, 0.35)
    topic_scope = TOPIC_SCOPE.get(topic, 0.45)
    authority_scope = AUTHORITY_SCOPE.get(authority, 0.0)
    scope = max(responsible_scope, topic_scope * 0.85, authority_scope)

    if responsible_scope > 0:
        reasons.append(f"responsible:{responsible}:{responsible_scope:.2f}")
    if topic_scope > 0:
        reasons.append(f"topic:{topic}:{topic_scope:.2f}")
    if authority_scope > 0:
        reasons.append(f"authority_scope:{authority}:{authority_scope:.2f}")

    raw = (
        SENTIMENT_BASE.get(sentiment, 0.0)
        + APPEAL_MODIFIER.get(appeal, 0.0)
        + AUTHORITY_MODIFIER.get(authority, 0.0)
    )
    reasons.append(f"sentiment:{sentiment}:{SENTIMENT_BASE.get(sentiment, 0.0):.0f}")
    reasons.append(f"appeal:{appeal}:{APPEAL_MODIFIER.get(appeal, 0.0):.0f}")
    reasons.append(f"authority:{authority}:{AUTHORITY_MODIFIER.get(authority, 0.0):.0f}")

    if sarcasm == "yes":
        if raw > 0:
            raw = -abs(raw) * 0.75 - 12.0
            reasons.append("sarcasm:positive_to_negative")
        else:
            raw -= 10.0
            reasons.append("sarcasm:negative_boost")
    elif sarcasm == "unsure":
        raw *= 0.88
        reasons.append("sarcasm:unsure_discount")

    if raw == 0 and appeal in {"question", "request"}:
        raw = -8.0
        reasons.append("weak_problem_request")

    score = int(round(clamp(raw * scope * quality_weight)))
    return OmsuScore(
        score=score,
        impact_class=score_to_impact_class(score),
        negative_signal=score_to_negative_signal(score),
        confidence_weight=round(quality_weight, 4),
        scope_weight=round(scope, 4),
        reason="; ".join(reasons),
    )
