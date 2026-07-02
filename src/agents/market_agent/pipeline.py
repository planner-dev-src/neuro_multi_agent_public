from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.agents.base.agent import BaseAgent
from src.agents.base.models import AgentResult
from src.agents.market_agent import extractor
from src.agents.market_agent.analyzer import build_platform_analytics_from_items
from src.agents.market_agent.crawler import MarketCrawler
from src.agents.market_agent.crawler_config import CrawlerConfig
from src.agents.market_agent.normalizer import normalize_documents_to_catalog_items
from src.agents.market_agent.report_builder import (
    save_csv_report,
    save_json_report,
    save_markdown_report,
)
from src.agents.market_agent.types import (
    MarketAgentPayloadDict,
    PageResultDict,
    PlatformReportDict,
    SourceMetaDict,
)

INPUT_CSV_PATH = Path("data/input/platforms.csv")

AccessMode = Literal["live_direct", "live_proxy", "offline_snapshot"]

CATEGORY_ORDER: dict[str, int] = {
    "ru": 0,
    "global": 1,
}


def _normalize_category(value: str | None) -> str:
    return (value or "").strip().lower()


def _priority_as_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 999


def _platform_sort_key(platform: dict[str, Any]) -> tuple[int, int, str]:
    category = _normalize_category(platform.get("category"))
    priority = _priority_as_int(platform.get("priority"))
    name = str(platform.get("name", "") or "").strip().lower()
    return (
        CATEGORY_ORDER.get(category, 999),
        priority,
        name,
    )


