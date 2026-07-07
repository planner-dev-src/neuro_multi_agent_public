from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from src.agents.market_analysis_agent import loader, report_builder
from src.agents.market_analysis_agent.taxonomy import (
    COMPETENCY_FAMILY_LABELS,
    CORE_SIGNAL_LABELS,
    TOPIC_KEYS,
    TOPIC_LABELS,
)
from src.agents.market_analysis_agent.types import (
    CatalogItem,
    MarketAnalysisBundle,
    PlatformReportInput,
)


def _reload_loader_module():
    return importlib.reload(loader)


def _reload_report_builder_module():
    return importlib.reload(report_builder)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _label(mapping: dict[str, str], key: str) -> str:
    return mapping.get(key, key)


def _pick_existing_topic(*preferred: str) -> str:
    for key in preferred:
        if key in TOPIC_LABELS:
            return key
    if TOPIC_KEYS:
        return TOPIC_KEYS[0]
    raise AssertionError("TOPIC_KEYS is empty; cannot build report test data")


def _pick_existing_core_signal(*preferred: str) -> str:
    for key in preferred:
        if key in CORE_SIGNAL_LABELS:
            return key
    if CORE_SIGNAL_LABELS:
        return next(iter(CORE_SIGNAL_LABELS))
    raise AssertionError("CORE_SIGNAL_LABELS is empty; cannot build report test data")


def _pick_existing_competency(*preferred: str) -> str:
    for key in preferred:
        if key in COMPETENCY_FAMILY_LABELS:
            return key
    if COMPETENCY_FAMILY_LABELS:
        return next(iter(COMPETENCY_FAMILY_LABELS))
    raise AssertionError("COMPETENCY_FAMILY_LABELS is empty; cannot build report test data")


def _make_offer_features_item(**kwargs: Any) -> Any:
    """Создаёт динамический объект, совместимый с OfferFeatures.

    Принимает любые keyword-аргументы и выставляет их как атрибуты.
    Пропущенные поля получают значения по умолчанию, соответствующие
    актуальному контракту OfferFeatures.
    """
    defaults: dict[str, Any] = {
        "platform_name": "",
        "item_id": "",
        "title": "",
        "item_title": "",
        "canonical_url": "",
        "item_type": "",
        "normalized_title": "",
        "text_fingerprint": "",
        "topic_clusters": [],
        "competency_families": [],
        "audience_segments": [],
        "core_signals": [],
        "format_signals": [],
        "outcome_signals": [],
        "support_signals": [],
        "intensity_signals": [],
        "value_props": [],
        "duration_bucket": "unknown",
        "difficulty_bucket": "unknown",
        "quality_score": 0.0,
        "is_noise": False,
        "noise_reasons": [],
        "evidence_text": "",
        "language": "",
        "extraction_confidence": None,
        "extraction_notes": [],
    }
    merged = {**defaults, **kwargs}

    class OfferFeaturesItem:
        pass

    obj = OfferFeaturesItem()
    for k, v in merged.items():
        setattr(obj, k, v)
    return obj


def _make_catalog_item(
    *,
    platform_name: str,
    item_id: str,
    title: str,
    canonical_url: str,
    topic_keys: list[str],
    competency_keys: list[str],
    audience_segments: list[str],
    core_signal_keys: list[str],
    quality_score: float,
    evidence_text: str,
) -> Any:
    return _make_offer_features_item(
        platform_name=platform_name,
        item_id=item_id,
        title=title,
        item_title=title,
        canonical_url=canonical_url,
        item_type="course",
        normalized_title=title.lower(),
        text_fingerprint=f"fp-{item_id}",
        topic_clusters=topic_keys,
        competency_families=competency_keys,
        audience_segments=audience_segments,
        core_signals=core_signal_keys,
        format_signals=["cohort"],
        outcome_signals=["portfolio"],
        support_signals=["mentor"],
        intensity_signals=["part_time"],
        value_props=["hands_on"],
        duration_bucket="medium",
        difficulty_bucket="beginner",
        quality_score=quality_score,
        is_noise=False,
        noise_reasons=[],
        evidence_text=evidence_text,
        language="ru",
        extraction_confidence=0.85,
        extraction_notes=["source:test"],
    )


