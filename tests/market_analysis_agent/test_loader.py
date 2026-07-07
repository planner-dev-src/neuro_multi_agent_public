from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from src.agents.market_analysis_agent.loader import (
    _as_dict,
    _as_list,
    _build_catalog_item,
    _build_platform_report,
    _coerce_optional_bool,
    _coerce_optional_float,
    _extract_catalog_items,
    _extract_report_metadata,
    _latest_market_agent_json,
    load_market_agent_reports,
)


@pytest.fixture
def reports_root(tmp_path: Path) -> Path:
    root = tmp_path / "data" / "reports" / "market_agent"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def sample_item_payload() -> dict[str, Any]:
    return {
        "item_id": "course-1",
        "title": "Intro to AI",
        "description": "Basics",
        "canonical_url": "https://example.com/course-1",
        "source_url": "https://example.com/source-1",
        "category_hint": "ai",
        "category_raw": "AI",
        "item_type": "course",
        "provider_name": "Example Academy",
        "tags_raw": ["ai", "ml"],
        "ai_topics": ["machine_learning"],
        "audience_types": ["beginners"],
        "duration_text": "10 hours",
        "duration_hours": "10",
        "difficulty_level": "beginner",
        "certificate_available": "true",
        "project_based": "false",
        "mentor_support": "yes",
        "job_support": "0",
        "metadata": {"language": "en"},
    }


@pytest.fixture
def sample_platform_report(sample_item_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform_name": "Example Platform",
        "platform_url": "https://example.com",
        "source_url": "https://example.com/source",
        "platform_slug": "example-platform",
        "items": [sample_item_payload],
        "source_meta": {"origin": "crawler"},
        "pages": [{"url": "https://example.com/catalog"}],
        "analytics": {"items_seen": 1},
        "summary_markdown": "# Summary",
        "artifacts": {"raw_html": "artifact.html"},
    }


@pytest.fixture
def sample_payload(sample_platform_report: dict[str, Any]) -> dict[str, Any]:
    return {"platform_reports": [sample_platform_report]}


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_latest_market_agent_json_picks_most_recent_file_by_mtime(reports_root: Path) -> None:
    older = reports_root / "market_agent_20250101_010101.json"
    newer = reports_root / "market_agent_20240101_010101.json"

    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")

    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    result = _latest_market_agent_json(reports_root)

    assert result == newer


def test_latest_market_agent_json_ignores_non_matching_files(reports_root: Path) -> None:
    ignored = reports_root / "not_market_agent.json"
    valid = reports_root / "market_agent_20250101_010101.json"

    ignored.write_text("{}", encoding="utf-8")
    valid.write_text("{}", encoding="utf-8")

    os.utime(valid, (2000, 2000))

    result = _latest_market_agent_json(reports_root)

    assert result == valid


def test_latest_market_agent_json_raises_when_root_missing(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        _latest_market_agent_json(missing_root)


def test_latest_market_agent_json_raises_when_no_candidates(reports_root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No market_agent JSON reports found"):
        _latest_market_agent_json(reports_root)


def test_as_dict_returns_dict() -> None:
    payload = {"a": 1}
    assert _as_dict(payload, context="payload") == payload


@pytest.mark.parametrize("value", [None, [], "x", 1])
def test_as_dict_raises_for_non_dict(value: object) -> None:
    with pytest.raises(ValueError, match="Expected payload to be an object"):
        _as_dict(value, context="payload")


def test_as_list_returns_empty_for_none() -> None:
    assert _as_list(None, context="items") == []


def test_as_list_returns_list() -> None:
    assert _as_list([1, 2], context="items") == [1, 2]


@pytest.mark.parametrize("value", [{}, "x", 1])
def test_as_list_raises_for_non_list(value: object) -> None:
    with pytest.raises(ValueError, match="Expected items to be a list"):
        _as_list(value, context="items")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (1, 1.0),
        (1.5, 1.5),
        ("2.75", 2.75),
        (" bad ", None),
    ],
)
def test_coerce_optional_float(value: object, expected: float | None) -> None:
    assert _coerce_optional_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, True),
        (False, False),
        ("true", True),
        ("1", True),
        ("yes", True),
        ("y", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("n", False),
        ("maybe", None),
    ],
)
def test_coerce_optional_bool(value: object, expected: bool | None) -> None:
    assert _coerce_optional_bool(value) == expected


