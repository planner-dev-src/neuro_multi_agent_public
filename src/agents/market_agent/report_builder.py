from __future__ import annotations


import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORTS_ROOT = Path("data/reports/market_agent")



def _ensure_reports_root() -> Path:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    return REPORTS_ROOT



def _build_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")



def _escape_md(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace("|", r"\|")
    return text.strip()



def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)



def _pick(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue
        return str(value)
    return ""



def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    if is_dataclass(value):
        try:
            return _json_safe(asdict(value))
        except Exception:
            pass

    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return _json_safe(dumped)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return _json_safe(vars(value))
        except Exception:
            pass

    return str(value)



def _extract_summary_text(report: dict[str, Any]) -> str:
    analytics = report.get("analytics", {}) or {}
    analytics_summary = analytics.get("summary", {}) or {}


    if isinstance(analytics_summary, str) and analytics_summary.strip():
        return analytics_summary.strip()


    if isinstance(analytics_summary, dict) and analytics_summary:
        parts: list[str] = []
        ordered_keys = [
            "programs_total",
            "courses_total",
            "lessons_total",
            "distinct_ai_topics_total",
            "ai_topic_coverage_ratio",
            "advanced_courses_total",
            "largest_topic_name",
            "largest_topic_share",
        ]
        for key in ordered_keys:
            if key in analytics_summary:
                parts.append(f"{key}={analytics_summary.get(key)}")
        if parts:
            return "; ".join(parts)


    return _pick(
        report.get("summary"),
        report.get("analysis_summary"),
        report.get("description"),
    )



def _normalize_catalog_item(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        data = item.model_dump()
        if isinstance(data, dict):
            return data

    if is_dataclass(item):
        try:
            data = asdict(item)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    if isinstance(item, dict):
        return dict(item)

    return {}



def _collect_catalog_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = report.get("catalog_items", []) or []
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        item = _normalize_catalog_item(raw)
        if item:
            items.append(item)
    return items



def _extract_catalog_items_total(report: dict[str, Any]) -> int:
    source_meta = report.get("source_meta", {}) or {}
    analytics = report.get("analytics", {}) or {}
    normalized_entities = analytics.get("normalized_entities", {}) or {}

    explicit_total = source_meta.get("catalog_items_total", None)
    if explicit_total not in (None, ""):
        try:
            return int(explicit_total)
        except Exception:
            pass

    analytics_total = normalized_entities.get("catalog_items_total", None)
    if analytics_total not in (None, ""):
        try:
            return int(analytics_total)
        except Exception:
            pass

    return len(_collect_catalog_items(report))



def _build_platform_summary_row(report: dict[str, Any]) -> dict[str, Any]:
    source_meta = report.get("source_meta", {}) or {}
    analytics = report.get("analytics", {}) or {}
    normalized_entities = analytics.get("normalized_entities", {}) or {}


    page_results = source_meta.get("page_results", []) or []
    first_error = next(
        (page.get("error", "") for page in page_results if page.get("status") == "error"),
        "",
    )


    return {
        "platform_name": _pick(
            report.get("platform_name"),
            report.get("name"),
            source_meta.get("platform_name"),
        ),
        "summary": _extract_summary_text(report),
        "fit_for_learning": _pick(report.get("fit_for_learning")),
        "fit_score": report.get("fit_score", ""),
        "business_model": _pick(report.get("business_model")),
        "delivery_model": _pick(report.get("delivery_model")),
        "target_audience": _stringify(report.get("target_audience", [])),
        "top_categories": _stringify(report.get("top_categories", [])),
        "category_scores": _stringify(report.get("category_scores", {})),
        "highlights": _stringify(report.get("highlights", [])),
        "pricing_signals": _stringify(report.get("pricing_signals", [])),
        "risks": _stringify(report.get("risks", [])),
        "category": _pick(source_meta.get("category"), report.get("category")),
        "priority": _pick(source_meta.get("priority"), report.get("priority")),
        "notes": _pick(source_meta.get("notes"), report.get("notes")),
        "urls": _stringify(source_meta.get("urls", [])),
        "pages_total": source_meta.get("pages_total", 0),
        "pages_ok": source_meta.get("pages_ok", 0),
        "pages_error": source_meta.get("pages_error", 0),
        "documents_total": source_meta.get("documents_total", 0),
        "catalog_items_total": _extract_catalog_items_total(report),
        "courses_total": normalized_entities.get("courses_total", 0),
        "programs_total": normalized_entities.get("programs_total", 0),
        "crawler_access_mode": _pick(source_meta.get("crawler_access_mode")),
        "access_modes_used": _stringify(source_meta.get("access_modes_used", [])),
        "snapshot_hits": source_meta.get("snapshot_hits", 0),
        "proxy_hits": source_meta.get("proxy_hits", 0),
        "direct_hits": source_meta.get("direct_hits", 0),
        "live_fetch_count": source_meta.get("live_fetch_count", 0),
        "failed_urls": _stringify(source_meta.get("failed_urls", [])),
        "first_error": _pick(first_error),
        "raw_report_json": json.dumps(_json_safe(report), ensure_ascii=False),
    }



def _build_catalog_item_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    source_meta = report.get("source_meta", {}) or {}
    platform_name = _pick(
        report.get("platform_name"),
        report.get("name"),
        source_meta.get("platform_name"),
    )
    category = _pick(source_meta.get("category"), report.get("category"))
    priority = _pick(source_meta.get("priority"), report.get("priority"))


    rows: list[dict[str, Any]] = []
    for item in _collect_catalog_items(report):
        rows.append(
            {
                "platform_name": platform_name,
                "category": category,
                "priority": priority,
                "item_id": _pick(item.get("item_id")),
                "source_platform": _pick(item.get("source_platform"), platform_name),
                "source_url": _pick(item.get("source_url")),
                "canonical_url": _pick(item.get("canonical_url")),
                "item_type": _pick(item.get("item_type")),
                "title": _pick(item.get("title")),
                "description": _pick(item.get("description")),
                "provider_name": _pick(item.get("provider_name")),
                "language": _pick(item.get("language")),
                "category_raw": _pick(item.get("category_raw")),
                "tags_raw": _stringify(item.get("tags_raw", [])),
                "difficulty_level": _pick(item.get("difficulty_level")),
                "duration_text": _pick(item.get("duration_text")),
                "duration_hours": item.get("duration_hours", ""),
                "lessons_count": item.get("lessons_count", ""),
                "modules_count": item.get("modules_count", ""),
                "certificate_available": item.get("certificate_available", ""),
                "project_based": item.get("project_based", ""),
                "mentor_support": item.get("mentor_support", ""),
                "job_support": item.get("job_support", ""),
                "ai_topics": _stringify(item.get("ai_topics", [])),
                "audience_types": _stringify(item.get("audience_types", [])),
                "parent_program_id": _pick(item.get("parent_program_id")),
                "child_course_ids": _stringify(item.get("child_course_ids", [])),
                "crawl_depth": item.get("crawl_depth", ""),
                "extraction_confidence": item.get("extraction_confidence", ""),
                "extraction_notes": _stringify(item.get("extraction_notes", [])),
            }
        )
    return rows



def save_json_report(platform_reports: list[dict[str, Any]], agent_name: str) -> Path:
    output_dir = _ensure_reports_root()
    timestamp = _build_timestamp()
    output_path = output_dir / f"{agent_name}_{timestamp}.json"


    payload = {
        "agent_name": agent_name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "platforms_total": len(platform_reports),
        "catalog_items_total": sum(_extract_catalog_items_total(report) for report in platform_reports),
        "platform_reports": _json_safe(platform_reports),
    }


    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path



def save_csv_report(platform_reports: list[dict[str, Any]]) -> Path:
    output_dir = _ensure_reports_root()
    timestamp = _build_timestamp()
    output_path = output_dir / f"market_catalog_items_{timestamp}.csv"


    rows: list[dict[str, Any]] = []
    for report in platform_reports:
        rows.extend(_build_catalog_item_rows(report))


    if not rows:
        for report in platform_reports:
            summary_row = _build_platform_summary_row(report)
            rows.append(
                {
                    "platform_name": summary_row.get("platform_name", ""),
                    "category": summary_row.get("category", ""),
                    "priority": summary_row.get("priority", ""),
                    "item_id": "",
                    "source_platform": summary_row.get("platform_name", ""),
                    "source_url": "",
                    "canonical_url": "",
                    "item_type": "platform_summary",
                    "title": summary_row.get("platform_name", ""),
                    "description": summary_row.get("summary", ""),
                    "provider_name": "",
                    "language": "",
                    "category_raw": "",
                    "tags_raw": "",
                    "difficulty_level": "",
                    "duration_text": "",
                    "duration_hours": "",
                    "lessons_count": "",
                    "modules_count": "",
                    "certificate_available": "",
                    "project_based": "",
                    "mentor_support": "",
                    "job_support": "",
                    "ai_topics": "",
                    "audience_types": "",
                    "parent_program_id": "",
                    "child_course_ids": "",
                    "crawl_depth": "",
                    "extraction_confidence": "",
                    "extraction_notes": "",
                }
            )


    fieldnames = [
        "platform_name",
        "category",
        "priority",
        "item_id",
        "source_platform",
        "source_url",
        "canonical_url",
        "item_type",
        "title",
        "description",
        "provider_name",
        "language",
        "category_raw",
        "tags_raw",
        "difficulty_level",
        "duration_text",
        "duration_hours",
        "lessons_count",
        "modules_count",
        "certificate_available",
        "project_based",
        "mentor_support",
        "job_support",
        "ai_topics",
        "audience_types",
        "parent_program_id",
        "child_course_ids",
        "crawl_depth",
        "extraction_confidence",
        "extraction_notes",
    ]


    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


    return output_path



def save_markdown_report(platform_reports: list[dict[str, Any]], agent_name: str) -> Path:
    output_dir = _ensure_reports_root()
    timestamp = _build_timestamp()
    output_path = output_dir / f"{agent_name}_{timestamp}.md"


    lines: list[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()


    lines.append(f"# {agent_name}")
    lines.append("")
    lines.append(f"- Generated at (UTC): {generated_at}")
    lines.append(f"- Platforms total: {len(platform_reports)}")
    lines.append(
        f"- Catalog items total: {sum(_extract_catalog_items_total(report) for report in platform_reports)}"
    )
    lines.append("")


    for idx, report in enumerate(platform_reports, start=1):
        source_meta = report.get("source_meta", {}) or {}
        analytics = report.get("analytics", {}) or {}
        normalized_entities = analytics.get("normalized_entities", {}) or {}
        breadth = analytics.get("breadth", {}) or {}
        depth = analytics.get("depth", {}) or {}
        coverage = analytics.get("coverage", {}) or {}
        concentration = analytics.get("concentration", {}) or {}
        page_results = source_meta.get("page_results", []) or []


        platform_name = _pick(
            report.get("platform_name"),
            report.get("name"),
            source_meta.get("platform_name"),
            f"platform_{idx}",
        )
        summary = _extract_summary_text(report)


        lines.append(f"## {platform_name}")
        lines.append("")
        lines.append(f"- Category: {_escape_md(source_meta.get('category', report.get('category', '')))}")
        lines.append(f"- Priority: {_escape_md(source_meta.get('priority', report.get('priority', '')))}")
        lines.append(f"- Fit for learning: {_escape_md(report.get('fit_for_learning', ''))}")
        lines.append(f"- Fit score: {_escape_md(report.get('fit_score', ''))}")
        lines.append(f"- Business model: {_escape_md(report.get('business_model', ''))}")
        lines.append(f"- Delivery model: {_escape_md(report.get('delivery_model', ''))}")
        lines.append(f"- Access mode: {_escape_md(source_meta.get('crawler_access_mode', ''))}")
        lines.append(f"- Access modes used: {_escape_md(_stringify(source_meta.get('access_modes_used', [])))}")
        lines.append(f"- Pages total: {source_meta.get('pages_total', 0)}")
        lines.append(f"- Pages ok: {source_meta.get('pages_ok', 0)}")
        lines.append(f"- Pages error: {source_meta.get('pages_error', 0)}")
        lines.append(f"- Documents total: {source_meta.get('documents_total', 0)}")
        lines.append(f"- Catalog items total: {_extract_catalog_items_total(report)}")
        lines.append(f"- Courses total: {normalized_entities.get('courses_total', 0)}")
        lines.append(f"- Programs total: {normalized_entities.get('programs_total', 0)}")
        lines.append(f"- Snapshot hits: {source_meta.get('snapshot_hits', 0)}")
        lines.append(f"- Proxy hits: {source_meta.get('proxy_hits', 0)}")
        lines.append(f"- Direct hits: {source_meta.get('direct_hits', 0)}")
        lines.append(f"- Live fetch count: {source_meta.get('live_fetch_count', 0)}")
        lines.append("")


        notes = _pick(source_meta.get("notes"), report.get("notes"))
        if notes:
            lines.append("### Notes")
            lines.append("")
            lines.append(notes)
            lines.append("")


        urls = source_meta.get("urls", []) or []
        if urls:
            lines.append("### URLs")
            lines.append("")
            for url in urls:
                lines.append(f"- {url}")
            lines.append("")


        if summary:
            lines.append("### Summary")
            lines.append("")
            lines.append(summary)
            lines.append("")


        target_audience = report.get("target_audience", []) or []
        if target_audience:
            lines.append("### Target audience")
            lines.append("")
            for item in target_audience:
                lines.append(f"- {_escape_md(item)}")
            lines.append("")


        top_categories = report.get("top_categories", []) or []
        if top_categories:
            lines.append("### Top categories")
            lines.append("")
            for item in top_categories:
                lines.append(f"- {_escape_md(item)}")
            lines.append("")


        category_scores = report.get("category_scores", {}) or {}
        if category_scores:
            lines.append("### Category scores")
            lines.append("")
            lines.append("| Category | Score |")
            lines.append("|---|---:|")
            for key, value in category_scores.items():
                lines.append(f"| {_escape_md(key)} | {_escape_md(value)} |")
            lines.append("")


        highlights = report.get("highlights", []) or []
        if highlights:
            lines.append("### Highlights")
            lines.append("")
            for item in highlights:
                lines.append(f"- {_escape_md(item)}")
            lines.append("")


        pricing_signals = report.get("pricing_signals", []) or []
        if pricing_signals:
            lines.append("### Pricing signals")
            lines.append("")
            for item in pricing_signals:
                lines.append(f"- {_escape_md(item)}")
            lines.append("")


        risks = report.get("risks", []) or []
        if risks:
            lines.append("### Risks")
            lines.append("")
            for item in risks:
                lines.append(f"- {_escape_md(item)}")
            lines.append("")


        if analytics:
            lines.append("### Analytics")
            lines.append("")
            lines.append(f"- Breadth: {_escape_md(_stringify(breadth))}")
            lines.append(f"- Depth: {_escape_md(_stringify(depth))}")
            lines.append(f"- Coverage: {_escape_md(_stringify(coverage))}")
            lines.append(f"- Concentration: {_escape_md(_stringify(concentration))}")
            lines.append("")


        catalog_items = _collect_catalog_items(report)
        if catalog_items:
            lines.append("### Catalog items")
            lines.append("")
            lines.append("| Title | Type | Difficulty | Duration hours | URL |")
            lines.append("|---|---|---|---:|---|")
            for item in catalog_items:
                lines.append(
                    "| "
                    f"{_escape_md(item.get('title', ''))} | "
                    f"{_escape_md(item.get('item_type', ''))} | "
                    f"{_escape_md(item.get('difficulty_level', ''))} | "
                    f"{_escape_md(item.get('duration_hours', ''))} | "
                    f"{_escape_md(item.get('canonical_url', ''))} |"
                )
            lines.append("")


        if page_results:
            lines.append("### Page results")
            lines.append("")
            lines.append("| URL | Status | Code | Access | HTML length | Text length | Preview | Error |")
            lines.append("|---|---|---:|---|---:|---:|---|---|")


            for page in page_results:
                preview = _escape_md(page.get("preview", ""))
                error = _escape_md(page.get("error", ""))
                lines.append(
                    "| "
                    f"{_escape_md(page.get('url', ''))} | "
                    f"{_escape_md(page.get('status', ''))} | "
                    f"{_escape_md(page.get('status_code', ''))} | "
                    f"{_escape_md(page.get('access_mode', ''))} | "
                    f"{_escape_md(page.get('html_length', 0))} | "
                    f"{_escape_md(page.get('text_length', 0))} | "
                    f"{preview} | "
                    f"{error} |"
                )
            lines.append("")


        failed_urls = source_meta.get("failed_urls", []) or []
        if failed_urls:
            lines.append("### Failed URLs")
            lines.append("")
            for url in failed_urls:
                lines.append(f"- {url}")
            lines.append("")


        extra_keys = [
            key
            for key in report.keys()
            if key
            not in {
                "source_meta",
                "platform_name",
                "name",
                "summary",
                "analysis_summary",
                "description",
                "analytics",
                "catalog_items",
                "fit_for_learning",
                "fit_score",
                "business_model",
                "delivery_model",
                "target_audience",
                "top_categories",
                "category_scores",
                "highlights",
                "pricing_signals",
                "risks",
                "category",
                "priority",
                "notes",
            }
        ]
        if extra_keys:
            lines.append("### Extra fields")
            lines.append("")
            for key in extra_keys:
                lines.append(f"- {key}: {_escape_md(_stringify(_json_safe(report.get(key))))}")
            lines.append("")


    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path



def build_market_report_bundle(*, agent_name: str, platform_reports: list[dict[str, Any]]) -> dict[str, str]:
    markdown_path = save_markdown_report(platform_reports, agent_name)
    json_path = save_json_report(platform_reports, agent_name)
    csv_path = save_csv_report(platform_reports)


    return {
        "markdown": str(markdown_path),
        "json": str(json_path),
        "csv": str(csv_path),
    }