from __future__ import annotations

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
    )
    monkeypatch.setattr(
        "src.agents.market_agent.extractor.TEXT_OUTPUT_ROOT",
        text_root,
    )

    def fake_analyze_platform_text(platform_name: str, text: str) -> dict:
        return {
            "platform_name": platform_name,
            "summary": text[:200],
            "fit_for_learning": "high" if "courses" in text.lower() else "unknown",
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
    assert "platform_reports" in payload
    assert "files" in payload

    platform_reports = payload["platform_reports"]
    assert len(platform_reports) == 1

    report = platform_reports[0]
    assert report["platform_name"] == "Example Platform"
    assert "summary" in report
    assert "source_meta" in report

    source_meta = report["source_meta"]
    assert source_meta["pages_total"] == 1
    assert source_meta["pages_ok"] == 1
    assert source_meta["pages_error"] == 0
    assert source_meta["crawler_access_mode"] == "offline_snapshot"
    assert source_meta["snapshot_hits"] == 1

    page_results = source_meta["page_results"]
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

    markdown_text = markdown_path.read_text(encoding="utf-8")
    assert "# market_agent" in markdown_text
    assert "## Example Platform" in markdown_text

    csv_text = csv_path.read_text(encoding="utf-8-sig")
    assert "platform_name" in csv_text
    assert "Example Platform" in csv_text