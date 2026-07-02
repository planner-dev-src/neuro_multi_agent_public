from __future__ import annotations

import csv
import json
from pathlib import Path

from src.agents.market_agent.report_builder import build_market_report_bundle


def _sample_platform_report() -> dict:
    return {
        "platform_name": "Example Platform",
        "summary": "Example Platform offers AI courses and certificate tracks.",
        "analysis_summary": "Example Platform offers AI courses and certificate tracks.",
        "fit_for_learning": "high",
        "fit_score": 15,
        "business_model": "b2c_subscription",
        "delivery_model": "self_paced_courses",
        "target_audience": ["individual_learners", "professionals"],
        "top_categories": ["courses", "skills", "credentials"],
        "category_scores": {
            "courses": 5,
            "skills": 4,
            "credentials": 2,
        },
        "highlights": [
            "Offers project-based AI learning.",
            "Provides certificates for several tracks.",
        ],
        "pricing_signals": [
            "Monthly subscription available.",
        ],
        "risks": [],
        "text_stats": {
            "chars": 1200,
            "tokens": 180,
            "unique_terms": 95,
            "top_terms": ["ai", "course", "certificate"],
        },
        "analysis_meta": {
            "contains_ai_terms": True,
            "contains_pricing_terms": True,
            "contains_enterprise_terms": False,
            "contains_credentials_terms": True,
        },
        "source_meta": {
            "pages_total": 2,
            "pages_ok": 2,
            "pages_error": 0,
            "crawler_access_mode": "offline_snapshot",
            "snapshot_hits": 2,
            "page_results": [
                {
                    "url": "https://example.com/catalog",
                    "status": "ok",
                    "access_mode": "offline_snapshot",
                    "raw_html_path": "/tmp/catalog.html",
                    "text_length": 700,
                },
                {
                    "url": "https://example.com/course-1",
                    "status": "ok",
                    "access_mode": "offline_snapshot",
                    "raw_html_path": "/tmp/course-1.html",
                    "text_length": 500,
                },
            ],
        },
    }


def test_build_market_report_bundle_creates_markdown_json_and_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.agents.market_agent.report_builder.REPORTS_ROOT",
        tmp_path,
    )

    report = _sample_platform_report()

    bundle = build_market_report_bundle(
        agent_name="market_agent",
        platform_reports=[report],
    )

    assert "markdown" in bundle
    assert "json" in bundle
    assert "csv" in bundle

    markdown_path = Path(bundle["markdown"])
    json_path = Path(bundle["json"])
    csv_path = Path(bundle["csv"])

    assert markdown_path.exists()
    assert markdown_path.is_file()
    assert json_path.exists()
    assert json_path.is_file()
    assert csv_path.exists()
    assert csv_path.is_file()


def test_build_market_report_bundle_writes_expected_json_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.agents.market_agent.report_builder.REPORTS_ROOT",
        tmp_path,
    )

    report = _sample_platform_report()

    bundle = build_market_report_bundle(
        agent_name="market_agent",
        platform_reports=[report],
    )

    json_path = Path(bundle["json"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["agent_name"] == "market_agent"
    assert payload["platforms_total"] == 1
    assert len(payload["platform_reports"]) == 1

    platform = payload["platform_reports"][0]
    assert platform["platform_name"] == "Example Platform"
    assert platform["fit_for_learning"] == "high"
    assert platform["fit_score"] == 15
    assert platform["business_model"] == "b2c_subscription"
    assert platform["delivery_model"] == "self_paced_courses"
    assert platform["source_meta"]["pages_total"] == 2
    assert platform["source_meta"]["pages_ok"] == 2
    assert platform["source_meta"]["pages_error"] == 0


def test_build_market_report_bundle_writes_expected_markdown_content(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.agents.market_agent.report_builder.REPORTS_ROOT",
        tmp_path,
    )

    report = _sample_platform_report()

    bundle = build_market_report_bundle(
        agent_name="market_agent",
        platform_reports=[report],
    )

    markdown_path = Path(bundle["markdown"])
    markdown_text = markdown_path.read_text(encoding="utf-8")

    assert "# market_agent" in markdown_text
    assert "## Example Platform" in markdown_text
    assert "Example Platform offers AI courses and certificate tracks." in markdown_text
    assert "high" in markdown_text
    assert "b2c_subscription" in markdown_text
    assert "self_paced_courses" in markdown_text


def test_build_market_report_bundle_writes_expected_csv_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.agents.market_agent.report_builder.REPORTS_ROOT",
        tmp_path,
    )

    report = _sample_platform_report()

    bundle = build_market_report_bundle(
        agent_name="market_agent",
        platform_reports=[report],
    )

    csv_path = Path(bundle["csv"])

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1

    row = rows[0]
    assert row["platform_name"] == "Example Platform"
    assert row["fit_for_learning"] == "high"
    assert row["fit_score"] == "15"
    assert row["business_model"] == "b2c_subscription"
    assert row["delivery_model"] == "self_paced_courses"


def test_build_market_report_bundle_handles_multiple_platforms(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.agents.market_agent.report_builder.REPORTS_ROOT",
        tmp_path,
    )

    first = _sample_platform_report()
    second = _sample_platform_report() | {
        "platform_name": "Second Platform",
        "summary": "Second Platform focuses on enterprise AI enablement.",
        "analysis_summary": "Second Platform focuses on enterprise AI enablement.",
        "fit_for_learning": "medium",
        "fit_score": 9,
        "business_model": "b2b",
        "delivery_model": "cohort_or_live",
    }

    bundle = build_market_report_bundle(
        agent_name="market_agent",
        platform_reports=[first, second],
    )

    json_path = Path(bundle["json"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["platforms_total"] == 2
    assert len(payload["platform_reports"]) == 2
    assert payload["platform_reports"][0]["platform_name"] == "Example Platform"
    assert payload["platform_reports"][1]["platform_name"] == "Second Platform"

    csv_path = Path(bundle["csv"])
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2
    assert rows[0]["platform_name"] == "Example Platform"
    assert rows[1]["platform_name"] == "Second Platform"