def _make_dynamic_obj(**kwargs: Any) -> Any:
    """Универсальная фабрика динамических объектов.

    Создаёт объект и выставляет переданные keyword-аргументы как атрибуты.
    """
    obj = type("DynamicObj", (), {})()
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


def _make_trend_signal(
    *,
    trend_id: str,
    topic: Any,
    trend_type: str,
    platforms_count: int,
    items_count: int,
    platform_share: float,
    signal_strength: float,
    representative_platforms: list[str],
    evidence_item_ids: list[str],
    interpretation: str,
) -> Any:
    return _make_dynamic_obj(
        trend_id=trend_id,
        topic=topic,
        trend_type=trend_type,
        platforms_count=platforms_count,
        items_count=items_count,
        platform_share=platform_share,
        signal_strength=signal_strength,
        representative_platforms=representative_platforms,
        evidence_item_ids=evidence_item_ids,
        interpretation=interpretation,
    )


def _make_competitive_gap(
    *,
    topic: Any,
    gap_type: str,
    platforms_count: int,
    platform_share: float,
    underrepresented_platforms: list[str],
    opportunity_score: float,
    interpretation: str,
    evidence_item_ids: list[str],
) -> Any:
    return _make_dynamic_obj(
        topic=topic,
        gap_type=gap_type,
        platforms_count=platforms_count,
        platform_share=platform_share,
        underrepresented_platforms=underrepresented_platforms,
        opportunity_score=opportunity_score,
        interpretation=interpretation,
        evidence_item_ids=evidence_item_ids,
    )


def _make_platform_positioning(
    *,
    platform_name: str,
    audience_focus: list[str],
    value_props: list[str],
    core_signals: list[str],
    pedagogy_style: list[str],
    career_signals: list[str],
    academic_signals: list[str],
    execution_model: list[str],
    dominant_topics: list[str],
    dominant_competency_families: list[str],
    positioning_statement: str,
) -> Any:
    return _make_dynamic_obj(
        platform_name=platform_name,
        audience_focus=audience_focus,
        value_props=value_props,
        core_signals=core_signals,
        pedagogy_style=pedagogy_style,
        career_signals=career_signals,
        academic_signals=academic_signals,
        execution_model=execution_model,
        dominant_topics=dominant_topics,
        dominant_competency_families=dominant_competency_families,
        positioning_statement=positioning_statement,
    )