def test_build_catalog_item_maps_fields(sample_item_payload: dict[str, Any]) -> None:
    item = _build_catalog_item(sample_item_payload, platform_name="Example Platform")

    assert item.platform_name == "Example Platform"
    assert item.item_id == "course-1"
    assert item.title == "Intro to AI"
    assert item.description == "Basics"
    assert item.duration_hours == 10.0
    assert item.certificate_available is True
    assert item.project_based is False
    assert item.mentor_support is True
    assert item.job_support is False
    assert item.tags_raw == ["ai", "ml"]
    assert item.ai_topics == ["machine_learning"]
    assert item.audience_types == ["beginners"]
    assert item.metadata == {"language": "en"}


def test_build_catalog_item_strips_scalar_string_fields(sample_item_payload: dict[str, Any]) -> None:
    payload = dict(sample_item_payload)
    payload["item_id"] = "  course-1  "
    payload["title"] = "  Intro to AI  "
    payload["description"] = "  Basics  "

    item = _build_catalog_item(payload, platform_name="Example Platform")

    assert item.item_id == "course-1"
    assert item.title == "Intro to AI"
    assert item.description == "Basics"


def test_build_catalog_item_wraps_non_dict_metadata(sample_item_payload: dict[str, Any]) -> None:
    payload = dict(sample_item_payload)
    payload["metadata"] = "raw-meta"

    item = _build_catalog_item(payload, platform_name="Example Platform")

    assert item.metadata == {"raw_metadata": "raw-meta"}


def test_build_catalog_item_normalizes_string_like_lists(sample_item_payload: dict[str, Any]) -> None:
    payload = dict(sample_item_payload)
    payload["tags_raw"] = "ai"
    payload["ai_topics"] = None
    payload["audience_types"] = [" beginners ", None, ""]

    item = _build_catalog_item(payload, platform_name="Example Platform")

    assert item.tags_raw == ["ai"]
    assert item.ai_topics == []
    assert item.audience_types == ["beginners"]


def test_extract_catalog_items_prefers_items_key(sample_platform_report: dict[str, Any]) -> None:
    items = _extract_catalog_items(sample_platform_report, platform_name="Example Platform")

    assert len(items) == 1
    assert items[0].item_id == "course-1"


def test_extract_catalog_items_falls_back_to_catalog_items(sample_item_payload: dict[str, Any]) -> None:
    raw_report = {
        "platform_name": "Legacy Platform",
        "catalog_items": [sample_item_payload],
    }

    items = _extract_catalog_items(raw_report, platform_name="Legacy Platform")

    assert len(items) == 1
    assert items[0].title == "Intro to AI"


def test_extract_catalog_items_raises_for_non_dict_item() -> None:
    raw_report = {
        "platform_name": "Broken Platform",
        "items": ["not-a-dict"],
    }

    with pytest.raises(ValueError, match=r"items\[0\]"):
        _extract_catalog_items(raw_report, platform_name="Broken Platform")


def test_extract_report_metadata_collects_supported_fields(sample_platform_report: dict[str, Any]) -> None:
    metadata = _extract_report_metadata(sample_platform_report)

    assert metadata["source_meta"] == {"origin": "crawler"}
    assert metadata["pages"] == [{"url": "https://example.com/catalog"}]
    assert metadata["analytics"] == {"items_seen": 1}
    assert metadata["summary_markdown"] == "# Summary"
    assert metadata["artifacts"] == {"raw_html": "artifact.html"}
    assert metadata["platform_slug"] == "example-platform"
    assert metadata["canonical_items_present"] is True
    assert metadata["source_url"] == "https://example.com/source"
    assert metadata["platform_url"] == "https://example.com"


def test_extract_report_metadata_marks_legacy_catalog_items(sample_item_payload: dict[str, Any]) -> None:
    metadata = _extract_report_metadata(
        {
            "platform_name": "Legacy Platform",
            "catalog_items": [sample_item_payload],
        }
    )

    assert metadata["legacy_catalog_items_present"] is True
    assert "canonical_items_present" not in metadata


def test_build_platform_report_builds_domain_object(sample_platform_report: dict[str, Any]) -> None:
    report = _build_platform_report(sample_platform_report, 0)

    assert report.platform_name == "Example Platform"
    assert report.source_url == "https://example.com"
    assert len(report.items) == 1
    assert report.items[0].title == "Intro to AI"
    assert report.metadata["platform_slug"] == "example-platform"


