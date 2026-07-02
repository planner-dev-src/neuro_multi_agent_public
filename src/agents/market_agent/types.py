from __future__ import annotations

from typing import Any, TypedDict


class PageResultDict(TypedDict, total=False):
    page_index: int
    url: str
    status: str
    ok: bool
    status_code: int | None
    error: str | None
    final_url: str | None
    content_type: str | None
    encoding: str | None
    html_length: int
    text_length: int
    raw_html_path: str | None
    access_mode: str
    fetch_meta: dict[str, Any]
    metadata: dict[str, Any]
    preview: str
    title_hint: str | None
    title: str
    items_found: int
    duration_ms: int | float
    platform_name: str


class SourceMetaDict(TypedDict, total=False):
    csv_path: str
    generated_at: str
    platform_slug: str
    platform_url: str
    category: str
    priority: str
    notes: str
    urls: list[str]
    crawler_access_mode: str
    access_modes_used: list[str]
    pages_total: int
    pages_ok: int
    pages_error: int
    pages_failed: int
    page_results: list[PageResultDict]
    snapshot_hits: int
    proxy_hits: int
    direct_hits: int
    live_fetch_count: int
    failed_urls: list[str]
    documents_total: int
    catalog_items_total: int
    selected_platforms_total: int


class CatalogItemDict(TypedDict, total=False):
    item_id: str
    item_type: str
    title: str
    source_url: str | None
    canonical_url: str | None
    difficulty_level: str | None
    duration_hours: int | float | None
    lessons_count: int | None
    modules_count: int | None
    ai_topics: list[str]
    audience_types: list[str]
    extraction_confidence: int | float | None


class PlatformReportDict(TypedDict, total=False):
    platform_name: str
    platform_slug: str
    platform_url: str
    source_meta: SourceMetaDict
    pages: list[PageResultDict]
    analytics: dict[str, Any]
    summary_markdown: str
    artifacts: dict[str, str]
    catalog_items: list[CatalogItemDict]


class MarketAgentPayloadDict(TypedDict, total=False):
    run_id: str
    generated_at: str
    source_meta: SourceMetaDict
    platform_reports: list[PlatformReportDict]
    files: dict[str, str]
    errors: list[str]