def _build_bundle() -> MarketAnalysisBundle:
    topic_a = _pick_existing_topic("computer_vision", "nlp", "classical_ml")
    topic_b = _pick_existing_topic("llm_agents", "automl", "data_engineering")
    topic_c = next((x for x in TOPIC_KEYS if x not in {topic_a, topic_b}), None) or topic_a

    core_a = _pick_existing_core_signal("independent_assignments", "flexible_schedule", "job_support")
    core_b = next((x for x in CORE_SIGNAL_LABELS if x != core_a), core_a)
    core_c = next((x for x in CORE_SIGNAL_LABELS if x not in {core_a, core_b}), core_a)

    competency_a = _pick_existing_competency("ai_ml_core", "generative_ai", "data_platforms")
    competency_b = next((x for x in COMPETENCY_FAMILY_LABELS if x != competency_a), competency_a)

    offer_features = [
        _make_catalog_item(
            platform_name="Platform A",
            item_id="item-1",
            title="Applied AI Foundations",
            canonical_url="https://platform-a.example/item-1",
            topic_keys=[topic_a, topic_b],
            competency_keys=[competency_a],
            audience_segments=["beginners"],
            core_signal_keys=[core_a, core_b],
            quality_score=0.91,
            evidence_text="Strong applied AI positioning.",
        ),
        _make_catalog_item(
            platform_name="Platform B",
            item_id="item-2",
            title="Production AI Systems",
            canonical_url="https://platform-b.example/item-2",
            topic_keys=[topic_c],
            competency_keys=[competency_a],
            audience_segments=["working_professionals"],
            core_signal_keys=[core_c],
            quality_score=0.82,
            evidence_text="Production-oriented systems course.",
        ),
    ]

    trend_signals = [
        _make_trend_signal(
            trend_id="trend-1",
            topic=topic_a,
            trend_type="topic_cluster",
            platforms_count=2,
            items_count=18,
            platform_share=0.67,
            signal_strength=0.8123,
            representative_platforms=["Platform A", "Platform C"],
            evidence_item_ids=["item-1", "item-3"],
            interpretation="Foundational content remains highly visible.",
        ),
        _make_trend_signal(
            trend_id="trend-2",
            topic=topic_c,
            trend_type="topic_cluster",
            platforms_count=1,
            items_count=9,
            platform_share=0.33,
            signal_strength=0.4567,
            representative_platforms=["Platform B"],
            evidence_item_ids=["item-2"],
            interpretation="This area remains more specialized.",
        ),
        _make_trend_signal(
            trend_id="trend-3",
            topic=core_a,
            trend_type="core_signal",
            platforms_count=2,
            items_count=11,
            platform_share=0.67,
            signal_strength=0.63,
            representative_platforms=["Platform A", "Platform C"],
            evidence_item_ids=["item-1"],
            interpretation="This positioning is common.",
        ),
        _make_trend_signal(
            trend_id="trend-4",
            topic=core_b,
            trend_type="core_signal",
            platforms_count=1,
            items_count=4,
            platform_share=0.33,
            signal_strength=0.28,
            representative_platforms=["Platform A"],
            evidence_item_ids=["item-1"],
            interpretation="This signal appears selectively.",
        ),
        _make_trend_signal(
            trend_id="trend-5",
            topic=competency_a,
            trend_type="competency_family",
            platforms_count=3,
            items_count=25,
            platform_share=1.0,
            signal_strength=0.88,
            representative_platforms=["Platform A", "Platform B", "Platform C"],
            evidence_item_ids=["item-1", "item-2"],
            interpretation="This competency family remains dominant.",
        ),
    ]

    competitive_gaps = [
        _make_competitive_gap(
            topic=topic_a,
            gap_type="topic_cluster",
            platforms_count=3,
            platform_share=0.85,
            underrepresented_platforms=["Platform B"],
            opportunity_score=0.22,
            interpretation="Dense space with limited whitespace.",
            evidence_item_ids=["item-1"],
        ),
        _make_competitive_gap(
            topic=topic_b,
            gap_type="topic_cluster",
            platforms_count=1,
            platform_share=0.20,
            underrepresented_platforms=["Platform A", "Platform B"],
            opportunity_score=0.74,
            interpretation="Potential whitespace in this area.",
            evidence_item_ids=["item-4"],
        ),
    ]

    platform_positioning = [
        _make_platform_positioning(
            platform_name="Platform A",
            audience_focus=["beginners", "career_switchers"],
            value_props=["hands_on", "career_support"],
            core_signals=[core_a, core_b],
            pedagogy_style=["cohort_based"],
            career_signals=["portfolio_projects"],
            academic_signals=["light_theory"],
            execution_model=["guided"],
            dominant_topics=[topic_a, topic_b],
            dominant_competency_families=[competency_a, competency_b],
            positioning_statement="Structured applied AI learning with guided support.",
        ),
        _make_platform_positioning(
            platform_name="Platform B",
            audience_focus=["working_professionals"],
            value_props=["production_readiness"],
            core_signals=[core_c],
            pedagogy_style=["self_paced"],
            career_signals=["career_growth"],
            academic_signals=["systems_depth"],
            execution_model=["independent"],
            dominant_topics=[topic_c],
            dominant_competency_families=[competency_a],
            positioning_statement="Flexible systems upskilling for practitioners.",
        ),
    ]

    return MarketAnalysisBundle(
        generated_at_utc="2026-07-05T12:00:00Z",
        platforms_total=3,
        catalog_items_total_raw=120,
        catalog_items_total_deduped=15,
        catalog_items_total_noise=10,
        catalog_items_total_kept=95,
        offer_features=offer_features,
        trend_signals=trend_signals,
        competitive_gaps=competitive_gaps,
        platform_positioning=platform_positioning,
    )


