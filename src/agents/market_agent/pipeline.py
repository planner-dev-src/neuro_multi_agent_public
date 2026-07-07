from __future__ import annotations


import csv
import heapq
import re
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse


from src.agents.base.agent import BaseAgent
from src.agents.base.models import AgentResult
from src.agents.market_agent import extractor
from src.agents.market_agent.analyzer import build_platform_analytics_from_items
from src.agents.market_agent.crawler import MarketCrawler
from src.agents.market_agent.crawler_config import CrawlerConfig
from src.agents.market_agent.normalizer import normalize_documents_to_catalog_items
from src.agents.market_agent.report_builder import build_market_report_bundle
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


MAX_PAGES_PER_PLATFORM = 120
MAX_CRAWL_DEPTH = 3


YANDEX_PRAKTIKUM_EXTRA_SEEDS = [
    "https://practicum.yandex.ru/catalog/?from=main_all-courses-first-page_card",
    "https://practicum.yandex.ru/catalog/iskusstvennyj-intellekt/?from=main_ai_card",
    "https://practicum.yandex.ru/catalog/data-analysis/?from=main_data-analysis_card",
    "https://practicum.yandex.ru/catalog/programming/?from=main_programming_card",
    "https://start.practicum.yandex/courses/",
]


HSE_DPO_SEEDS = [
    "https://www.hse.ru/edu/dpo/?tags=867039226&tags=867039230&tags=867039232&tags=867039167&tags=867039231&tags=867039227&tags=867039168&tags=914770513",
    "https://www.hse.ru/edu/dpo/?page=2&tags=867039226&tags=867039230&tags=867039232&tags=867039167&tags=867039231&tags=867039227&tags=867039168&tags=914770513",
    "https://www.hse.ru/edu/dpo/?page=3&tags=867039226&tags=867039230&tags=867039232&tags=867039167&tags=867039231&tags=867039227&tags=867039168&tags=914770513",
]


