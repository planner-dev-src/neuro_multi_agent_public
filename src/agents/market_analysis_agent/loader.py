from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import CatalogItem, PlatformReportInput


DEFAULT_REPORTS_ROOT = Path("data/reports/market_agent")


def _latest_market_agent_json(root: Path = DEFAULT_REPORTS_ROOT) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"Market agent reports root does not exist: {root}")

    candidates = [path for path in root.glob("market_agent_*.json") if path.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No market_agent JSON reports found in {root}")

    return max(candidates, key=lambda path: path.stat().st_mtime)


def _as_dict(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Expected {context} to be an object, got {type(value).__name__}")
    return value


def _as_list(value: Any, *, context: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Expected {context} to be a list, got {type(value).__name__}")
    return value


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if x is not None and str(x).strip()]
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    return []


def _coerce_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def _normalize_metadata(raw_item: dict[str, Any]) -> dict[str, Any]:
    metadata = raw_item.get("metadata")
    if metadata is None:
        metadata = {}
    if isinstance(metadata, dict):
        return metadata
    return {"raw_metadata": metadata}


def _build_catalog_item(raw_item: dict[str, Any], *, platform_name: str) -> CatalogItem:
    metadata = _normalize_metadata(raw_item)

    tags_raw = _as_str_list(raw_item.get("tags_raw"))
    ai_topics = _as_str_list(raw_item.get("ai_topics"))
    audience_types = _as_str_list(raw_item.get("audience_types"))
    extraction_notes = _as_str_list(raw_item.get("extraction_notes"))

    # Сохраняем поля market_agent, которых нет в явных атрибутах CatalogItem,
    # в metadata для downstream-использования
    extra_fields = {
        "language": raw_item.get("language"),
        "lessons_count": raw_item.get("lessons_count"),
        "modules_count": raw_item.get("modules_count"),
        "parent_program_id": raw_item.get("parent_program_id"),
        "child_course_ids": raw_item.get("child_course_ids"),
        "crawl_depth": raw_item.get("crawl_depth"),
        "platform_name": raw_item.get("platform_name") or raw_item.get("source_platform"),
    }
    # Убираем None-значения, чтобы не засорять metadata
    extra_fields = {k: v for k, v in extra_fields.items() if v is not None}

    # Сливаем с существующими metadata, приоритет у явных metadata
    for k, v in extra_fields.items():
        if k not in metadata:
            metadata[k] = v

    return CatalogItem(
        platform_name=platform_name,
        item_id=str(raw_item.get("item_id") or "").strip(),
        title=str(raw_item.get("title") or raw_item.get("item_title") or "").strip(),
        description=str(raw_item.get("description") or "").strip(),
        canonical_url=str(raw_item.get("canonical_url") or "").strip(),
        source_url=str(raw_item.get("source_url") or "").strip(),
        category_hint=str(raw_item.get("category_hint") or "").strip(),
        category_raw=str(raw_item.get("category_raw") or "").strip(),
        item_type=str(raw_item.get("item_type") or "").strip(),
        provider_name=str(raw_item.get("provider_name") or "").strip(),
        tags_raw=tags_raw,
        ai_topics=ai_topics,
        audience_types=audience_types,
        duration_text=str(raw_item.get("duration_text") or "").strip(),
        duration_hours=_coerce_optional_float(raw_item.get("duration_hours")),
        difficulty_level=str(raw_item.get("difficulty_level") or "").strip(),
        certificate_available=_coerce_optional_bool(raw_item.get("certificate_available")),
        project_based=_coerce_optional_bool(raw_item.get("project_based")),
        mentor_support=_coerce_optional_bool(raw_item.get("mentor_support")),
        job_support=_coerce_optional_bool(raw_item.get("job_support")),
        language=str(raw_item.get("language") or "").strip(),
        extraction_confidence=_coerce_optional_float(raw_item.get("extraction_confidence")),
        extraction_notes=extraction_notes,
        metadata=metadata,
    )


def _extract_raw_items_payload(raw_report: dict[str, Any], *, platform_name: str) -> list[Any]:
    if "items" in raw_report and raw_report.get("items") is not None:
        return _as_list(
            raw_report.get("items"),
            context=f"items for platform '{platform_name}'",
        )

    return _as_list(
        raw_report.get("catalog_items", []),
        context=f"catalog_items for platform '{platform_name}'",
    )


def _extract_catalog_items(raw_report: dict[str, Any], *, platform_name: str) -> list[CatalogItem]:
    raw_items = _extract_raw_items_payload(raw_report, platform_name=platform_name)

    items: list[CatalogItem] = []
    for item_idx, raw_item in enumerate(raw_items):
        item_dict = _as_dict(
            raw_item,
            context=f"items[{item_idx}] for platform '{platform_name}'",
        )
        items.append(_build_catalog_item(item_dict, platform_name=platform_name))
    return items


def _extract_report_metadata(raw_report: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    source_meta = raw_report.get("source_meta")
    if isinstance(source_meta, dict):
        metadata["source_meta"] = source_meta

    pages = raw_report.get("pages")
    if isinstance(pages, list):
        metadata["pages"] = pages

    analytics = raw_report.get("analytics")
    if isinstance(analytics, dict):
        metadata["analytics"] = analytics

    summary_markdown = raw_report.get("summary_markdown")
    if summary_markdown is not None:
        metadata["summary_markdown"] = summary_markdown

    summary = raw_report.get("summary")
    if summary is not None:
        metadata["summary"] = summary

    fit_for_learning = raw_report.get("fit_for_learning")
    if fit_for_learning is not None:
        metadata["fit_for_learning"] = fit_for_learning

    artifacts = raw_report.get("artifacts")
    if isinstance(artifacts, dict):
        metadata["artifacts"] = artifacts

    if "platform_slug" in raw_report:
        metadata["platform_slug"] = raw_report.get("platform_slug")

    if "catalog_items" in raw_report:
        metadata["legacy_catalog_items_present"] = True

    if "items" in raw_report:
        metadata["canonical_items_present"] = True

    source_url = raw_report.get("source_url")
    if source_url:
        metadata["source_url"] = source_url

    platform_url = raw_report.get("platform_url")
    if platform_url:
        metadata["platform_url"] = platform_url

    return metadata


def _build_platform_report(raw_report: dict[str, Any], idx: int) -> PlatformReportInput:
    platform_name = str(raw_report.get("platform_name") or "").strip()
    if not platform_name:
        raise ValueError(f"platform_reports[{idx}] is missing required field 'platform_name'")

    platform_url = str(raw_report.get("platform_url") or raw_report.get("source_url") or "").strip()

    items = _extract_catalog_items(raw_report, platform_name=platform_name)
    metadata = _extract_report_metadata(raw_report)

    return PlatformReportInput(
        platform_name=platform_name,
        items=items,
        source_url=platform_url,
        metadata=metadata,
    )


def load_market_agent_reports(
    *,
    source_json_path: str | None = None,
) -> list[PlatformReportInput]:
    path = Path(source_json_path).expanduser() if source_json_path else _latest_market_agent_json()

    if not path.exists():
        raise FileNotFoundError(f"Market agent report file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected top-level JSON object in {path}, got {type(payload).__name__}"
        )

    raw_reports = _as_list(payload.get("platform_reports", []), context=f"'platform_reports' in {path}")

    validated_reports: list[PlatformReportInput] = []
    for idx, raw_report in enumerate(raw_reports):
        report_dict = _as_dict(raw_report, context=f"platform_reports[{idx}]")
        try:
            validated_reports.append(_build_platform_report(report_dict, idx))
        except Exception as exc:
            raise ValueError(
                f"Failed to build platform_reports[{idx}] from {path}: {exc}"
            ) from exc

    return validated_reports