def test_load_market_agent_reports_reads_items_payload(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_sample.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Platform A",
                    "platform_url": "https://platform-a.example",
                    "items": [
                        {
                            "item_id": "course-1",
                            "title": "Intro to AI",
                            "description": "Basics",
                            "canonical_url": "https://platform-a.example/course-1",
                            "source_url": "https://platform-a.example/source-course-1",
                            "category_hint": "ai",
                            "category_raw": "AI",
                            "item_type": "course",
                            "provider_name": "Platform A",
                            "tags_raw": ["ai", "intro"],
                            "ai_topics": ["topic-a"],
                            "audience_types": ["beginners"],
                            "duration_text": "4 weeks",
                            "duration_hours": "12.5",
                            "difficulty_level": "beginner",
                            "certificate_available": "yes",
                            "project_based": "true",
                            "mentor_support": "false",
                            "job_support": None,
                            "metadata": {"language": "en"},
                        }
                    ],
                }
            ]
        },
    )

    reports = loader_module.load_market_agent_reports(source_json_path=str(source_path))

    assert len(reports) == 1
    report = reports[0]
    assert isinstance(report, PlatformReportInput)
    assert report.platform_name == "Platform A"
    assert report.source_url == "https://platform-a.example"
    assert len(report.items) == 1

    item = report.items[0]
    assert isinstance(item, CatalogItem)
    assert item.item_id == "course-1"
    assert item.title == "Intro to AI"
    assert item.duration_hours == 12.5
    assert item.certificate_available is True
    assert item.project_based is True
    assert item.mentor_support is False
    assert item.job_support is None
    assert item.metadata == {"language": "en"}


def test_load_market_agent_reports_falls_back_to_catalog_items(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_legacy.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Legacy Platform",
                    "source_url": "https://legacy.example",
                    "catalog_items": [
                        {
                            "item_id": "legacy-1",
                            "item_title": "Legacy AI Course",
                            "metadata": "legacy-metadata",
                        }
                    ],
                }
            ]
        },
    )

    reports = loader_module.load_market_agent_reports(source_json_path=str(source_path))

    assert len(reports) == 1
    assert reports[0].platform_name == "Legacy Platform"
    assert reports[0].source_url == "https://legacy.example"
    assert len(reports[0].items) == 1
    assert reports[0].items[0].title == "Legacy AI Course"
    assert reports[0].items[0].metadata == {"raw_metadata": "legacy-metadata"}
    assert reports[0].metadata["legacy_catalog_items_present"] is True
    assert "canonical_items_present" not in reports[0].metadata


def test_load_market_agent_reports_uses_latest_file_by_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader_module = _reload_loader_module()

    reports_root = tmp_path / "isolated_reports"
    reports_root.mkdir(parents=True, exist_ok=True)

    older = reports_root / "market_agent_20260101_010101.json"
    newer = reports_root / "market_agent_20240101_010101.json"

    _write_json(
        older,
        {
            "platform_reports": [
                {
                    "platform_name": "Older by mtime",
                    "items": [],
                }
            ]
        },
    )
    _write_json(
        newer,
        {
            "platform_reports": [
                {
                    "platform_name": "Newer by mtime",
                    "items": [],
                }
            ]
        },
    )

    old_ts = 1_700_000_000
    new_ts = old_ts + 100
    os.utime(older, (old_ts, old_ts))
    os.utime(newer, (new_ts, new_ts))

    # Изолируемся от реальной data/reports/market_agent
    monkeypatch.setattr(loader_module, "DEFAULT_REPORTS_ROOT", reports_root)

    def _mock_latest(root: Path = reports_root) -> Path:
        return newer

    monkeypatch.setattr(loader_module, "_latest_market_agent_json", _mock_latest)

    reports = loader_module.load_market_agent_reports()

    assert len(reports) == 1
    assert reports[0].platform_name == "Newer by mtime"


