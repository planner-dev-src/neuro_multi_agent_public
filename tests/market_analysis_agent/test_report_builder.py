from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from src.agents.market_analysis_agent.report_builder import (
    _build_markdown,
    _bundle_to_dict,
    _core_signal_prevalence,
    _display_label,
    _fmt_float,
    _gap_topic_key,
    _join_list,
    _safe_float,
    _timestamp,
    _topic_gap_map,
    _topic_trend_map,
    _trend_topic_key,
    build_market_analysis_report_bundle,
)


@dataclass
class FakeOfferFeature:
    platform_name: str = "Platform A"
    item_id: str = "item-1"
    title: str = "Intro to LLMs"
    item_title: str = ""
    canonical_url: str = "https://example.com/course"
    item_type: str = "course"
    normalized_title: str = "intro to llms"
    text_fingerprint: str = "fp-1"
    topic_clusters: list[str] = field(default_factory=lambda: ["llm_applications"])
    competency_families: list[str] = field(default_factory=lambda: ["ai_engineering"])
    audience_segments: list[str] = field(default_factory=lambda: ["beginners"])
    core_signals: list[str] = field(default_factory=lambda: ["project_based_learning"])
    format_signals: list[str] = field(default_factory=lambda: ["cohort"])
    outcome_signals: list[str] = field(default_factory=lambda: ["career_transition"])
    support_signals: list[str] = field(default_factory=lambda: ["mentor_support"])
    intensity_signals: list[str] = field(default_factory=lambda: ["part_time"])
    value_props: list[str] = field(default_factory=lambda: ["practical"])
    duration_bucket: str = "short"
    difficulty_bucket: str = "beginner"
    quality_score: float = 0.91
    is_noise: bool = False
    noise_reasons: list[str] = field(default_factory=list)
    evidence_text: str = "Hands-on projects with mentor support."


@dataclass
class FakePlatformPositioning:
    platform_name: str = "Platform A"
    audience_focus: list[str] = field(default_factory=lambda: ["beginners", "working_professionals"])
    value_props: list[str] = field(default_factory=lambda: ["practical", "career-focused"])
    core_signals: list[str] = field(default_factory=lambda: ["project_based_learning"])
    pedagogy_style: list[str] = field(default_factory=lambda: ["hands-on"])
    career_signals: list[str] = field(default_factory=lambda: ["portfolio"])
    academic_signals: list[str] = field(default_factory=lambda: ["instructor-led"])
    execution_model: list[str] = field(default_factory=lambda: ["cohort"])
    dominant_topics: list[str] = field(default_factory=lambda: ["llm_applications"])
    dominant_competency_families: list[str] = field(default_factory=lambda: ["ai_engineering"])
    positioning_statement: str = "Практико-ориентированная платформа для быстрого входа в AI."


@dataclass
class FakeTrendSignal:
    trend_id: str
    topic: Any
    trend_type: str
    platforms_count: int
    items_count: int
    platform_share: float
    signal_strength: float
    representative_platforms: list[str]
    evidence_item_ids: list[str]
    interpretation: str


@dataclass
class FakeCompetitiveGap:
    topic: Any
    gap_type: str
    platforms_count: int
    platform_share: float
    underrepresented_platforms: list[str]
    opportunity_score: float
    interpretation: str
    evidence_item_ids: list[str]


@dataclass
class FakeMarketAnalysisBundle:
    generated_at_utc: str = "2026-07-05T05:00:00Z"
    platforms_total: int = 3
    catalog_items_total_raw: int = 120
    catalog_items_total_deduped: int = 15
    catalog_items_total_noise: int = 10
    catalog_items_total_kept: int = 95
    offer_features: list[FakeOfferFeature] = field(default_factory=list)
    platform_positioning: list[FakePlatformPositioning] = field(default_factory=list)
    trend_signals: list[FakeTrendSignal] = field(default_factory=list)
    competitive_gaps: list[FakeCompetitiveGap] = field(default_factory=list)


@dataclass
class TopicObj:
    key: str


