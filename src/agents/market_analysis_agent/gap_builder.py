from __future__ import annotations

from collections import defaultdict
from typing import Literal

from .taxonomy import (
    COMPETENCY_FAMILY_LABELS,
    CORE_SIGNAL_LABELS,
    TOPIC_LABELS,
)
from .types import CompetitiveGap, OfferFeatures, PlatformAggregate


GapType = Literal["topic_cluster", "competency_family", "core_signal"]


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


def _normalize_signal_values(values: list[str]) -> list[str]:
    return _unique_preserve_order([value.strip() for value in values if value and value.strip()])


def _display_label(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)


def _label_mapping_for_gap_type(gap_type: GapType) -> dict[str, str]:
    if gap_type == "topic_cluster":
        return TOPIC_LABELS
    if gap_type == "competency_family":
        return COMPETENCY_FAMILY_LABELS
    return CORE_SIGNAL_LABELS


def _topic_field_to_gap_type(topic_field: str) -> GapType:
    mapping: dict[str, GapType] = {
        "topic_clusters": "topic_cluster",
        "competency_families": "competency_family",
        "core_signals": "core_signal",
    }
    return mapping[topic_field]


def _gap_type_to_topic_field(gap_type: GapType) -> str:
    mapping: dict[GapType, str] = {
        "topic_cluster": "topic_clusters",
        "competency_family": "competency_families",
        "core_signal": "core_signals",
    }
    return mapping[gap_type]


def _signal_values_for_gap_type(item: OfferFeatures, gap_type: GapType) -> list[str]:
    if gap_type == "topic_cluster":
        return item.topic_clusters
    if gap_type == "competency_family":
        return item.competency_families
    return item.core_signals


def _opportunity_score(
    *,
    platforms_count: int,
    total_platforms: int,
    items_count: int,
    item_density_cap: int,
) -> tuple[float, float]:
    platform_share = platforms_count / max(total_platforms, 1)
    scarcity_component = 1.0 - platform_share
    density_component = min(items_count / max(item_density_cap, 1), 1.0)
    opportunity_score = round((scarcity_component * 0.65) + (density_component * 0.35), 4)
    return round(platform_share, 4), opportunity_score


def _topic_gap_interpretation_ru(platform_share: float) -> str:
    if platform_share >= 0.75:
        return "Кластер тем уже широко представлен на рынке и скорее отражает конкурентный паритет, чем выраженный gap."
    if platform_share >= 0.40:
        return "Кластер тем покрыт частью игроков, но ещё оставляет пространство для выборочной дифференциации."
    return "Кластер тем представлен ограниченно и может рассматриваться как заметная зона конкурентного роста."


def _competency_gap_interpretation_ru(platform_share: float) -> str:
    if platform_share >= 0.75:
        return "Семейство компетенций уже стало близким к рыночному стандарту и даёт ограниченный потенциал для отличия."
    if platform_share >= 0.40:
        return "Семейство компетенций представлено умеренно и может использоваться как рабочая зона усиления."
    return "Семейство компетенций недопредставлено и выглядит как потенциально сильная точка позиционирования."


def _core_signal_gap_interpretation_ru(platform_share: float) -> str:
    if platform_share >= 0.75:
        return "Эта каноническая ось дифференциации уже распространена широко и чаще означает ожидаемый рыночный baseline."
    if platform_share >= 0.40:
        return "Эта каноническая ось дифференциации присутствует у части игроков и может усиливать позиционирование при точечной доработке."
    return "Эта каноническая ось дифференциации пока используется избирательно и выглядит как сильная возможность для конкурентного отличия."


def _interpretation_for_gap_type(gap_type: GapType, platform_share: float) -> str:
    if gap_type == "topic_cluster":
        return _topic_gap_interpretation_ru(platform_share)
    if gap_type == "competency_family":
        return _competency_gap_interpretation_ru(platform_share)
    return _core_signal_gap_interpretation_ru(platform_share)