def test_load_market_agent_reports_uses_expanduser_for_explicit_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "market_agent_home.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Home Platform",
                    "items": [],
                }
            ]
        },
    )

    loader_module = _reload_loader_module()

    reports = loader_module.load_market_agent_reports(source_json_path=str(source_path))

    assert len(reports) == 1
    assert reports[0].platform_name == "Home Platform"


def test_load_market_agent_reports_raises_for_missing_file(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    missing_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="Market agent report file not found"):
        loader_module.load_market_agent_reports(source_json_path=str(missing_path))


def test_load_market_agent_reports_raises_for_non_object_top_level(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_bad.json"
    source_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected top-level JSON object"):
        loader_module.load_market_agent_reports(source_json_path=str(source_path))


def test_load_market_agent_reports_raises_for_invalid_platform_reports_type(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_bad_platform_reports.json"
    _write_json(source_path, {"platform_reports": {}})

    with pytest.raises(ValueError, match="Expected 'platform_reports' in"):
        loader_module.load_market_agent_reports(source_json_path=str(source_path))


def test_load_market_agent_reports_wraps_platform_build_errors(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_invalid_platform.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_url": "https://broken.example",
                    "items": [],
                }
            ]
        },
    )

    with pytest.raises(ValueError, match=r"Failed to build platform_reports\[0\]"):
        loader_module.load_market_agent_reports(source_json_path=str(source_path))


def test_load_market_agent_reports_collects_report_metadata(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_meta.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Meta Platform",
                    "platform_url": "https://meta.example/platform",
                    "source_url": "https://meta.example/source",
                    "items": [],
                    "source_meta": {"crawler": "firecrawl"},
                    "pages": [{"url": "https://meta.example/page-1"}],
                    "analytics": {"items_seen": 15},
                    "summary_markdown": "# Summary",
                    "artifacts": {"raw_html": "saved"},
                    "platform_slug": "meta-platform",
                }
            ]
        },
    )

    reports = loader_module.load_market_agent_reports(source_json_path=str(source_path))
    metadata = reports[0].metadata

    assert metadata["source_meta"] == {"crawler": "firecrawl"}
    assert metadata["pages"] == [{"url": "https://meta.example/page-1"}]
    assert metadata["analytics"] == {"items_seen": 15}
    assert metadata["summary_markdown"] == "# Summary"
    assert metadata["artifacts"] == {"raw_html": "saved"}
    assert metadata["platform_slug"] == "meta-platform"
    assert metadata["source_url"] == "https://meta.example/source"
    assert metadata["platform_url"] == "https://meta.example/platform"
    assert metadata["canonical_items_present"] is True


def test_load_market_agent_reports_normalizes_string_lists_and_scalars(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_lists.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Normalization Platform",
                    "items": [
                        {
                            "item_id": "item-1",
                            "title": "  Course Title  ",
                            "tags_raw": "single-tag",
                            "ai_topics": [" llm_foundations ", None, ""],
                            "audience_types": None,
                            "provider_name": " Provider ",
                            "duration_text": " 8 weeks ",
                        }
                    ],
                }
            ]
        },
    )

    reports = loader_module.load_market_agent_reports(source_json_path=str(source_path))
    item = reports[0].items[0]

    assert item.title == "Course Title"
    assert item.tags_raw == ["single-tag"]
    assert item.ai_topics == ["llm_foundations"]
    assert item.audience_types == []
    assert item.provider_name == "Provider"
    assert item.duration_text == "8 weeks"


def test_load_market_agent_reports_rejects_non_list_items_payload(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_bad_items.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Broken Items",
                    "items": {},
                }
            ]
        },
    )

    with pytest.raises(ValueError, match=r"Failed to build platform_reports\[0\]"):
        loader_module.load_market_agent_reports(source_json_path=str(source_path))