def test_build_platform_report_falls_back_to_source_url(sample_item_payload: dict[str, Any]) -> None:
    raw_report = {
        "platform_name": "Example Platform",
        "source_url": "https://example.com/source-only",
        "items": [sample_item_payload],
    }

    report = _build_platform_report(raw_report, 0)

    assert report.source_url == "https://example.com/source-only"


def test_build_platform_report_raises_when_platform_name_missing(
    sample_platform_report: dict[str, Any],
) -> None:
    broken = dict(sample_platform_report)
    broken["platform_name"] = "   "

    with pytest.raises(ValueError, match="missing required field 'platform_name'"):
        _build_platform_report(broken, 0)


def test_load_market_agent_reports_reads_explicit_source_json_path(
    tmp_path: Path,
    sample_payload: dict[str, Any],
) -> None:
    json_path = tmp_path / "market_agent_manual.json"
    _write_json(json_path, sample_payload)

    reports = load_market_agent_reports(source_json_path=str(json_path))

    assert len(reports) == 1
    assert reports[0].platform_name == "Example Platform"
    assert reports[0].items[0].item_id == "course-1"


def test_load_market_agent_reports_expands_user_in_source_json_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample_payload: dict[str, Any],
) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir(parents=True, exist_ok=True)

    json_path = fake_home / "market_agent_manual.json"
    _write_json(json_path, sample_payload)

    monkeypatch.setenv("HOME", str(fake_home))

    reports = load_market_agent_reports(source_json_path="~/market_agent_manual.json")

    assert len(reports) == 1
    assert reports[0].platform_name == "Example Platform"


def test_load_market_agent_reports_uses_latest_file_from_default_root(
    monkeypatch: pytest.MonkeyPatch,
    reports_root: Path,
    sample_payload: dict[str, Any],
) -> None:
    older = reports_root / "market_agent_20250101_000001.json"
    newer = reports_root / "market_agent_20250101_000002.json"
    _write_json(older, sample_payload)
    _write_json(newer, sample_payload)

    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    monkeypatch.setattr(
        "src.agents.market_analysis_agent.loader.DEFAULT_REPORTS_ROOT",
        reports_root,
    )

    reports = load_market_agent_reports()

    assert len(reports) == 1
    assert reports[0].platform_name == "Example Platform"


def test_load_market_agent_reports_raises_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="Market agent report file not found"):
        load_market_agent_reports(source_json_path=str(missing))


def test_load_market_agent_reports_raises_for_non_object_top_level(tmp_path: Path) -> None:
    json_path = tmp_path / "market_agent_bad.json"
    json_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected top-level JSON object"):
        load_market_agent_reports(source_json_path=str(json_path))


def test_load_market_agent_reports_raises_for_non_list_platform_reports(tmp_path: Path) -> None:
    json_path = tmp_path / "market_agent_bad.json"
    _write_json(json_path, {"platform_reports": {}})

    with pytest.raises(ValueError, match=r"Expected 'platform_reports' in .* to be a list|Expected 'platform_reports'"):
        load_market_agent_reports(source_json_path=str(json_path))


def test_load_market_agent_reports_wraps_platform_build_errors(
    tmp_path: Path,
    sample_platform_report: dict[str, Any],
) -> None:
    broken = dict(sample_platform_report)
    broken["platform_name"] = ""

    json_path = tmp_path / "market_agent_bad.json"
    _write_json(json_path, {"platform_reports": [broken]})

    with pytest.raises(ValueError, match=r"Failed to build platform_reports\[0\]"):
        load_market_agent_reports(source_json_path=str(json_path))


def test_load_market_agent_reports_accepts_catalog_items_legacy_shape(
    tmp_path: Path,
    sample_item_payload: dict[str, Any],
) -> None:
    payload = {
        "platform_reports": [
            {
                "platform_name": "Legacy Platform",
                "source_url": "https://legacy.example.com",
                "catalog_items": [sample_item_payload],
            }
        ]
    }
    json_path = tmp_path / "market_agent_legacy.json"
    _write_json(json_path, payload)

    reports = load_market_agent_reports(source_json_path=str(json_path))

    assert len(reports) == 1
    assert reports[0].platform_name == "Legacy Platform"
    assert len(reports[0].items) == 1
    assert reports[0].metadata["legacy_catalog_items_present"] is True


def test_load_market_agent_reports_returns_empty_list_when_platform_reports_missing(tmp_path: Path) -> None:
    json_path = tmp_path / "market_agent_empty.json"
    _write_json(json_path, {})

    reports = load_market_agent_reports(source_json_path=str(json_path))

    assert reports == []