@pytest.fixture
def fake_bundle() -> FakeMarketAnalysisBundle:
    return FakeMarketAnalysisBundle(
        offer_features=[
            FakeOfferFeature(),
            FakeOfferFeature(
                platform_name="Platform B",
                item_id="item-2",
                title="AI Product Builder",
                core_signals=["project_based_learning"],
                topic_clusters=["llm_applications"],
            ),
        ],
        platform_positioning=[
            FakePlatformPositioning(),
            FakePlatformPositioning(
                platform_name="Platform B",
                audience_focus=["working_professionals"],
                dominant_topics=["llm_applications"],
                positioning_statement="Платформа для практиков, усиливающих AI delivery.",
            ),
        ],
        trend_signals=[
            FakeTrendSignal(
                trend_id="t1",
                topic="llm_applications",
                trend_type="topic_cluster",
                platforms_count=2,
                items_count=14,
                platform_share=0.67,
                signal_strength=0.82,
                representative_platforms=["Platform A", "Platform B"],
                evidence_item_ids=["item-1", "item-2"],
                interpretation="Сильный рыночный интерес к прикладным LLM-программам.",
            ),
            FakeTrendSignal(
                trend_id="t2",
                topic="project_based_learning",
                trend_type="core_signal",
                platforms_count=2,
                items_count=12,
                platform_share=0.67,
                signal_strength=0.74,
                representative_platforms=["Platform A", "Platform B"],
                evidence_item_ids=["item-1", "item-2"],
                interpretation="Практический формат часто используется как основной differentiator.",
            ),
            FakeTrendSignal(
                trend_id="t3",
                topic=TopicObj("ai_engineering"),
                trend_type="competency_family",
                platforms_count=2,
                items_count=18,
                platform_share=0.67,
                signal_strength=0.79,
                representative_platforms=["Platform A", "Platform B"],
                evidence_item_ids=["item-1", "item-2"],
                interpretation="AI engineering остаётся одним из самых устойчивых competency-кластеров.",
            ),
        ],
        competitive_gaps=[
            FakeCompetitiveGap(
                topic="llm_applications",
                gap_type="topic_cluster",
                platforms_count=2,
                platform_share=0.83,
                underrepresented_platforms=["Platform C"],
                opportunity_score=0.58,
                interpretation="Высокий спрос сочетается с пространством для более глубокого differentiated offering.",
                evidence_item_ids=["item-1"],
            ),
        ],
    )


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "data" / "reports" / "market_analysis_agent"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_timestamp_format() -> None:
    value = _timestamp()
    assert len(value) == 15
    assert value[8] == "_"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0.0),
        ("", 0.0),
        ("1.25", 1.25),
        (2, 2.0),
        ("bad", 0.0),
    ],
)
def test_safe_float(value: object, expected: float) -> None:
    assert _safe_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0.000"),
        (1.23456, "1.235"),
        ("2.5", "2.500"),
        ("bad", "0.000"),
    ],
)
def test_fmt_float(value: object, expected: str) -> None:
    assert _fmt_float(value) == expected


def test_join_list_handles_lists_strings_and_none() -> None:
    assert _join_list(["a", "b"]) == "a | b"
    assert _join_list("abc") == "abc"
    assert _join_list(None) == ""


def test_join_list_strips_empty_values_from_list() -> None:
    assert _join_list([" a ", "", None, "b "]) == "a | b"


def test_trend_topic_key_extracts_from_string() -> None:
    item = type("Obj", (), {"topic": "llm_applications"})()
    assert _trend_topic_key(item) == "llm_applications"


def test_trend_topic_key_extracts_from_key_object() -> None:
    item = type("Obj", (), {"topic": TopicObj("ai_engineering")})()
    assert _trend_topic_key(item) == "ai_engineering"


def test_gap_topic_key_uses_string_value() -> None:
    item = type("Obj", (), {"topic": "llm_applications"})()
    assert _gap_topic_key(item) == "llm_applications"


def test_display_label_returns_fallback_for_unknown_topic() -> None:
    assert _display_label("unknown_topic", "topic_cluster") == "unknown_topic"


def test_bundle_to_dict_supports_dataclass(fake_bundle: FakeMarketAnalysisBundle) -> None:
    payload = _bundle_to_dict(fake_bundle)

    assert payload["generated_at_utc"] == "2026-07-05T05:00:00Z"
    assert len(payload["offer_features"]) == 2
    assert len(payload["trend_signals"]) == 3


def test_topic_gap_map_contains_topic_cluster_items(fake_bundle: FakeMarketAnalysisBundle) -> None:
    result = _topic_gap_map(fake_bundle)

    assert "llm_applications" in result
    assert result["llm_applications"].gap_type == "topic_cluster"


def test_topic_trend_map_contains_topic_cluster_items(fake_bundle: FakeMarketAnalysisBundle) -> None:
    result = _topic_trend_map(fake_bundle)

    assert "llm_applications" in result
    assert result["llm_applications"].trend_type == "topic_cluster"


def test_core_signal_prevalence_counts_in_canonical_order(fake_bundle: FakeMarketAnalysisBundle) -> None:
    result = dict(_core_signal_prevalence(fake_bundle))

    assert result["project_based_learning"] == 2


def test_build_markdown_contains_expected_sections(fake_bundle: FakeMarketAnalysisBundle) -> None:
    markdown = _build_markdown(fake_bundle)

    assert "# Исполнительный обзор рынка" in markdown
    assert "## Обзор" in markdown
    assert "## Ключевые исполнительные сигналы" in markdown
    assert "## Покрытие направлений" in markdown
    assert "## Позиционирование платформ" in markdown
    assert "## Гипотезы по gap-направлениям" in markdown
    assert "Platform A" in markdown
    assert "Platform B" in markdown