def test_load_market_agent_reports_rejects_non_dict_item(tmp_path: Path) -> None:
    loader_module = _reload_loader_module()

    source_path = tmp_path / "market_agent_bad_item_entry.json"
    _write_json(
        source_path,
        {
            "platform_reports": [
                {
                    "platform_name": "Broken Item Entry",
                    "items": ["not-a-dict"],
                }
            ]
        },
    )

    with pytest.raises(ValueError, match=r"Failed to build platform_reports\[0\]"):
        loader_module.load_market_agent_reports(source_json_path=str(source_path))


def test_build_market_analysis_report_bundle_writes_expected_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    expected_keys = {
        "json_report",
        "offer_features_csv",
        "platform_positioning_csv",
        "trend_signals_csv",
        "competitive_gaps_csv",
        "markdown_report",
        "rag_chunks_json",
    }
    assert set(result.keys()) == expected_keys

    for path_str in result.values():
        path = Path(path_str)
        assert path.exists()
        assert path.parent == tmp_path


def test_build_market_analysis_report_bundle_json_contains_bundle_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    payload = json.loads(Path(result["json_report"]).read_text(encoding="utf-8"))

    assert payload["generated_at_utc"] == "2026-07-05T12:00:00Z"
    assert payload["platforms_total"] == 3
    assert len(payload["offer_features"]) == 2


def test_build_market_analysis_report_bundle_offer_csv_contains_expected_columns_and_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    content = _read_text(Path(result["offer_features_csv"])).lstrip("\ufeff")

    topic_a = bundle.offer_features[0].topic_clusters[0]
    topic_b = bundle.offer_features[0].topic_clusters[1]
    core_a = bundle.offer_features[0].core_signals[0]
    core_b = bundle.offer_features[0].core_signals[1]

    assert "platform_name" in content
    assert "Applied AI Foundations" in content
    # topic_clusters в CSV хранятся как ключи, а не label'ы
    assert f"{topic_a} | {topic_b}" in content
    # core_signals в CSV хранятся как label'ы (переведены через CORE_SIGNAL_LABELS)
    assert f"{_label(CORE_SIGNAL_LABELS, core_a)} | {_label(CORE_SIGNAL_LABELS, core_b)}" in content
    assert "Strong applied AI positioning." in content


def test_build_market_analysis_report_bundle_positioning_csv_translates_audience_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    content = _read_text(Path(result["platform_positioning_csv"]))
    topic_a = bundle.platform_positioning[0].dominant_topics[0]
    topic_b = bundle.platform_positioning[0].dominant_topics[1]
    competency_a = bundle.platform_positioning[0].dominant_competency_families[0]
    competency_b = bundle.platform_positioning[0].dominant_competency_families[1]

    assert "начинающие | смена профессии" in content
    assert f"{_label(TOPIC_LABELS, topic_a)} | {_label(TOPIC_LABELS, topic_b)}" in content
    assert f"{_label(COMPETENCY_FAMILY_LABELS, competency_a)} | {_label(COMPETENCY_FAMILY_LABELS, competency_b)}" in content


def test_build_market_analysis_report_bundle_trends_csv_uses_display_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    content = _read_text(Path(result["trend_signals_csv"]))

    assert "topic_label" in content
    assert any(_label(TOPIC_LABELS, key) in content for key in TOPIC_KEYS)
    assert any(label in content for label in CORE_SIGNAL_LABELS.values())
    assert any(label in content for label in COMPETENCY_FAMILY_LABELS.values())


def test_build_market_analysis_report_bundle_gaps_csv_contains_gap_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    content = _read_text(Path(result["competitive_gaps_csv"]))
    topic_b = bundle.competitive_gaps[1].topic

    assert "topic_label" in content
    assert _label(TOPIC_LABELS, topic_b) in content
    assert "0.74" in content
    assert "Platform A | Platform B" in content


