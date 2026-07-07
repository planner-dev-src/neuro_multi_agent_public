from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.market_agent.pipeline import INPUT_CSV_PATH, MarketAgent, load_platforms_from_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test runner for market_agent",
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
        default=3,
        help="Maximum number of platforms to process",
    )
    parser.add_argument(
        "--platform",
        action="append",
        default=[],
        help="Platform name to include; may be provided multiple times",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to save smoke summary JSON",
    )
    return parser.parse_args()


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def select_platforms(platforms: list[dict], names: list[str], limit: int) -> list[dict]:
    if names:
        wanted = {_normalize_name(name) for name in names}
        selected = [
            platform
            for platform in platforms
            if _normalize_name(platform.get("name", "")) in wanted
        ]
    else:
        selected = list(platforms)

    if limit > 0:
        selected = selected[:limit]

    return selected


def build_smoke_summary(result_payload: dict) -> dict:
    platform_reports = result_payload.get("platform_reports", []) or []

    platforms_total = len(platform_reports)
    pages_total = 0
    pages_ok = 0
    pages_error = 0
    documents_total = 0
    catalog_items_total = 0
    snapshot_hits = 0
    proxy_hits = 0
    direct_hits = 0
    live_fetch_count = 0
    failed_urls: list[str] = []
    access_modes_used: set[str] = set()

    platform_summaries: list[dict] = []

    for report in platform_reports:
        platform_name = report.get("platform_name", "unknown")
        source_meta = report.get("source_meta", {}) or {}
        analytics = report.get("analytics", {}) or {}
        normalized_entities = analytics.get("normalized_entities", {}) or {}

        platform_pages_total = int(source_meta.get("pages_total", 0) or 0)
        platform_pages_ok = int(source_meta.get("pages_ok", 0) or 0)
        platform_pages_error = int(source_meta.get("pages_error", 0) or 0)
        platform_documents_total = int(source_meta.get("documents_total", 0) or 0)
        platform_catalog_items_total = int(
            source_meta.get(
                "catalog_items_total",
                normalized_entities.get("catalog_items_total", 0),
            )
            or 0
        )
        platform_snapshot_hits = int(source_meta.get("snapshot_hits", 0) or 0)
        platform_proxy_hits = int(source_meta.get("proxy_hits", 0) or 0)
        platform_direct_hits = int(source_meta.get("direct_hits", 0) or 0)
        platform_live_fetch_count = int(source_meta.get("live_fetch_count", 0) or 0)
        platform_failed_urls = source_meta.get("failed_urls", []) or []
        platform_access_modes = source_meta.get("access_modes_used", []) or []

        pages_total += platform_pages_total
        pages_ok += platform_pages_ok
        pages_error += platform_pages_error
        documents_total += platform_documents_total
        catalog_items_total += platform_catalog_items_total
        snapshot_hits += platform_snapshot_hits
        proxy_hits += platform_proxy_hits
        direct_hits += platform_direct_hits
        live_fetch_count += platform_live_fetch_count
        failed_urls.extend(str(url) for url in platform_failed_urls if url)

        for mode in platform_access_modes:
            if mode:
                access_modes_used.add(str(mode))

        platform_summaries.append(
            {
                "platform_name": platform_name,
                "crawler_access_mode": source_meta.get("crawler_access_mode", ""),
                "access_modes_used": platform_access_modes,
                "pages_total": platform_pages_total,
                "pages_ok": platform_pages_ok,
                "pages_error": platform_pages_error,
                "documents_total": platform_documents_total,
                "catalog_items_total": platform_catalog_items_total,
                "snapshot_hits": platform_snapshot_hits,
                "proxy_hits": platform_proxy_hits,
                "direct_hits": platform_direct_hits,
                "live_fetch_count": platform_live_fetch_count,
                "failed_urls": platform_failed_urls,
            }
        )

    success = platforms_total > 0 and pages_ok > 0

    return {
        "success": success,
        "platforms_total": platforms_total,
        "pages_total": pages_total,
        "pages_ok": pages_ok,
        "pages_error": pages_error,
        "documents_total": documents_total,
        "catalog_items_total": catalog_items_total,
        "snapshot_hits": snapshot_hits,
        "proxy_hits": proxy_hits,
        "direct_hits": direct_hits,
        "live_fetch_count": live_fetch_count,
        "access_modes_used": sorted(access_modes_used),
        "failed_urls": failed_urls,
        "platform_summaries": platform_summaries,
        "generated_files": result_payload.get("files", {}),
    }


def print_human_summary(summary: dict) -> None:
    print(f"success: {summary['success']}")
    print(f"platforms_total: {summary['platforms_total']}")
    print(f"pages_total: {summary['pages_total']}")
    print(f"pages_ok: {summary['pages_ok']}")
    print(f"pages_error: {summary['pages_error']}")
    print(f"documents_total: {summary['documents_total']}")
    print(f"catalog_items_total: {summary['catalog_items_total']}")
    print(f"snapshot_hits: {summary['snapshot_hits']}")
    print(f"proxy_hits: {summary['proxy_hits']}")
    print(f"direct_hits: {summary['direct_hits']}")
    print(f"live_fetch_count: {summary['live_fetch_count']}")
    print(f"access_modes_used: {', '.join(summary['access_modes_used']) or '-'}")

    if summary["failed_urls"]:
        print("failed_urls:")
        for url in summary["failed_urls"]:
            print(f"  - {url}")

    print("platform_summaries:")
    for platform in summary["platform_summaries"]:
        print(
            f"  - {platform['platform_name']}: "
            f"pages_ok={platform['pages_ok']}/{platform['pages_total']}, "
            f"items={platform['catalog_items_total']}, "
            f"mode={platform['crawler_access_mode']}"
        )


def save_summary_json(output_path: Path, summary: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    platforms = load_platforms_from_csv(args.csv)
    selected_platforms = select_platforms(
        platforms=platforms,
        names=args.platform,
        limit=args.limit,
    )

    if not selected_platforms:
        print("No platforms selected for smoke test.", file=sys.stderr)
        return 2

    agent = MarketAgent()
    result = agent.run(platforms=selected_platforms)

    payload = result.payload if isinstance(result.payload, dict) else {}
    summary = build_smoke_summary(payload)

    print_human_summary(summary)

    if args.output_json is not None:
        save_summary_json(args.output_json, summary)

    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())