def _append_signal_occurrence(
    *,
    signal_values: list[str],
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


def _all_platform_names(platform_aggregates: list[PlatformAggregate]) -> list[str]:
    names = [item.platform_name.strip() for item in platform_aggregates if item.platform_name and item.platform_name.strip()]
    return sorted(_unique_preserve_order(names))


def _build_gap_entry(
    *,
    signal_value: str,
    gap_type: GapType,
    all_platform_names: list[str],
    covered_platforms: set[str],
    items_count: int,
    evidence_item_ids: list[str],
    item_density_cap: int,
) -> CompetitiveGap:
    total_platforms = max(len(all_platform_names), 1)
    platform_share, opportunity_score = _opportunity_score(
        platforms_count=len(covered_platforms),
        total_platforms=total_platforms,
        items_count=items_count,
        item_density_cap=item_density_cap,
    )

    covered = set(covered_platforms)
    underrepresented_platforms = [name for name in all_platform_names if name not in covered]

    return CompetitiveGap(
        topic=signal_value,
        gap_type=gap_type,
        platforms_count=len(covered_platforms),
        platform_share=platform_share,
        underrepresented_platforms=underrepresented_platforms,
        opportunity_score=opportunity_score,
        interpretation=_interpretation_for_gap_type(gap_type, platform_share),
        evidence_item_ids=_unique_preserve_order(evidence_item_ids)[:10],
    )


def _empty_gap_registry() -> tuple[
    dict[str, set[str]],
    dict[str, int],
    dict[str, list[str]],
]:
    return defaultdict(set), defaultdict(int), defaultdict(list)


def _build_gap_entries_for_type(
    *,
    gap_type: GapType,
    signal_to_platforms: dict[str, set[str]],
    signal_to_items: dict[str, int],
    signal_to_item_ids: dict[str, list[str]],
    all_platform_names: list[str],
    item_density_cap: int,
) -> list[CompetitiveGap]:
    entries: list[CompetitiveGap] = []

    for signal_value, covered_platforms in signal_to_platforms.items():
        entries.append(
            _build_gap_entry(
                signal_value=signal_value,
                gap_type=gap_type,
                all_platform_names=all_platform_names,
                covered_platforms=covered_platforms,
                items_count=signal_to_items[signal_value],
                evidence_item_ids=signal_to_item_ids[signal_value],
                item_density_cap=item_density_cap,
            )
        )

    return entries


def build_competitive_gaps(
    offer_features: list[OfferFeatures],
    platform_aggregates: list[PlatformAggregate],
) -> list[CompetitiveGap]:
    all_platform_names = _all_platform_names(platform_aggregates)

    topic_to_platforms, topic_to_items, topic_to_item_ids = _empty_gap_registry()
    competency_to_platforms, competency_to_items, competency_to_item_ids = _empty_gap_registry()
    core_signal_to_platforms, core_signal_to_items, core_signal_to_item_ids = _empty_gap_registry()

    for item in offer_features:
        _append_signal_occurrence(
            signal_values=item.topic_clusters,
            platform_name=item.platform_name,
            item_id=item.item_id,
            signal_to_platforms=topic_to_platforms,
            signal_to_items=topic_to_items,
            signal_to_item_ids=topic_to_item_ids,
        )

        _append_signal_occurrence(
            signal_values=item.competency_families,
            platform_name=item.platform_name,
            item_id=item.item_id,
            signal_to_platforms=competency_to_platforms,
            signal_to_items=competency_to_items,
            signal_to_item_ids=competency_to_item_ids,
        )

        _append_signal_occurrence(
            signal_values=item.core_signals,
            platform_name=item.platform_name,
            item_id=item.item_id,
            signal_to_platforms=core_signal_to_platforms,
            signal_to_items=core_signal_to_items,
            signal_to_item_ids=core_signal_to_item_ids,
        )

    gaps: list[CompetitiveGap] = []

    gaps.extend(
        _build_gap_entries_for_type(
            gap_type="topic_cluster",
            signal_to_platforms=topic_to_platforms,
            signal_to_items=topic_to_items,
            signal_to_item_ids=topic_to_item_ids,
            all_platform_names=all_platform_names,
            item_density_cap=20,
        )
    )

    gaps.extend(
        _build_gap_entries_for_type(
            gap_type="competency_family",
            signal_to_platforms=competency_to_platforms,
            signal_to_items=competency_to_items,
            signal_to_item_ids=competency_to_item_ids,
            all_platform_names=all_platform_names,
            item_density_cap=20,
        )
    )

    gaps.extend(
        _build_gap_entries_for_type(
            gap_type="core_signal",
            signal_to_platforms=core_signal_to_platforms,
            signal_to_items=core_signal_to_items,
            signal_to_item_ids=core_signal_to_item_ids,
            all_platform_names=all_platform_names,
            item_density_cap=25,
        )
    )

    gaps.sort(
        key=lambda x: (
            -float(x.opportunity_score or 0.0),
            float(x.platform_share or 0.0),
            -len(x.underrepresented_platforms or []),
            x.gap_type,
            x.topic,
        )
    )
    return gaps


def attach_gap_labels(gaps: list[CompetitiveGap]) -> list[dict]:
    labeled: list[dict] = []

    for gap in gaps:
        label = _display_label(
            gap.topic,
            _label_mapping_for_gap_type(gap.gap_type),
        )

        labeled.append(
            {
                "topic": gap.topic,
                "label": label,
                "gap_type": gap.gap_type,
                "topic_field": _gap_type_to_topic_field(gap.gap_type),
                "platforms_count": gap.platforms_count,
                "platform_share": gap.platform_share,
                "underrepresented_platforms": gap.underrepresented_platforms,
                "opportunity_score": gap.opportunity_score,
                "interpretation": gap.interpretation,
                "evidence_item_ids": gap.evidence_item_ids,
            }
        )

    return labeled