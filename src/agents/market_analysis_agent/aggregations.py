from __future__ import annotations

from collections import Counter, defaultdict

from .taxonomy import (
    COMPETENCY_FAMILY_LABELS,
    CORE_SIGNAL_LABELS,
    TOPIC_LABELS,
)
from .types import CompetitiveGap, OfferFeatures, PlatformAggregate


def _normalize_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_platform_name(value: object) -> str:
    return _normalize_str(value)


def _normalize_str_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    for value in values:
        normalized = _normalize_str(value)
        if normalized:
            result.append(normalized)
    return result


def _top(counter: Counter[str], n: int) -> list[str]:
    return [key for key, _ in counter.most_common(n)]


def _unique_preserve_order(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in _normalize_str_list(list(values) if values is not None else []):
        if value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


def _display_label(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)


def _noise_score(item: OfferFeatures) -> float:
    score = 0.0

    if _normalize_str(getattr(item, "title", "")):
        score += 0.15
    if _normalize_str(getattr(item, "description", "")):
        score += 0.10
    if _normalize_str_list(getattr(item, "topic_clusters", [])):
        score += 0.20
    if _normalize_str_list(getattr(item, "competency_families", [])):
        score += 0.20
    if _normalize_str_list(getattr(item, "value_props", [])):
        score += 0.10
    if _normalize_str_list(getattr(item, "core_signals", [])):
        score += 0.10
    if _normalize_str_list(getattr(item, "audience_segments", [])):
        score += 0.05
    if _normalize_str_list(getattr(item, "format_signals", [])):
        score += 0.05
    if _normalize_str_list(getattr(item, "support_signals", [])):
        score += 0.025
    if _normalize_str_list(getattr(item, "outcome_signals", [])):
        score += 0.025
    if _normalize_str_list(getattr(item, "intensity_signals", [])):
        score += 0.025

    return round(min(score, 1.0), 4)


def deduplicate_offer_features(
    items: list[OfferFeatures],
) -> tuple[list[OfferFeatures], int]:
    seen_keys: set[tuple[str, str, str]] = set()
    result: list[OfferFeatures] = []
    removed = 0

    for item in items:
        dedup_key = (
            _normalize_platform_name(getattr(item, "platform_name", "")).lower(),
            _normalize_str(getattr(item, "title", "")).lower(),
            _normalize_str(getattr(item, "canonical_url", "")).lower(),
        )
        if dedup_key in seen_keys:
            removed += 1
            continue

        seen_keys.add(dedup_key)
        result.append(item)

    return result, removed


def filter_noise_offer_features(
    items: list[OfferFeatures],
    *,
    min_quality_score: float = 0.35,
    require_topic_or_competency: bool = True,
) -> tuple[list[OfferFeatures], int]:
    result: list[OfferFeatures] = []
    removed = 0

    for item in items:
        quality_score = _noise_score(item)

        has_topics = bool(_normalize_str_list(getattr(item, "topic_clusters", [])))
        has_competencies = bool(_normalize_str_list(getattr(item, "competency_families", [])))

        if require_topic_or_competency and not (has_topics or has_competencies):
            removed += 1
            continue

        if quality_score < min_quality_score:
            removed += 1
            continue

        result.append(item)

    return result, removed


def aggregate_offer_features_by_platform(
    offer_features: list[OfferFeatures],
    *,
    raw_offer_features_total: int = 0,
    deduped_count: int = 0,
    noise_count: int = 0,
) -> list[PlatformAggregate]:
    grouped: dict[str, list[OfferFeatures]] = defaultdict(list)
    for item in offer_features:
        platform_name = _normalize_platform_name(getattr(item, "platform_name", ""))
        if not platform_name:
            continue
        grouped[platform_name].append(item)

    result: list[PlatformAggregate] = []

    for platform_name, items in grouped.items():
        topic_counter: Counter[str] = Counter()
        competency_counter: Counter[str] = Counter()
        value_counter: Counter[str] = Counter()
        core_counter: Counter[str] = Counter()
        audience_counter: Counter[str] = Counter()
        format_counter: Counter[str] = Counter()

        evidence_items: list[str] = []

        for item in items:
            topic_counter.update(_unique_preserve_order(getattr(item, "topic_clusters", [])))
            competency_counter.update(_unique_preserve_order(getattr(item, "competency_families", [])))
            value_counter.update(_unique_preserve_order(getattr(item, "value_props", [])))
            core_counter.update(_unique_preserve_order(getattr(item, "core_signals", [])))
            audience_counter.update(_unique_preserve_order(getattr(item, "audience_segments", [])))
            format_counter.update(_unique_preserve_order(getattr(item, "format_signals", [])))

            item_id = _normalize_str(getattr(item, "item_id", ""))
            canonical_url = _normalize_str(getattr(item, "canonical_url", ""))

            if item_id:
                evidence_items.append(item_id)
            elif canonical_url:
                evidence_items.append(canonical_url)

        result.append(
            PlatformAggregate(
                platform_name=platform_name,
                offers_count=len(items),
                raw_items_count=0,
                deduped_items_count=0,
                filtered_items_count=0,
                dropped_as_noise_count=0,
                dropped_as_duplicates_count=0,
                top_topics=_top(topic_counter, 8),
                top_competency_families=_top(competency_counter, 8),
                top_value_props=_top(value_counter, 8),
                top_core_signals=_top(core_counter, 10),
                top_audiences=_top(audience_counter, 8),
                top_format_signals=_top(format_counter, 8),
                evidence_items=_unique_preserve_order(evidence_items)[:20],
                source_items_count=len(items),
                source_items_count_raw=raw_offer_features_total,
                source_items_deduped_removed=deduped_count,
                source_items_noise_removed=noise_count,
            )
        )

    result.sort(key=lambda x: _normalize_platform_name(getattr(x, "platform_name", "")).lower())
    return result


def enrich_platform_counts(
    platform_aggregates: list[PlatformAggregate],
    *,
    raw_items: list[OfferFeatures],
    deduped_items: list[OfferFeatures],
    filtered_items: list[OfferFeatures],
) -> list[PlatformAggregate]:
    raw_counter = Counter(
        _normalize_platform_name(getattr(item, "platform_name", ""))
        for item in raw_items
        if _normalize_platform_name(getattr(item, "platform_name", ""))
    )
    deduped_counter = Counter(
        _normalize_platform_name(getattr(item, "platform_name", ""))
        for item in deduped_items
        if _normalize_platform_name(getattr(item, "platform_name", ""))
    )
    filtered_counter = Counter(
        _normalize_platform_name(getattr(item, "platform_name", ""))
        for item in filtered_items
        if _normalize_platform_name(getattr(item, "platform_name", ""))
    )

    enriched: list[PlatformAggregate] = []

    for aggregate in platform_aggregates:
        platform_name = _normalize_platform_name(getattr(aggregate, "platform_name", ""))
        raw_count = raw_counter.get(platform_name, 0)
        deduped_count = deduped_counter.get(platform_name, 0)
        filtered_count = filtered_counter.get(platform_name, 0)

        aggregate.raw_items_count = raw_count
        aggregate.deduped_items_count = deduped_count
        aggregate.filtered_items_count = filtered_count
        aggregate.dropped_as_duplicates_count = max(raw_count - deduped_count, 0)
        aggregate.dropped_as_noise_count = max(deduped_count - filtered_count, 0)

        enriched.append(aggregate)

    return enriched


def _topic_gap_interpretation_ru(
    *,
    label: str,
    platform_share: float,
    platforms_count: int,
    total_platforms: int,
) -> str:
    if platform_share <= 0.20:
        return (
            f"Направление «{label}» представлено только у {platforms_count} из {total_platforms} платформ, "
            f"что указывает на свободную или слабо занятую рыночную нишу."
        )
    if platform_share <= 0.40:
        return (
            f"Направление «{label}» встречается у ограниченной части игроков "
            f"({platforms_count} из {total_platforms}), что делает его заметной зоной роста."
        )
    return (
        f"Направление «{label}» уже присутствует у значимой части рынка, "
        f"но остаётся недопредставленным относительно более массовых тематических кластеров."
    )


def _competency_gap_interpretation_ru(
    *,
    label: str,
    platform_share: float,
    platforms_count: int,
    total_platforms: int,
) -> str:
    if platform_share <= 0.20:
        return (
            f"Семейство компетенций «{label}» встречается редко — только у {platforms_count} из {total_platforms} платформ, "
            f"поэтому может рассматриваться как точка дифференциации."
        )
    if platform_share <= 0.40:
        return (
            f"Семейство компетенций «{label}» имеет ограниченное покрытие на рынке "
            f"({platforms_count} из {total_platforms}), что создаёт пространство для усиления позиционирования."
        )
    return (
        f"Семейство компетенций «{label}» представлено неравномерно: это уже не пустая ниша, "
        f"но и не универсальный стандарт категории."
    )


def _core_signal_gap_interpretation_ru(
    *,
    label: str,
    platform_share: float,
    platforms_count: int,
    total_platforms: int,
) -> str:
    if platform_share <= 0.20:
        return (
            f"Сигнал дифференциации «{label}» почти не стандартизирован на рынке: "
            f"он обнаружен лишь у {platforms_count} из {total_platforms} платформ."
        )
    if platform_share <= 0.40:
        return (
            f"Сигнал «{label}» используется ограниченным числом игроков "
            f"({platforms_count} из {total_platforms}), поэтому может усиливать уникальность предложения."
        )
    return (
        f"Сигнал «{label}» уже заметен на рынке, но пока не стал базовым ожиданием по всей категории."
    )


def _opportunity_score(
    *,
    platform_share: float,
    underrepresented_platforms_count: int,
    total_platforms: int,
) -> float:
    return round(
        (1 - platform_share) * 0.7
        + min(underrepresented_platforms_count / max(total_platforms, 1), 1.0) * 0.3,
        4,
    )


def build_competitive_gaps(
    offer_features: list[OfferFeatures],
    platform_aggregates: list[PlatformAggregate],
) -> list[CompetitiveGap]:
    all_platform_names = sorted(
        {
            _normalize_platform_name(getattr(aggregate, "platform_name", ""))
            for aggregate in platform_aggregates
            if _normalize_platform_name(getattr(aggregate, "platform_name", ""))
        }
    )
    total_platforms = max(len(all_platform_names), 1)

    topic_to_platforms: dict[str, set[str]] = defaultdict(set)
    topic_to_item_ids: dict[str, list[str]] = defaultdict(list)

    competency_to_platforms: dict[str, set[str]] = defaultdict(set)
    competency_to_item_ids: dict[str, list[str]] = defaultdict(list)

    core_to_platforms: dict[str, set[str]] = defaultdict(set)
    core_to_item_ids: dict[str, list[str]] = defaultdict(list)

    for item in offer_features:
        platform_name = _normalize_platform_name(getattr(item, "platform_name", ""))
        if not platform_name:
            continue

        item_id = _normalize_str(getattr(item, "item_id", ""))

        for topic in _unique_preserve_order(getattr(item, "topic_clusters", [])):
            topic_to_platforms[topic].add(platform_name)
            if item_id:
                topic_to_item_ids[topic].append(item_id)

        for family in _unique_preserve_order(getattr(item, "competency_families", [])):
            competency_to_platforms[family].add(platform_name)
            if item_id:
                competency_to_item_ids[family].append(item_id)

        for signal in _unique_preserve_order(getattr(item, "core_signals", [])):
            core_to_platforms[signal].add(platform_name)
            if item_id:
                core_to_item_ids[signal].append(item_id)

    gaps: list[CompetitiveGap] = []

    for topic, platforms in topic_to_platforms.items():
        platforms_count = len(platforms)
        platform_share = round(platforms_count / total_platforms, 4)

        if platform_share >= 0.60:
            continue

        underrepresented_platforms = [name for name in all_platform_names if name not in platforms]
        opportunity_score = _opportunity_score(
            platform_share=platform_share,
            underrepresented_platforms_count=len(underrepresented_platforms),
            total_platforms=total_platforms,
        )
        label = _display_label(topic, TOPIC_LABELS)
        interpretation = _topic_gap_interpretation_ru(
            label=label,
            platform_share=platform_share,
            platforms_count=platforms_count,
            total_platforms=total_platforms,
        )

        gaps.append(
            CompetitiveGap(
                topic=topic,
                gap_type="topic_cluster",
                platforms_count=platforms_count,
                platform_share=platform_share,
                underrepresented_platforms=underrepresented_platforms[:20],
                opportunity_score=opportunity_score,
                interpretation=interpretation,
                evidence_item_ids=_unique_preserve_order(topic_to_item_ids[topic])[:10],
            )
        )

    for family, platforms in competency_to_platforms.items():
        platforms_count = len(platforms)
        platform_share = round(platforms_count / total_platforms, 4)

        if platform_share >= 0.60:
            continue

        underrepresented_platforms = [name for name in all_platform_names if name not in platforms]
        opportunity_score = _opportunity_score(
            platform_share=platform_share,
            underrepresented_platforms_count=len(underrepresented_platforms),
            total_platforms=total_platforms,
        )
        label = _display_label(family, COMPETENCY_FAMILY_LABELS)
        interpretation = _competency_gap_interpretation_ru(
            label=label,
            platform_share=platform_share,
            platforms_count=platforms_count,
            total_platforms=total_platforms,
        )

        gaps.append(
            CompetitiveGap(
                topic=family,
                gap_type="competency_family",
                platforms_count=platforms_count,
                platform_share=platform_share,
                underrepresented_platforms=underrepresented_platforms[:20],
                opportunity_score=opportunity_score,
                interpretation=interpretation,
                evidence_item_ids=_unique_preserve_order(competency_to_item_ids[family])[:10],
            )
        )

    for signal, platforms in core_to_platforms.items():
        platforms_count = len(platforms)
        platform_share = round(platforms_count / total_platforms, 4)

        if platform_share >= 0.60:
            continue

        underrepresented_platforms = [name for name in all_platform_names if name not in platforms]
        opportunity_score = _opportunity_score(
            platform_share=platform_share,
            underrepresented_platforms_count=len(underrepresented_platforms),
            total_platforms=total_platforms,
        )
        label = _display_label(signal, CORE_SIGNAL_LABELS)
        interpretation = _core_signal_gap_interpretation_ru(
            label=label,
            platform_share=platform_share,
            platforms_count=platforms_count,
            total_platforms=total_platforms,
        )

        gaps.append(
            CompetitiveGap(
                topic=signal,
                gap_type="core_signal",
                platforms_count=platforms_count,
                platform_share=platform_share,
                underrepresented_platforms=underrepresented_platforms[:20],
                opportunity_score=opportunity_score,
                interpretation=interpretation,
                evidence_item_ids=_unique_preserve_order(core_to_item_ids[signal])[:10],
            )
        )

    gaps.sort(
        key=lambda x: (
            -float(getattr(x, "opportunity_score", 0.0) or 0.0),
            float(getattr(x, "platform_share", 0.0) or 0.0),
            -int(len(getattr(x, "underrepresented_platforms", []) or [])),
            getattr(x, "gap_type", ""),
            getattr(x, "topic", ""),
        )
    )
    return gaps