def test_build_market_analysis_report_bundle_markdown_contains_core_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    markdown = _read_text(Path(result["markdown_report"]))

    assert "# Исполнительный обзор рынка" in markdown
    assert "## Обзор" in markdown
    assert "## Canonical AI differentiation axes" in markdown
    assert "## Ключевые исполнительные сигналы" in markdown
    assert "## Покрытие направлений" in markdown
    assert "## Интерпретация трендов" in markdown
    assert "## Позиционирование платформ" in markdown
    assert "## Гипотезы по gap-направлениям" in markdown


def test_build_market_analysis_report_bundle_markdown_includes_dense_and_whitespace_topics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    dense_topic_label = _label(TOPIC_LABELS, bundle.competitive_gaps[0].topic)
    whitespace_topic_label = _label(TOPIC_LABELS, bundle.competitive_gaps[1].topic)

    assert f"Перегруженные направления: {dense_topic_label}" in markdown
    assert f"Потенциальные направления-белые пятна: {whitespace_topic_label}" in markdown


def test_build_market_analysis_report_bundle_markdown_formats_core_signal_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    core_a = bundle.offer_features[0].core_signals[0]
    core_b = bundle.offer_features[0].core_signals[1]
    core_c = bundle.offer_features[1].core_signals[0]

    assert "| Ось дифференциации | Key | Количество курсов | Тренд-сигнал | Платформы |" in markdown
    assert f"| {_label(CORE_SIGNAL_LABELS, core_a)} | `{core_a}` | 1 | 0.630 | 2 |" in markdown
    assert f"| {_label(CORE_SIGNAL_LABELS, core_b)} | `{core_b}` | 1 | 0.280 | 1 |" in markdown
    assert f"| {_label(CORE_SIGNAL_LABELS, core_c)} | `{core_c}` | 1 | 0.000 | 0 |" in markdown


def test_build_market_analysis_report_bundle_markdown_formats_topic_coverage_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    topic_a = bundle.trend_signals[0].topic
    topic_b = bundle.competitive_gaps[1].topic
    topic_c = bundle.trend_signals[1].topic

    assert "| Направление | Платформы | Курсы | Сила сигнала | Доля платформ | Потенциал gap |" in markdown
    assert f"| {_label(TOPIC_LABELS, topic_a)} | 2 | 18 | 0.812 | 0.850 | 0.220 |" in markdown
    assert f"| {_label(TOPIC_LABELS, topic_b)} | 0 | 0 | 0.000 | 0.200 | 0.740 |" in markdown
    assert f"| {_label(TOPIC_LABELS, topic_c)} | 1 | 9 | 0.457 | 0.000 | 0.000 |" in markdown


def test_build_market_analysis_report_bundle_markdown_includes_competency_family_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    competency_key = bundle.trend_signals[-1].topic
    competency_label = _label(COMPETENCY_FAMILY_LABELS, competency_key)

    assert "## Сигналы по семействам компетенций" in markdown
    assert f"| {competency_label} | 3 | 25 | 0.880 | This competency family remains dominant. |" in markdown


def test_build_market_analysis_report_bundle_markdown_includes_platform_positioning_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    row_a = bundle.platform_positioning[0]
    row_b = bundle.platform_positioning[1]

    row_a_topics = ", ".join(_label(TOPIC_LABELS, x) for x in row_a.dominant_topics[:4]) or "н/д"
    row_a_competencies = ", ".join(_label(COMPETENCY_FAMILY_LABELS, x) for x in row_a.dominant_competency_families[:4]) or "н/д"
    row_a_signals = ", ".join(_label(CORE_SIGNAL_LABELS, x) for x in row_a.core_signals[:4]) or "н/д"

    row_b_topics = ", ".join(_label(TOPIC_LABELS, x) for x in row_b.dominant_topics[:4]) or "н/д"
    row_b_competencies = ", ".join(_label(COMPETENCY_FAMILY_LABELS, x) for x in row_b.dominant_competency_families[:4]) or "н/д"
    row_b_signals = ", ".join(_label(CORE_SIGNAL_LABELS, x) for x in row_b.core_signals[:4]) or "н/д"

    assert (
        f"| {row_a.platform_name} | {row_a_topics} | {row_a_competencies} | {row_a_signals} | "
        f"начинающие, смена профессии | {row_a.positioning_statement} |"
    ) in markdown
    assert (
        f"| {row_b.platform_name} | {row_b_topics} | {row_b_competencies} | {row_b_signals} | "
        f"работающие специалисты | {row_b.positioning_statement} |"
    ) in markdown