def _load_seeds(platform_key: str) -> list[str]:
    """Загружает seed-лист из data/input/seeds/, если файл существует."""
    seeds_file = Path(f"data/input/seeds/{platform_key}_seeds.txt")
    if seeds_file.exists():
        return [
            line.strip()
            for line in seeds_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    return []


NETOLOGY_EXTRA_SEEDS = _load_seeds("netology")
SKILLBOX_EXTRA_SEEDS = _load_seeds("skillbox")
OTUS_EXTRA_SEEDS = _load_seeds("otus")
KARPOV_EXTRA_SEEDS = _load_seeds("karpov-courses")



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



def _normalize_url(url: str) -> str:
    return (url or "").strip()



def _url_key(url: str) -> str:
    return _normalize_url(url).lower().rstrip("/")



def _host_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""



def _same_registered_host(url: str, allowed_domains: list[str]) -> bool:
    host = _host_of(url)
    if not host:
        return False


    normalized_allowed: list[str] = []
    for domain in allowed_domains:
        value = (domain or "").strip().lower()
        if value.startswith("www."):
            value = value[4:]
        if value:
            normalized_allowed.append(value)


    return any(host == domain or host.endswith("." + domain) for domain in normalized_allowed)



def _is_program_like_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(
        token in path
        for token in (
            "/course/",
            "/courses/",
            "/profession/",
            "/program/",
            "/programs/",
            "/edu/dpo/",
            "/ycloud/",
            "/python",
            "/java",
            "/data-",
            "/qa-",
            "/frontend",
            "/backend",
        )
    )



def _is_catalog_like_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(
        token in path
        for token in (
            "/catalog",
            "/courses",
            "/navigation",
            "/education",
            "/code",
            "/design",
            "/management",
            "/marketing",
            "/games",
            "/psychology",
            "/engineering",
            "/other",
            "/edu/dpo",
        )
    )



def _link_priority(url: str, *, is_pagination: bool = False) -> int:
    if _is_program_like_url(url):
        return 10
    if is_pagination:
        return 20
    if _is_catalog_like_url(url):
        return 30
    return 100



def _augment_platform_urls(platform: dict[str, Any]) -> list[str]:
    name = str(platform.get("name", "") or "").strip().lower()
    urls = [_normalize_url(str(url)) for url in (platform.get("urls", []) or []) if str(url).strip()]
    extra: list[str] = []


    if "яндекс" in name or "practicum" in name or "практикум" in name:
        extra.extend(YANDEX_PRAKTIKUM_EXTRA_SEEDS)


    if name == "hse" or "higher school of economics" in name or "вшэ" in name:
        extra.extend(HSE_DPO_SEEDS)


    if "otus" in name:
        extra.extend(OTUS_EXTRA_SEEDS)


    if "нетология" in name or "netology" in name:
        extra.extend(NETOLOGY_EXTRA_SEEDS)


    if "skillbox" in name:
        extra.extend(SKILLBOX_EXTRA_SEEDS)


    if "karpov" in name:
        extra.extend(KARPOV_EXTRA_SEEDS)


    deduped: list[str] = []
    seen = set()
    for url in urls + extra:
        key = _url_key(url)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(url)
    return deduped



def build_crawler_config_for_platform(platform: dict[str, Any]) -> CrawlerConfig:
    notes = str(platform.get("notes", "") or "").lower()
    urls_value = platform.get("urls", []) or []
    urls = [str(url) for url in urls_value]
    name = str(platform.get("name", "") or "").strip().lower()


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


    if "яндекс" in name or "practicum" in name or "практикум" in name:
        for extra_domain in ("practicum.yandex.ru", "start.practicum.yandex"):
            if extra_domain not in allowed_domains:
                allowed_domains.append(extra_domain)


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



def _build_page_result(
    *,
    platform_name: str,
    url: str,
    depth: int,
    document: Any,
    text_meta: dict[str, Any],
    discovered_links: list[str],
    pagination_links: list[str],
    html_items_count: int,
    jsonld_items_count: int,
) -> PageResultDict:
    html = getattr(document, "html", "") or ""
    text = getattr(document, "text", "") or text_meta.get("text", "") or ""
    title_hint = getattr(document, "title_hint", None)
    document_meta = getattr(document, "meta", {}) or {}
    effective_url = getattr(document, "final_url", url) or url


    return {
        "page_index": 0,
        "url": url,
        "effective_url": effective_url,
        "status": "ok",
        "status_code": getattr(document, "status_code", None),
        "final_url": getattr(document, "final_url", effective_url),
        "content_type": getattr(document, "content_type", None),
        "encoding": getattr(document, "encoding", None),
        "html_length": len(html),
        "text_length": len(text),
        "raw_html_path": document_meta.get("snapshot_path"),
        "access_mode": getattr(document, "access_mode", None),
        "fetch_meta": document_meta,
        "preview": str(text)[:300],
        "title_hint": title_hint,
        "platform_name": platform_name,
        "crawl_depth": depth,
        "discovered_links_count": len(discovered_links),
        "pagination_links_count": len(pagination_links),
        "catalog_items_html_count": html_items_count,
        "catalog_items_jsonld_count": jsonld_items_count,
        "saved_text_path": text_meta.get("saved_text_path"),
        "text_extraction_method": text_meta.get("extraction_method"),
    }



def _serialize_catalog_item(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        data = item.model_dump()
        if isinstance(data, dict):
            return data


    return {
        "item_id": getattr(item, "item_id", ""),
        "source_platform": getattr(item, "source_platform", ""),
        "source_url": getattr(item, "source_url", ""),
        "canonical_url": getattr(item, "canonical_url", ""),
        "item_type": getattr(item, "item_type", ""),
        "title": getattr(item, "title", ""),
        "description": getattr(item, "description", ""),
        "provider_name": getattr(item, "provider_name", ""),
        "language": getattr(item, "language", ""),
        "category_raw": getattr(item, "category_raw", ""),
        "tags_raw": getattr(item, "tags_raw", []),
        "difficulty_level": getattr(item, "difficulty_level", ""),
        "duration_text": getattr(item, "duration_text", ""),
        "duration_hours": getattr(item, "duration_hours", None),
        "lessons_count": getattr(item, "lessons_count", None),
        "modules_count": getattr(item, "modules_count", None),
        "certificate_available": getattr(item, "certificate_available", None),
        "project_based": getattr(item, "project_based", None),
        "mentor_support": getattr(item, "mentor_support", None),
        "job_support": getattr(item, "job_support", None),
        "ai_topics": getattr(item, "ai_topics", []),
        "audience_types": getattr(item, "audience_types", []),
        "parent_program_id": getattr(item, "parent_program_id", None),
        "child_course_ids": getattr(item, "child_course_ids", []),
        "crawl_depth": getattr(item, "crawl_depth", 0),
        "extraction_confidence": getattr(item, "extraction_confidence", None),
        "extraction_notes": getattr(item, "extraction_notes", []),
    }



def _enqueue_links(
    queue: list[tuple[int, int, str]],
    links: list[str],
    *,
    depth: int,
    max_depth: int,
    allowed_domains: list[str],
    seen_enqueued: set[str],
    is_pagination: bool = False,
) -> int:
    if depth >= max_depth:
        return 0


    added = 0
    next_depth = depth + 1


    for link in links:
        normalized = _normalize_url(link)
        key = _url_key(normalized)
        if not key:
            continue
        if key in seen_enqueued:
            continue
        if allowed_domains and not _same_registered_host(normalized, allowed_domains):
            continue


        priority = _link_priority(normalized, is_pagination=is_pagination)
        seen_enqueued.add(key)
        heapq.heappush(queue, (priority, next_depth, normalized))
        added += 1


    return added



def _crawl_platform_pages(
    *,
    platform_name: str,
    seed_urls: list[str],
    crawler: MarketCrawler,
    max_pages: int = MAX_PAGES_PER_PLATFORM,
    max_depth: int = MAX_CRAWL_DEPTH,
) -> tuple[list[Any], list[dict[str, Any]], list[PageResultDict], str]:
    documents: list[Any] = []
    raw_catalog_items: list[dict[str, Any]] = []
    page_results: list[PageResultDict] = []
    combined_text_parts: list[str] = []


    queue: list[tuple[int, int, str]] = []
    seen_enqueued: set[str] = set()
    seen_fetched: set[str] = set()


    for seed_url in seed_urls:
        normalized = _normalize_url(seed_url)
        key = _url_key(normalized)
        if not key:
            continue
        if key in seen_enqueued:
            continue
        seen_enqueued.add(key)
        heapq.heappush(queue, (0, 0, normalized))


    page_index = 0


    while queue and len(documents) < max_pages:
        _, depth, current_url = heapq.heappop(queue)
        current_key = _url_key(current_url)
        if current_key in seen_fetched:
            continue


        seen_fetched.add(current_key)
        page_index += 1


        try:
            document = crawler.fetch_one(current_url)
            html = getattr(document, "html", "") or ""
            effective_url = getattr(document, "final_url", current_url) or current_url


            text_meta = extractor.extract_text_with_meta(
                html=html,
                platform_name=platform_name,
                source_tag=f"page_{page_index}",
            )
            extracted_text = text_meta.get("text", "") or ""
            if extracted_text:
                try:
                    setattr(document, "text", extracted_text)
                except Exception:
                    pass
                combined_text_parts.append(str(extracted_text))


            html_items = extractor.extract_catalog_items_from_html(
                html=html,
                platform_name=platform_name,
                source_url=effective_url,
            )
            jsonld_items = extractor.extract_catalog_items_from_jsonld(
                html=html,
                platform_name=platform_name,
                source_url=effective_url,
            )


            discovered_links = extractor.extract_discovered_catalog_links(
                html=html,
                source_url=effective_url,
            )
            pagination_links = extractor.extract_pagination_links(
                html=html,
                source_url=effective_url,
            )


            for item in html_items + jsonld_items:
                item.setdefault("requested_url", current_url)
                item.setdefault("source_url", effective_url)
                item.setdefault("page_url", effective_url)
                item["crawl_depth"] = depth


            raw_catalog_items.extend(html_items)
            raw_catalog_items.extend(jsonld_items)


            _enqueue_links(
                queue,
                discovered_links,
                depth=depth,
                max_depth=max_depth,
                allowed_domains=crawler.config.allowed_domains,
                seen_enqueued=seen_enqueued,
                is_pagination=False,
            )
            _enqueue_links(
                queue,
                pagination_links,
                depth=depth,
                max_depth=max_depth,
                allowed_domains=crawler.config.allowed_domains,
                seen_enqueued=seen_enqueued,
                is_pagination=True,
            )


            final_key = _url_key(effective_url)
            if final_key and final_key not in seen_fetched:
                seen_fetched.add(final_key)


            document_meta = getattr(document, "meta", {}) or {}
            try:
                setattr(
                    document,
                    "meta",
                    {
                        **document_meta,
                        "crawl_depth": depth,
                        "requested_url": current_url,
                        "effective_url": effective_url,
                    },
                )
            except Exception:
                pass


            page_result = _build_page_result(
                platform_name=platform_name,
                url=current_url,
                depth=depth,
                document=document,
                text_meta=text_meta,
                discovered_links=discovered_links,
                pagination_links=pagination_links,
                html_items_count=len(html_items),
                jsonld_items_count=len(jsonld_items),
            )
            page_result["page_index"] = page_index


            documents.append(document)
            page_results.append(page_result)


        except Exception as e:
            page_results.append(
                {
                    "page_index": page_index,
                    "url": current_url,
                    "effective_url": current_url,
                    "status": "error",
                    "error": str(e),
                    "access_mode": crawler.config.access_mode,
                    "platform_name": platform_name,
                    "crawl_depth": depth,
                }
            )


    combined_text = "\n\n".join(combined_text_parts)
    return documents, raw_catalog_items, page_results, combined_text



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
        "курс",
        "курсы",
        "программа",
        "обучение",
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
            platform_urls = _augment_platform_urls(platform)


            if crawler_config is not None:
                platform_crawler_config = crawler_config
            else:
                base_config = build_crawler_config_for_platform(
                    {**platform, "urls": platform_urls}
                )
                platform_crawler_config = build_crawler_config_with_overrides(
                    base_config=base_config,
                    overrides=crawler_config_overrides,
                )


            crawler = MarketCrawler(platform_crawler_config)


            documents, raw_catalog_items, page_results, combined_text = _crawl_platform_pages(
                platform_name=platform_name,
                seed_urls=platform_urls,
                crawler=crawler,
            )


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
                raw_catalog_items=raw_catalog_items,
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
                "raw_catalog_items_total": len(raw_catalog_items),
                "text_output_path": str(text_file_path),
                "text_length_total": len(combined_text),
            }


            platform_report: PlatformReportDict = {
                "platform_name": platform_name,
                "summary": str(text_analysis.get("summary", "") or ""),
                "fit_for_learning": str(text_analysis.get("fit_for_learning", "") or ""),
                "analytics": analytics,
                "catalog_items": [_serialize_catalog_item(item) for item in catalog_items],
                "source_meta": source_meta,
            }


            platform_reports.append(platform_report)


        report_builder_reports = cast(list[dict[str, Any]], platform_reports)
        report_files = build_market_report_bundle(
            agent_name=self.name,
            platform_reports=report_builder_reports,
        )


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
                "markdown": str(report_files.get("markdown", "")),
                "json": str(report_files.get("json", "")),
                "csv": str(report_files.get("csv", "")),
            },
        }


        return AgentResult(
            agent_name=self.name,
            status="success",
            payload=cast(dict[str, Any], payload),
            message=f"Analyzed {len(platform_reports)} platforms",
        )