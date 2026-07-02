from pathlib import Path

from src.orchestrators.workflow import run_agent


def test_market_agent_smoke():
    demo_platforms = [
        {
            "name": "demo_ai_platform",
            "category": "test",
            "priority": "1",
            "notes": "Self-paced AI platform with projects, webinars, career services and MLOps content.",
            "urls": [],
        }
    ]

    result = run_agent("market_agent", platforms=demo_platforms)

    assert result.agent_name == "market_agent"
    assert result.status == "success"
    assert "report" in result.payload
    assert "files" in result.payload

    report = result.payload["report"]
    assert report["platform_count"] == 1
    assert len(report["platforms"]) == 1

    platform = report["platforms"][0]
    assert platform["name"] == "demo_ai_platform"
    assert "summary" in platform
    assert "directions_found" in platform
    assert "criteria_found" in platform
    assert "directions_details" in platform
    assert "criteria_details" in platform
    assert "source_meta" in platform

    files = result.payload["files"]
    assert Path(files["json"]).exists()
    assert Path(files["markdown"]).exists()
    assert Path(files["csv"]).exists()