def test_build_market_analysis_report_bundle_markdown_includes_gap_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    gap_a = bundle.competitive_gaps[0]
    gap_b = bundle.competitive_gaps[1]

    assert (
        f"| {_label(TOPIC_LABELS, gap_a.topic)} | 0.850 | 0.220 | Platform B | {gap_a.interpretation} |"
    ) in markdown
    assert f"| {_label(TOPIC_LABELS, gap_b.topic)} | 0.200 | 0.740 | Platform A, Platform B | {gap_b.interpretation} |" in markdown


def test_build_market_analysis_report_bundle_handles_non_string_topic_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    class TopicRef:
        def __init__(self, key: str) -> None:
            self.key = key

    bundle = _build_bundle()
    object_topic = _pick_existing_topic("llm_agents", "automl", "data_engineering")
    bundle.trend_signals.append(
        _make_trend_signal(
            trend_id="trend-6",
            topic=TopicRef(key=object_topic),
            trend_type="topic_cluster",
            platforms_count=2,
            items_count=7,
            platform_share=0.5,
            signal_strength=0.512,
            representative_platforms=["Platform A"],
            evidence_item_ids=["item-7"],
            interpretation="Object-backed topic reference works.",
        )
    )

    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    trend_csv = _read_text(Path(result["trend_signals_csv"]))

    assert object_topic in trend_csv
    assert _label(TOPIC_LABELS, object_topic) in trend_csv


def test_build_market_analysis_report_bundle_omits_core_signal_section_when_no_prevalence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    bundle = _build_bundle()
    for item in bundle.offer_features:
        item.core_signals = []

    result = report_builder_module.build_market_analysis_report_bundle(bundle)
    markdown = _read_text(Path(result["markdown_report"]))

    assert "## Покрытие canonical AI differentiation axes" not in markdown


def test_build_market_analysis_report_bundle_supports_model_dump_like_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_builder_module = _reload_report_builder_module()
    monkeypatch.setattr(report_builder_module, "_DEFAULT_OUTPUT_DIR", tmp_path)

    class ModelDumpBundle:
        def __init__(self) -> None:
            self.generated_at_utc = "2026-07-05T12:00:00Z"
            self.platforms_total = 1
            self.catalog_items_total_raw = 1
            self.catalog_items_total_deduped = 0
            self.catalog_items_total_noise = 0
            self.catalog_items_total_kept = 1
            self.offer_features = []
            self.trend_signals = []
            self.competitive_gaps = []
            self.platform_positioning = []

        def model_dump(self) -> dict[str, Any]:
            return {
                "generated_at_utc": self.generated_at_utc,
                "platforms_total": self.platforms_total,
                "catalog_items_total_raw": self.catalog_items_total_raw,
                "catalog_items_total_deduped": self.catalog_items_total_deduped,
                "catalog_items_total_noise": self.catalog_items_total_noise,
                "catalog_items_total_kept": self.catalog_items_total_kept,
                "offer_features": [{"title": "Serialized via model_dump"}],
                "trend_signals": [],
                "competitive_gaps": [],
                "platform_positioning": [],
            }

    bundle = ModelDumpBundle()
    result = report_builder_module.build_market_analysis_report_bundle(bundle)

    payload = json.loads(Path(result["json_report"]).read_text(encoding="utf-8"))
    assert payload["offer_features"] == [{"title": "Serialized via model_dump"}]