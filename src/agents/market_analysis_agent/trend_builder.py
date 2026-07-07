from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from .taxonomy import (
    COMPETENCY_FAMILY_LABELS,
    CORE_SIGNAL_LABELS,
    TOPIC_LABELS,
)
from .types import OfferFeatures, PlatformAggregate, TrendSignal


TrendType = Literal["topic_cluster", "competency_family", "core_signal"]


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_signal_key(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if hasattr(value, "key"):
        key = getattr(value, "key")
        if isinstance(key, str) and key.strip():
            return key.strip()

    if hasattr(value, "value"):
        raw_value = getattr(value, "value")
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()

    if hasattr(value, "topic_key"):
        topic_key = getattr(value, "topic_key")
        if isinstance(topic_key, str) and topic_key.strip():
            return topic_key.strip()

    if hasattr(value, "name"):
        name = getattr(value, "name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    return str(value).strip()


def _normalize_signal_values(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = _normalize_signal_key(value)
        if normalized:
            result.append(normalized)
    return _unique_preserve_order(result)


def _display_label(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)


def _topic_interpretation_ru(platform_share: float) -> str:
    if platform_share >= 0.75:
        return "Широко представленный кластер тем в конкурентном наборе."
    if platform_share >= 0.40:
        return "Растущий или средне-плотный кластер тем с заметным рыночным присутствием."
    return "Нишевой или формирующийся кластер тем с ограниченным платформенным покрытием."


def _competency_interpretation_ru(platform_share: float) -> str:
    if platform_share >= 0.75:
        return "Широко представленное семейство компетенций на рынке."
    if platform_share >= 0.40:
        return "Значимое семейство компетенций с умеренным кросс-платформенным присутствием."
    return "Специализированное семейство компетенций с более низкой конкурентной насыщенностью."


def _core_signal_interpretation_ru(platform_share: float) -> str:
    if platform_share >= 0.75:
        return "Каноническая ось дифференциации, широко используемая на рынке."
    if platform_share >= 0.40:
        return "Заметная ось дифференциации с устойчивым, но не универсальным присутствием."
    return "Избирательно используемая ось дифференциации, которая чаще служит точкой отличия, чем рыночным стандартом."


def _interpretation_for_trend_type(trend_type: TrendType, platform_share: float) -> str:
    if trend_type == "topic_cluster":
        return _topic_interpretation_ru(platform_share)
    if trend_type == "competency_family":
        return _competency_interpretation_ru(platform_share)
    return _core_signal_interpretation_ru(platform_share)


def _label_mapping_for_trend_type(trend_type: TrendType) -> dict[str, str]:
    if trend_type == "topic_cluster":
        return TOPIC_LABELS
    if trend_type == "competency_family":
        return COMPETENCY_FAMILY_LABELS
    return CORE_SIGNAL_LABELS


def _trend_signal_strength(
    *,
    platforms_count: int,
    total_platforms: int,
    items_count: int,
    item_density_cap: int,
) -> tuple[float, float]:
    platform_share = platforms_count / max(total_platforms, 1)
    item_density_component = min(items_count / max(item_density_cap, 1), 1.0)
    signal_strength = round((platform_share * 0.7) + (item_density_component * 0.3), 4)
    return round(platform_share, 4), signal_strength


def _append_signal_occurrence(
    *,
    signal_values: list[Any],
    platform_name: str,
    item_id: str,
    signal_to_platforms: dict[str, set[str]],
    signal_to_items: dict[str, int],
    signal_to_item_ids: dict[str, list[str]],
) -> None:
    for signal in _normalize_signal_values(signal_values):
        signal_to_platforms[signal].add(platform_name)
        signal_to_items[signal] += 1
        if item_id:
            signal_to_item_ids[signal].append(item_id)


def _build_trend_entry(
    *,
    signal_value: str,
    trend_type: TrendType,
    platforms: set[str],
    items_count: int,
    evidence_item_ids: list[str],
    total_platforms: int,
    item_density_cap: int,
) -> TrendSignal:
    normalized_signal = _normalize_signal_key(signal_value)

    platform_share, signal_strength = _trend_signal_strength(
        platforms_count=len(platforms),
        total_platforms=total_platforms,
        items_count=items_count,
        item_density_cap=item_density_cap,
    )

    return TrendSignal(
        trend_id=f"{trend_type}::{normalized_signal}",
        topic=normalized_signal,
        trend_type=trend_type,
        platforms_count=len(platforms),
        items_count=items_count,
        platform_share=platform_share,
        signal_strength=signal_strength,
        representative_platforms=sorted(x for x in platforms if x),
        evidence_item_ids=_unique_preserve_order(evidence_item_ids)[:10],
        core_signals=[normalized_signal] if trend_type == "core_signal" else [],
        interpretation=_interpretation_for_trend_type(trend_type, platform_share),
    )


def build_trend_signals(
    offer_features: list[OfferFeatures],
    platform_aggregates: list[PlatformAggregate],
) -> list[TrendSignal]:
    total_platforms = max(len(platform_aggregates), 1)

    topic_to_platforms: dict[str, set[str]] = defaultdict(set)
    topic_to_items: dict[str, int] = defaultdict(int)
    topic_to_item_ids: dict[str, list[str]] = defaultdict(list)

    competency_to_platforms: dict[str, set[str]] = defaultdict(set)
    competency_to_items: dict[str, int] = defaultdict(int)
    competency_to_item_ids: dict[str, list[str]] = defaultdict(list)

    core_signal_to_platforms: dict[str, set[str]] = defaultdict(set)
    core_signal_to_items: dict[str, int] = defaultdict(int)
    core_signal_to_item_ids: dict[str, list[str]] = defaultdict(list)

    for item in offer_features:
        _append_signal_occurrence(
            signal_values=getattr(item, "topic_clusters", []),
            platform_name=getattr(item, "platform_name", ""),
            item_id=getattr(item, "item_id", ""),
            signal_to_platforms=topic_to_platforms,
            signal_to_items=topic_to_items,
            signal_to_item_ids=topic_to_item_ids,
        )

        _append_signal_occurrence(
            signal_values=getattr(item, "competency_families", []),
            platform_name=getattr(item, "platform_name", ""),
            item_id=getattr(item, "item_id", ""),
            signal_to_platforms=competency_to_platforms,
            signal_to_items=competency_to_items,
            signal_to_item_ids=competency_to_item_ids,
        )

        _append_signal_occurrence(
            signal_values=getattr(item, "core_signals", []),
            platform_name=getattr(item, "platform_name", ""),
            item_id=getattr(item, "item_id", ""),
            signal_to_platforms=core_signal_to_platforms,
            signal_to_items=core_signal_to_items,
            signal_to_item_ids=core_signal_to_item_ids,
        )

    trends: list[TrendSignal] = []

    for topic, platforms in topic_to_platforms.items():
        trends.append(
            _build_trend_entry(
                signal_value=topic,
                trend_type="topic_cluster",
                platforms=platforms,
                items_count=topic_to_items[topic],
                evidence_item_ids=topic_to_item_ids[topic],
                total_platforms=total_platforms,
                item_density_cap=20,
            )
        )

    for family, platforms in competency_to_platforms.items():
        trends.append(
            _build_trend_entry(
                signal_value=family,
                trend_type="competency_family",
                platforms=platforms,
                items_count=competency_to_items[family],
                evidence_item_ids=competency_to_item_ids[family],
                total_platforms=total_platforms,
                item_density_cap=20,
            )
        )

    for core_signal, platforms in core_signal_to_platforms.items():
        trends.append(
            _build_trend_entry(
                signal_value=core_signal,
                trend_type="core_signal",
                platforms=platforms,
                items_count=core_signal_to_items[core_signal],
                evidence_item_ids=core_signal_to_item_ids[core_signal],
                total_platforms=total_platforms,
                item_density_cap=25,
            )
        )

    trends.sort(
        key=lambda x: (
            -float(getattr(x, "signal_strength", 0.0) or 0.0),
            -int(getattr(x, "platforms_count", 0) or 0),
            -int(getattr(x, "items_count", 0) or 0),
            str(getattr(x, "trend_type", "") or ""),
            _normalize_signal_key(getattr(x, "topic", "")),
        )
    )
    return trends


def attach_trend_labels(trends: list[TrendSignal]) -> list[dict[str, Any]]:
    labeled: list[dict[str, Any]] = []

    for trend in trends:
        topic_key = _normalize_signal_key(getattr(trend, "topic", ""))
        label = _display_label(
            topic_key,
            _label_mapping_for_trend_type(getattr(trend, "trend_type", "topic_cluster")),
        )

        labeled.append(
            {
                "trend_id": getattr(trend, "trend_id", ""),
                "topic": topic_key,
                "label": label,
                "trend_type": getattr(trend, "trend_type", ""),
                "platforms_count": getattr(trend, "platforms_count", 0),
                "items_count": getattr(trend, "items_count", 0),
                "platform_share": getattr(trend, "platform_share", 0.0),
                "signal_strength": getattr(trend, "signal_strength", 0.0),
                "representative_platforms": getattr(trend, "representative_platforms", []),
                "evidence_item_ids": getattr(trend, "evidence_item_ids", []),
                "core_signals": getattr(trend, "core_signals", []),
                "interpretation": getattr(trend, "interpretation", ""),
            }
        )

    return labeled