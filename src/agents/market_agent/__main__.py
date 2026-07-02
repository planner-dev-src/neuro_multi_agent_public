from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.agents.market_agent import MarketAgent, load_platforms_from_csv
from src.agents.market_agent.pipeline import INPUT_CSV_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.agents.market_agent",
        description="Run market_agent pipeline",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=INPUT_CSV_PATH,
        help="Path to platforms CSV file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of platforms to process; 0 means all",
    )
    parser.add_argument(
        "--platform",
        action="append",
        default=[],
        help="Platform name to include; may be provided multiple times",
    )
    return parser.parse_args()


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def select_platforms(platforms: list[dict], names: list[str], limit: int) -> list[dict]:
    selected = list(platforms)

    if names:
        wanted = {_normalize_name(name) for name in names}
        selected = [
            platform
            for platform in selected
            if _normalize_name(platform.get("name", "")) in wanted
        ]

    if limit > 0:
        selected = selected[:limit]

    return selected


def print_run_summary(payload: dict) -> None:
    platform_reports = payload.get("platform_reports", []) or []

    print(f"platforms_total: {len(platform_reports)}")

    for report in platform_reports:
        source_meta = report.get("source_meta", {}) or {}
        analytics = report.get("analytics", {}) or {}
        normalized_entities = analytics.get("normalized_entities", {}) or {}

        platform_name = report.get("platform_name", "unknown")
        pages_ok = source_meta.get("pages_ok", 0)
        pages_total = source_meta.get("pages_total", 0)
        items_total = source_meta.get(
            "catalog_items_total",
            normalized_entities.get("catalog_items_total", 0),
        )
        access_mode = source_meta.get("crawler_access_mode", "")
        access_modes_used = source_meta.get("access_modes_used", []) or []

        print(
            f"- {platform_name}: "
            f"pages_ok={pages_ok}/{pages_total}, "
            f"catalog_items_total={items_total}, "
            f"mode={access_mode}, "
            f"used={','.join(str(x) for x in access_modes_used) or '-'}"
        )

    files = payload.get("files", {}) or {}
    if files:
        print("files:")
        for key, value in files.items():
            print(f"  {key}: {value}")


def main() -> int:
    args = parse_args()

    platforms = load_platforms_from_csv(args.csv)
    selected_platforms = select_platforms(
        platforms=platforms,
        names=args.platform,
        limit=args.limit,
    )

    if not selected_platforms:
        print("No platforms selected.", file=sys.stderr)
        return 2

    agent = MarketAgent()
    result = agent.run(platforms=selected_platforms)

    payload = result.payload if isinstance(result.payload, dict) else {}
    print_run_summary(payload)

    platform_reports = payload.get("platform_reports", []) or []
    has_success = any(
        (report.get("source_meta", {}) or {}).get("pages_ok", 0) > 0
        for report in platform_reports
    )

    return 0 if has_success else 1


if __name__ == "__main__":
    raise SystemExit(main())