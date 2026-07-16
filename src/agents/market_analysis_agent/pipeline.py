from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .aggregations import (
    aggregate_offer_features_by_platform,
    deduplicate_offer_features,
    enrich_platform_counts,
    filter_noise_offer_features,
)
from .classifiers import classify_catalog_items
from .gap_builder import build_competitive_gaps
from .loader import load_market_agent_reports
from .positioning import build_platform_positioning_profiles
from .report_builder import build_market_analysis_report_bundle
from .trend_builder import build_trend_signals
from .types import MarketAnalysisBundle


def run_market_analysis(
    *,
    source_json_path: str | None = None,
    min_quality_score: float = 0.35,
) -> dict[str, Any]:
    """
    Полный orchestration entrypoint для market analysis pipeline.

    Шаги:
    1. Загружает platform reports из market_agent JSON.
    2. Классифицирует catalog items в offer-level feature objects.
    3. Удаляет дубликаты и шум.
    4. Собирает platform aggregates.
    5. Строит positioning profiles, trend signals и competitive gaps.
    6. Формирует финальный MarketAnalysisBundle и downstream report artifacts.
    """

    platform_reports = load_market_agent_reports(source_json_path=source_json_path)

    raw_catalog_items_total = sum(len(platform.items) for platform in platform_reports)

    raw_offer_features = classify_catalog_items(platform_reports)

    deduped_offer_features, deduped_removed_count = deduplicate_offer_features(raw_offer_features)
    after_dedup_count = len(deduped_offer_features)

    filtered_offer_features, noise_count = filter_noise_offer_features(
        deduped_offer_features,
        min_quality_score=min_quality_score,
    )

    kept_offer_features_count = len(filtered_offer_features)

    platform_aggregates = aggregate_offer_features_by_platform(
        filtered_offer_features,
        raw_offer_features_total=len(raw_offer_features),
        deduped_count=deduped_removed_count,
        noise_count=noise_count,
    )

    platform_aggregates = enrich_platform_counts(
        platform_aggregates=platform_aggregates,
        raw_items=raw_offer_features,
        deduped_items=deduped_offer_features,
        filtered_items=filtered_offer_features,
    )

    platform_positioning = build_platform_positioning_profiles(
        platform_reports=platform_reports,
        platform_aggregates=platform_aggregates,
        offer_features=filtered_offer_features,
    )

    trend_signals = build_trend_signals(
        offer_features=filtered_offer_features,
        platform_aggregates=platform_aggregates,
    )

    competitive_gaps = build_competitive_gaps(
        offer_features=filtered_offer_features,
        platform_aggregates=platform_aggregates,
    )

    bundle = MarketAnalysisBundle(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_run_path=source_json_path or "",
        platforms_total=len(platform_reports),
        catalog_items_total_raw=raw_catalog_items_total,
        catalog_items_total_after_dedup=after_dedup_count,
        catalog_items_total_kept=kept_offer_features_count,
        catalog_items_total_noise=noise_count,
        catalog_items_total_deduped=deduped_removed_count,
        offer_features=filtered_offer_features,
        platform_aggregates=platform_aggregates,
        platform_positioning=platform_positioning,
        trend_signals=trend_signals,
        competitive_gaps=competitive_gaps,
        summary={
            "platforms_total": len(platform_reports),
            "catalog_items_total_raw": raw_catalog_items_total,
            "catalog_items_total_after_dedup": after_dedup_count,
            "catalog_items_total_deduped": deduped_removed_count,
            "catalog_items_total_noise": noise_count,
            "catalog_items_total_kept": kept_offer_features_count,
            "raw_offer_features_total": len(raw_offer_features),
            "deduped_offer_features_total": after_dedup_count,
            "filtered_offer_features_total": kept_offer_features_count,
            "trend_signals_total": len(trend_signals),
            "competitive_gaps_total": len(competitive_gaps),
            "platform_aggregates_total": len(platform_aggregates),
            "platform_positioning_total": len(platform_positioning),
            "min_quality_score": min_quality_score,
            "source_json_path": source_json_path or "",
        },
        metadata={
            "pipeline_version": "canonical_market_analysis_v1",
            "contract": {
                "platform_report_input_items_field": "items",
                "platform_report_input_compat_alias": "catalog_items",
                "offer_features_core_signals_enabled": True,
                "trend_types": ["topic_cluster", "competency_family", "core_signal"],
                "gap_types": ["topic_cluster", "competency_family", "core_signal"],
                "catalog_items_total_deduped_semantics": "duplicates_removed",
                "catalog_items_total_after_dedup_semantics": "items_remaining_after_dedup",
            },
        },
    )

    files = build_market_analysis_report_bundle(bundle)

    return {
        "bundle": bundle,
        "summary": bundle.summary,
        "files": files,
    }