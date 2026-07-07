from __future__ import annotations

import csv
import json
from pathlib import Path

from src.agents.market_agent.crawler_config import CrawlerConfig
from src.agents.market_agent.pipeline import MarketAgent


def test_market_agent_smoke_offline_snapshot(tmp_path, monkeypatch):
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)

    html = """
    <html>
      <head><title>Test Platform</title></head>
      <body>
        <main>
          <h1>Test Platform</h1>
          <p>This platform offers AI courses, certificates, and project-based learning.</p>
          <p>It supports enterprise training and individual subscriptions.</p>
        </main>
      </body>
    </html>
    """.strip()

    snapshot_file = snapshot_root / "example.com__platform.html"
    snapshot_file.write_text(html, encoding="utf-8")

    reports_root = tmp_path / "reports"
    text_root = tmp_path / "market_text"

    monkeypatch.setattr(
        "src.agents.market_agent.report_builder.REPORTS_ROOT",
        reports_root,
        raising=False,
    )
    monkeypatch.setattr(
        "src.agents.market_agent.extractor.TEXT_OUTPUT_ROOT",
        text_root,
        raising=False,
    )

    def fake_analyze_platform_text(platform_name: str, text: str) -> dict:
        lowered = text.lower()
        return {
            "platform_name": platform_name,
            "summary": text[:200],
            "items": [
                {
                    "item_id": "example-platform__catalog__1",
                    "title": "Applied AI Course",
                    "description": "Hands-on AI course with certificate and projects.",
                    "canonical_url": "https://example.com/platform/course/applied-ai",
                    "source_url": "https://example.com/platform",
                    "category_hint": "ai_course",
                    "category_raw": "course",
                    "item_type": "course",
                    "provider_name": platform_name,
                    "tags_raw": ["ai", "certificate", "project-based"],
                    "ai_topics": ["machine_learning", "applied_ai"],
                    "audience_types": ["individuals", "enterprise"],
                    "duration_text": "6 weeks",
                    "duration_hours": 24,
                    "difficulty_level": "beginner",
                    "certificate_available": "yes",
                    "project_based": True,
                    "mentor_support": False,
                    "job_support": None,
                    "metadata": {
                        "detected_from_text": True,
                        "fit_for_learning": "high" if "courses" in lowered else "unknown",
                    },
                }
            ],
        }

    monkeypatch.setattr(
        "src.agents.market_agent.pipeline.analyze_platform_text",
        fake_analyze_platform_text,
    )

    agent = MarketAgent()

    result = agent.run(
        platforms=[
            {
                "name": "Example Platform",
                "category": "education",
                "priority": "high",
                "notes": "offline snapshot smoke test",
                "urls": ["https://example.com/platform"],
            }
        ],
        crawler_config=CrawlerConfig(
            access_mode="offline_snapshot",
            snapshot_root=snapshot_root,
        ),
    )

    assert result.status == "success"
    assert result.agent_name == "market_agent"

    payload = result.payload
    assert isinstance(payload, dict)
    assert "platform_reports" in payload
    assert "files" in payload

    platform_reports = payload["platform_reports"]
    assert isinstance(platform_reports, list)
    assert len(platform_reports) == 1

    report = platform_reports[0]
    assert report["platform_name"] == "Example Platform"
    assert "summary" in report
    assert "source_meta" in report

    assert "items" in report or "catalog_items" in report
    report_items = report.get("items") or report.get("catalog_items") or []
    assert isinstance(report_items, list)
    assert len(report_items) == 1

    first_item = report_items[0]
    assert first_item["title"] == "Applied AI Course"
    assert first_item["item_type"] == "course"
    assert first_item["provider_name"] == "Example Platform"
    assert first_item["canonical_url"] == "https://example.com/platform/course/applied-ai"

    source_meta = report["source_meta"]
    assert source_meta["pages_total"] == 1
    assert source_meta["pages_ok"] == 1
    assert source_meta["pages_error"] == 0
    assert source_meta["crawler_access_mode"] == "offline_snapshot"
    assert source_meta["snapshot_hits"] == 1

    page_results = source_meta["page_results"]
    assert isinstance(page_results, list)
    assert len(page_results) == 1
    assert page_results[0]["status"] == "ok"
    assert page_results[0]["access_mode"] == "offline_snapshot"
    assert page_results[0]["raw_html_path"] is not None
    assert page_results[0]["text_length"] > 0

    files = payload["files"]
    markdown_path = Path(files["markdown"])
    json_path = Path(files["json"])
    csv_path = Path(files["csv"])

    assert markdown_path.exists()
    assert markdown_path.is_file()
    assert json_path.exists()
    assert json_path.is_file()
    assert csv_path.exists()
    assert csv_path.is_file()

    assert text_root.exists()
    saved_text_files = list(text_root.rglob("*.txt"))
    assert len(saved_text_files) >= 1

    saved_text = saved_text_files[0].read_text(encoding="utf-8")
    assert "AI courses" in saved_text or "ai courses" in saved_text.lower()

    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_payload["agent_name"] == "market_agent"
    assert json_payload["platforms_total"] == 1
    assert len(json_payload["platform_reports"]) == 1

    json_report = json_payload["platform_reports"][0]
    assert json_report["platform_name"] == "Example Platform"
    assert "source_meta" in json_report
    assert "items" in json_report or "catalog_items" in json_report

    json_items = json_report.get("items") or json_report.get("catalog_items") or []
    assert len(json_items) == 1
    assert json_items[0]["title"] == "Applied AI Course"

    markdown_text = markdown_path.read_text(encoding="utf-8")
    assert "# market_agent" in markdown_text
    assert "## Example Platform" in markdown_text
    assert "Applied AI Course" in markdown_text or "Example Platform" in markdown_text

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows
    assert "platform_name" in rows[0]
    assert any(row["platform_name"] == "Example Platform" for row in rows)