def test_build_markdown_renders_numeric_values_with_fixed_precision(
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    markdown = _build_markdown(fake_bundle)

    assert "0.820" in markdown
    assert "0.830" in markdown
    assert "0.580" in markdown
    assert "0.740" in markdown


def test_build_market_analysis_report_bundle_writes_all_expected_files(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)

    assert set(result.keys()) == {
        "json_report",
        "offer_features_csv",
        "platform_positioning_csv",
        "trend_signals_csv",
        "competitive_gaps_csv",
        "markdown_report",
    }

    for path_str in result.values():
        assert Path(path_str).exists()


def test_build_market_analysis_report_bundle_writes_valid_json(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)
    json_path = Path(result["json_report"])

    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["generated_at_utc"] == "2026-07-05T05:00:00Z"
    assert len(payload["offer_features"]) == 2
    assert len(payload["trend_signals"]) == 3


def test_build_market_analysis_report_bundle_writes_offer_features_csv(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)
    rows = _read_csv_rows(Path(result["offer_features_csv"]))

    assert len(rows) == 2
    assert rows[0]["platform_name"] == "Platform A"
    assert rows[0]["item_id"] == "item-1"
    assert rows[0]["topic_clusters"] == "llm_applications"
    assert rows[0]["quality_score"] == "0.91"
    assert rows[0]["is_noise"] == "False"


def test_build_market_analysis_report_bundle_writes_platform_positioning_csv(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)
    rows = _read_csv_rows(Path(result["platform_positioning_csv"]))

    assert len(rows) == 2
    assert rows[0]["platform_name"] == "Platform A"
    assert "начинающие" in rows[0]["audience_focus"]
    assert rows[0]["positioning_statement"]


def test_build_market_analysis_report_bundle_writes_trend_signals_csv(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)
    rows = _read_csv_rows(Path(result["trend_signals_csv"]))

    assert len(rows) == 3
    topic_row = next(row for row in rows if row["trend_id"] == "t1")
    assert topic_row["topic"] == "llm_applications"
    assert topic_row["trend_type"] == "topic_cluster"
    assert topic_row["signal_strength"] == "0.82"


def test_build_market_analysis_report_bundle_writes_competitive_gaps_csv(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)
    rows = _read_csv_rows(Path(result["competitive_gaps_csv"]))

    assert len(rows) == 1
    assert rows[0]["topic"] == "llm_applications"
    assert rows[0]["gap_type"] == "topic_cluster"
    assert rows[0]["opportunity_score"] == "0.58"


def test_build_market_analysis_report_bundle_writes_markdown_report(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)
    markdown = Path(result["markdown_report"]).read_text(encoding="utf-8")

    assert "# Исполнительный обзор рынка" in markdown
    assert "## Сигналы по семействам компетенций" in markdown
    assert "Platform A" in markdown
    assert "Практико-ориентированная платформа" in markdown


def test_build_market_analysis_report_bundle_creates_output_dir_if_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_bundle: FakeMarketAnalysisBundle,
) -> None:
    output_dir = tmp_path / "fresh-output"
    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(fake_bundle)

    assert output_dir.exists()
    assert Path(result["json_report"]).parent == output_dir


def test_build_market_analysis_report_bundle_supports_object_topic_values(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
) -> None:
    bundle = FakeMarketAnalysisBundle(
        offer_features=[FakeOfferFeature()],
        platform_positioning=[FakePlatformPositioning()],
        trend_signals=[
            FakeTrendSignal(
                trend_id="t-obj",
                topic=TopicObj("ai_engineering"),
                trend_type="competency_family",
                platforms_count=1,
                items_count=3,
                platform_share=0.33,
                signal_strength=0.61,
                representative_platforms=["Platform A"],
                evidence_item_ids=["item-1"],
                interpretation="Object-based topic key should be resolved correctly.",
            )
        ],
        competitive_gaps=[
            FakeCompetitiveGap(
                topic=TopicObj("llm_applications"),
                gap_type="topic_cluster",
                platforms_count=1,
                platform_share=0.4,
                underrepresented_platforms=["Platform B"],
                opportunity_score=0.7,
                interpretation="Gap topic object should also be resolved.",
                evidence_item_ids=["item-1"],
            )
        ],
    )

    monkeypatch.setattr(
        "src.agents.market_analysis_agent.report_builder.DEFAULT_OUTPUT_DIR",
        output_dir,
    )

    result = build_market_analysis_report_bundle(bundle)

    trend_rows = _read_csv_rows(Path(result["trend_signals_csv"]))
    gap_rows = _read_csv_rows(Path(result["competitive_gaps_csv"]))

    assert trend_rows[0]["topic"] == "ai_engineering"
    assert gap_rows[0]["topic"] == "llm_applications"