def _slugify_platform_name(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = normalized.strip("_")
    return normalized or "platform"


def _extract_text_from_html(html: str) -> str:
    normalized_html = (html or "").strip()
    if not normalized_html:
        return ""

    try:
        soup = BeautifulSoup(normalized_html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if text:
            return text
    except Exception:
        pass

    text = re.sub(r"<[^>]+>", " ", normalized_html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _save_platform_text(platform_name: str, text: str) -> Path:
    output_root = Path(extractor.TEXT_OUTPUT_ROOT)
    output_root.mkdir(parents=True, exist_ok=True)

    file_name = f"{_slugify_platform_name(platform_name)}.txt"
    file_path = output_root / file_name
    file_path.write_text(text or "", encoding="utf-8")
    return file_path


def load_platforms_from_csv(
    csv_path: Path = INPUT_CSV_PATH,
    *,
    only_ru: bool = True,
) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Platforms CSV not found: {csv_path}")

    platforms: list[dict[str, Any]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            name = (row.get("name", "") or "").strip()
            if not name:
                continue

            raw_urls = (row.get("urls", "") or "").strip()
            urls = [item.strip() for item in raw_urls.split("|") if item.strip()]

            platform = {
                "name": name,
                "category": (row.get("category", "") or "").strip(),
                "priority": (row.get("priority", "") or "").strip(),
                "notes": (row.get("notes", "") or "").strip(),
                "urls": urls,
            }

            if only_ru and _normalize_category(platform.get("category")) != "ru":
                continue

            platforms.append(platform)

    platforms.sort(key=_platform_sort_key)
    return platforms


def build_crawler_config_for_platform(platform: dict[str, Any]) -> CrawlerConfig:
    notes = str(platform.get("notes", "") or "").lower()
    urls_value = platform.get("urls", []) or []
    urls = [str(url) for url in urls_value]

    access_mode: AccessMode = "live_direct"
    if "vpn" in notes or "proxy" in notes:
        access_mode = "live_proxy"
    if "offline" in notes or "snapshot" in notes:
        access_mode = "offline_snapshot"

    allowed_domains: list[str] = []
    for url in urls:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.strip().lower()
            if domain:
                allowed_domains.append(domain)
        except Exception:
            continue

    return CrawlerConfig(
        access_mode=access_mode,
        proxy_env_enabled=(access_mode == "live_proxy"),
        allowed_domains=allowed_domains,
    )


def build_crawler_config_with_overrides(
    base_config: CrawlerConfig,
    overrides: dict[str, Any] | None,
) -> CrawlerConfig:
    if not overrides:
        return base_config

    access_mode = cast(
        AccessMode,
        overrides.get("access_mode", base_config.access_mode),
    )
    proxy_env_enabled = cast(
        bool,
        overrides.get("proxy_env_enabled", base_config.proxy_env_enabled),
    )
    allowed_domains = cast(
        list[str],
        overrides.get("allowed_domains", base_config.allowed_domains),
    )
    snapshot_root = cast(
        Path,
        overrides.get("snapshot_root", base_config.snapshot_root),
    )
    user_agent = cast(
        str,
        overrides.get("user_agent", base_config.user_agent),
    )

    return CrawlerConfig(
        access_mode=access_mode,
        proxy_env_enabled=proxy_env_enabled,
        allowed_domains=allowed_domains,
        snapshot_root=snapshot_root,
        user_agent=user_agent,
    )


def fetch_documents_with_meta(
    platform_name: str,
    urls: list[str],
    crawler: MarketCrawler,
) -> tuple[list[Any], list[PageResultDict]]:
    documents: list[Any] = []
    page_results: list[PageResultDict] = []

    for index, url in enumerate(urls, start=1):
        page_result: PageResultDict

        try:
            document = crawler.fetch_one(url)
            documents.append(document)

            html = getattr(document, "html", "") or ""
            text = getattr(document, "text", "") or ""
            if not text and html:
                text = _extract_text_from_html(html)

            title_hint = getattr(document, "title_hint", None)
            document_meta = getattr(document, "meta", {}) or {}

            page_result = {
                "page_index": index,
                "url": url,
                "status": "ok",
                "status_code": getattr(document, "status_code", None),
                "final_url": getattr(document, "final_url", url),
                "content_type": getattr(document, "content_type", None),
                "encoding": getattr(document, "encoding", None),
                "html_length": len(html),
                "text_length": len(text),
                "raw_html_path": document_meta.get("snapshot_path"),
                "access_mode": getattr(document, "access_mode", crawler.config.access_mode),
                "fetch_meta": document_meta,
                "preview": text[:300],
                "title_hint": title_hint,
                "platform_name": platform_name,
            }

            if not getattr(document, "text", "") and text:
                try:
                    setattr(document, "text", text)
                except Exception:
                    pass

        except Exception as e:
            page_result = {
                "page_index": index,
                "url": url,
                "status": "error",
                "error": str(e),
                "access_mode": crawler.config.access_mode,
                "platform_name": platform_name,
            }

        page_results.append(page_result)

    return documents, page_results


def analyze_platform_text(platform_name: str, text: str) -> dict[str, Any]:
    normalized_text = (text or "").strip()
    lowered = normalized_text.lower()

    fit_for_learning = "unknown"
    learning_markers = [
        "course",
        "courses",
        "learning",
        "certificate",
        "certificates",
        "program",
        "programs",
        "training",
        "lessons",
    ]
    if any(marker in lowered for marker in learning_markers):
        fit_for_learning = "high"

    summary = normalized_text[:500]
    if not summary:
        summary = f"No text extracted for {platform_name}."

    return {
        "platform_name": platform_name,
        "summary": summary,
        "fit_for_learning": fit_for_learning,
    }


class MarketAgent(BaseAgent):
    name = "market_agent"

    def run(
        self,
        platforms: list[dict[str, Any]] | None = None,
        crawler_config: CrawlerConfig | None = None,
        crawler_config_overrides: dict[str, Any] | None = None,
        only_ru: bool = True,
    ) -> AgentResult:
        if platforms is None:
            platforms = load_platforms_from_csv(only_ru=only_ru)
        else:
            platforms = sorted(platforms, key=_platform_sort_key)

        platform_reports: list[PlatformReportDict] = []

        for platform in platforms:
            platform_name = str(platform.get("name", "unknown"))
            platform_urls_value = platform.get("urls", []) or []
            platform_urls = [str(url) for url in platform_urls_value]

            if crawler_config is not None:
                platform_crawler_config = crawler_config
            else:
                base_config = build_crawler_config_for_platform(platform)
                platform_crawler_config = build_crawler_config_with_overrides(
                    base_config=base_config,
                    overrides=crawler_config_overrides,
                )

            crawler = MarketCrawler(platform_crawler_config)

            documents, page_results = fetch_documents_with_meta(
                platform_name=platform_name,
                urls=platform_urls,
                crawler=crawler,
            )

            combined_text_parts: list[str] = []
            for document in documents:
                text_value = getattr(document, "text", "") or ""
                if not text_value:
                    html_value = getattr(document, "html", "") or ""
                    text_value = _extract_text_from_html(html_value)

                if text_value:
                    combined_text_parts.append(str(text_value))

            combined_text = "\n\n".join(combined_text_parts)
            text_analysis = analyze_platform_text(
                platform_name=platform_name,
                text=combined_text,
            )

            text_file_path = _save_platform_text(
                platform_name=platform_name,
                text=combined_text,
            )

            catalog_items = normalize_documents_to_catalog_items(
                platform_name=platform_name,
                documents=documents,
            )

            analytics = build_platform_analytics_from_items(
                platform_name=platform_name,
                items=catalog_items,
            )

            ok_pages = [page for page in page_results if page.get("status") == "ok"]
            error_pages = [page for page in page_results if page.get("status") != "ok"]
            snapshot_hits = [
                page for page in ok_pages
                if page.get("access_mode") == "offline_snapshot"
            ]
            proxy_hits = [
                page for page in ok_pages
                if page.get("access_mode") == "live_proxy"
            ]
            direct_hits = [
                page for page in ok_pages
                if page.get("access_mode") == "live_direct"
            ]
            failed_urls = [str(page.get("url")) for page in error_pages if page.get("url")]
            access_modes_used = sorted(
                {
                    str(page.get("access_mode"))
                    for page in ok_pages
                    if page.get("access_mode")
                }
            )

            source_meta: SourceMetaDict = {
                "category": str(platform.get("category", "") or ""),
                "priority": str(platform.get("priority", "") or ""),
                "notes": str(platform.get("notes", "") or ""),
                "urls": platform_urls,
                "pages_total": len(page_results),
                "pages_ok": len(ok_pages),
                "pages_error": len(error_pages),
                "pages_failed": len(error_pages),
                "page_results": page_results,
                "crawler_access_mode": platform_crawler_config.access_mode,
                "access_modes_used": access_modes_used,
                "snapshot_hits": len(snapshot_hits),
                "proxy_hits": len(proxy_hits),
                "direct_hits": len(direct_hits),
                "live_fetch_count": len(direct_hits) + len(proxy_hits),
                "failed_urls": failed_urls,
                "documents_total": len(documents),
                "catalog_items_total": len(catalog_items),
                "text_output_path": str(text_file_path),
                "text_length_total": len(combined_text),
            }

            platform_report: PlatformReportDict = {
                "platform_name": platform_name,
                "summary": str(text_analysis.get("summary", "") or ""),
                "fit_for_learning": str(text_analysis.get("fit_for_learning", "") or ""),
                "analytics": analytics,
                "catalog_items": [
                    {
                        "item_id": item.item_id,
                        "item_type": item.item_type,
                        "title": item.title,
                        "source_url": item.source_url,
                        "canonical_url": item.canonical_url,
                        "difficulty_level": item.difficulty_level,
                        "duration_hours": item.duration_hours,
                        "lessons_count": item.lessons_count,
                        "modules_count": item.modules_count,
                        "ai_topics": item.ai_topics,
                        "audience_types": item.audience_types,
                        "extraction_confidence": item.extraction_confidence,
                    }
                    for item in catalog_items
                ],
                "source_meta": source_meta,
            }

            platform_reports.append(platform_report)

        report_builder_reports = cast(list[dict[str, Any]], platform_reports)

        markdown_path = save_markdown_report(report_builder_reports, agent_name=self.name)
        json_path = save_json_report(report_builder_reports, agent_name=self.name)
        csv_path = save_csv_report(report_builder_reports)

        legacy_report_platforms: list[dict[str, Any]] = []

        for platform_report in platform_reports:
            analytics = platform_report.get("analytics", {}) or {}
            source_meta = platform_report.get("source_meta", {}) or {}

            summary_value = str(platform_report.get("summary", "") or "").strip()
            if not summary_value:
                analytics_summary = analytics.get("summary")
                if isinstance(analytics_summary, str) and analytics_summary.strip():
                    summary_value = analytics_summary.strip()
                elif platform_report.get("catalog_items"):
                    summary_value = f"Catalog items found: {len(platform_report.get('catalog_items', []))}"
                else:
                    summary_value = "No catalog items extracted."

            normalized_entities = analytics.get("normalized_entities", {}) or {}
            coverage = analytics.get("coverage", {}) or {}
            concentration = analytics.get("concentration", {}) or {}
            breadth = analytics.get("breadth", {}) or {}
            depth = analytics.get("depth", {}) or {}

            legacy_report_platforms.append(
                {
                    "name": platform_report.get("platform_name", "unknown"),
                    "summary": summary_value,
                    "fit_for_learning": str(platform_report.get("fit_for_learning", "") or ""),
                    "directions_found": int(normalized_entities.get("courses_total", 0)),
                    "criteria_found": int(normalized_entities.get("programs_total", 0)),
                    "directions_details": {
                        "breadth": breadth,
                        "coverage": coverage,
                    },
                    "criteria_details": {
                        "depth": depth,
                        "concentration": concentration,
                    },
                    "source_meta": source_meta,
                }
            )

        legacy_report: dict[str, Any] = {
            "platform_count": len(legacy_report_platforms),
            "platforms": legacy_report_platforms,
        }

        payload: MarketAgentPayloadDict = {
            "platform_reports": platform_reports,
            "report": legacy_report,
            "files": {
                "markdown": str(markdown_path),
                "json": str(json_path),
                "csv": str(csv_path),
            },
        }

        agent_payload = cast(dict[str, Any], payload)

        return AgentResult(
            agent_name=self.name,
            status="success",
            payload=agent_payload,
            message=f"Analyzed {len(platform_reports)} platforms",
        )