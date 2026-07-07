from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.run_market_agent import main


def _write_input_file(tmp_path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> Path:
    input_path = tmp_path / "platforms.json"
    input_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return input_path


def test_cli_main_success_with_platforms_key(tmp_path, monkeypatch, capsys):
    input_path = _write_input_file(
        tmp_path,
        {
            "platforms": [
                {
                    "name": "Example Platform",
                    "category": "education",
                    "priority": "high",
                    "notes": "cli test",
                    "urls": ["https://example.com/platform"],
                }
            ]
        },
    )

    class FakeResult:
        status = "success"
        agent_name = "market_agent"
        payload = {
            "platform_reports": [{"platform_name": "Example Platform"}],
            "files": {
                "markdown": str(tmp_path / "report.md"),
                "json": str(tmp_path / "report.json"),
                "csv": str(tmp_path / "report.csv"),
            },
        }

    captured: dict[str, Any] = {}

    class FakeMarketAgent:
        def run(self, *, platforms, crawler_config):
            captured["platforms"] = platforms
            captured["crawler_config"] = crawler_config
            return FakeResult()

    monkeypatch.setattr(
        "scripts.run_market_agent.MarketAgent",
        FakeMarketAgent,
    )

    exit_code = main(
        [
            str(input_path),
            "--access-mode",
            "offline_snapshot",
            "--snapshot-root",
            str(tmp_path / "snapshots"),
            "--timeout-seconds",
            "12",
            "--max-retries",
            "4",
            "--retry-backoff-seconds",
            "2.5",
            "--proxy-env-enabled",
            "--use-system-env-by-default",
            "--allowed-domain",
            "example.com",
            "--denied-domain",
            "forbidden.example",
        ]
    )

    out = capsys.readouterr()

    assert exit_code == 0
    assert out.err == ""

    payload = json.loads(out.out)
    assert payload["status"] == "success"
    assert payload["agent_name"] == "market_agent"
    assert payload["payload"]["platform_reports"][0]["platform_name"] == "Example Platform"

    assert len(captured["platforms"]) == 1
    assert captured["platforms"][0]["name"] == "Example Platform"

    crawler_config = captured["crawler_config"]
    assert crawler_config.access_mode == "offline_snapshot"
    assert crawler_config.snapshot_root == Path(tmp_path / "snapshots")
    assert crawler_config.timeout_seconds == 12.0
    assert crawler_config.max_retries == 4
    assert crawler_config.retry_backoff_seconds == 2.5
    assert crawler_config.proxy_env_enabled is True
    assert crawler_config.use_system_env_by_default is True
    assert crawler_config.allowed_domains == ["example.com"]
    assert crawler_config.denied_domains == ["forbidden.example"]


def test_cli_main_success_with_top_level_list_payload(tmp_path, monkeypatch, capsys):
    input_path = _write_input_file(
        tmp_path,
        [
            {
                "name": "Platform A",
                "urls": ["https://example.com/a"],
            },
            {
                "name": "Platform B",
                "urls": ["https://example.com/b"],
            },
        ],
    )

    class FakeResult:
        status = "success"
        agent_name = "market_agent"
        payload = {"platform_reports": [], "files": {}}

    captured: dict[str, Any] = {}

    class FakeMarketAgent:
        def run(self, *, platforms, crawler_config):
            captured["platforms"] = platforms
            captured["crawler_config"] = crawler_config
            return FakeResult()

    monkeypatch.setattr(
        "scripts.run_market_agent.MarketAgent",
        FakeMarketAgent,
    )

    exit_code = main([str(input_path)])

    out = capsys.readouterr()

    assert exit_code == 0
    assert out.err == ""

    payload = json.loads(out.out)
    assert payload["status"] == "success"
    assert payload["agent_name"] == "market_agent"

    assert len(captured["platforms"]) == 2
    assert captured["platforms"][0]["name"] == "Platform A"
    assert captured["platforms"][1]["name"] == "Platform B"

    crawler_config = captured["crawler_config"]
    assert crawler_config.access_mode == "live_direct"
    assert crawler_config.snapshot_root == Path("data/market_snapshots")
    assert crawler_config.max_retries == 2


def test_cli_main_returns_error_when_input_file_missing(tmp_path, capsys):
    missing_path = tmp_path / "missing.json"

    exit_code = main([str(missing_path)])

    out = capsys.readouterr()

    assert exit_code == 1
    assert out.out == ""

    payload = json.loads(out.err)
    assert payload["status"] == "error"
    assert "Input file not found" in payload["error"]


def test_cli_main_returns_error_when_input_json_is_not_object_or_list(tmp_path, capsys):
    input_path = tmp_path / "invalid.json"
    input_path.write_text('"just a string"', encoding="utf-8")

    exit_code = main([str(input_path)])

    out = capsys.readouterr()

    assert exit_code == 1
    assert out.out == ""

    payload = json.loads(out.err)
    assert payload["status"] == "error"
    assert "top-level object" in payload["error"]


def test_cli_main_returns_error_when_platforms_value_is_not_a_list(tmp_path, capsys):
    input_path = _write_input_file(
        tmp_path,
        {"platforms": {"name": "bad-shape"}},
    )

    exit_code = main([str(input_path)])

    out = capsys.readouterr()

    assert exit_code == 1
    assert out.out == ""

    payload = json.loads(out.err)
    assert payload["status"] == "error"
    assert "must contain a 'platforms' list" in payload["error"]


def test_cli_main_returns_error_when_platform_entry_is_not_an_object(tmp_path, capsys):
    input_path = _write_input_file(
        tmp_path,
        {"platforms": ["bad-entry"]},
    )

    exit_code = main([str(input_path)])

    out = capsys.readouterr()

    assert exit_code == 1
    assert out.out == ""

    payload = json.loads(out.err)
    assert payload["status"] == "error"
    assert "must be an object" in payload["error"]


def test_cli_main_returns_exit_code_2_when_agent_result_is_not_success(tmp_path, monkeypatch, capsys):
    input_path = _write_input_file(
        tmp_path,
        {
            "platforms": [
                {
                    "name": "Example Platform",
                    "urls": ["https://example.com/platform"],
                }
            ]
        },
    )

    class FakeResult:
        status = "partial"
        agent_name = "market_agent"
        payload = {"platform_reports": [], "files": {}}

    class FakeMarketAgent:
        def run(self, *, platforms, crawler_config):
            return FakeResult()

    monkeypatch.setattr(
        "scripts.run_market_agent.MarketAgent",
        FakeMarketAgent,
    )

    exit_code = main([str(input_path)])

    out = capsys.readouterr()

    assert exit_code == 2
    assert out.err == ""

    payload = json.loads(out.out)
    assert payload["status"] == "partial"
    assert payload["agent_name"] == "market_agent"


def test_cli_main_returns_error_when_agent_raises_exception(tmp_path, monkeypatch, capsys):
    input_path = _write_input_file(
        tmp_path,
        {
            "platforms": [
                {
                    "name": "Example Platform",
                    "urls": ["https://example.com/platform"],
                }
            ]
        },
    )

    class FakeMarketAgent:
        def run(self, *, platforms, crawler_config):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "scripts.run_market_agent.MarketAgent",
        FakeMarketAgent,
    )

    exit_code = main([str(input_path)])

    out = capsys.readouterr()

    assert exit_code == 1
    assert out.out == ""

    payload = json.loads(out.err)
    assert payload["status"] == "error"
    assert payload["error"] == "boom"