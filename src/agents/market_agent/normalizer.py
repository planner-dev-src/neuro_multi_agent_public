# normalizer.py
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any, Literal
from urllib.parse import urlparse

from src.agents.market_agent.crawler import CrawlDocument
from src.agents.market_agent.models import CatalogItem, CatalogItemType

WHITESPACE_RE = re.compile(r"\s+")
DURATION_HOURS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:hours?|hrs?|h)\b", re.IGNORECASE)
DURATION_MINUTES_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:minutes?|mins?|min)\b", re.IGNORECASE)
LESSONS_RE = re.compile(r"(\d+)\s*(?:lessons?|lectures?)\b", re.IGNORECASE)
MODULES_RE = re.compile(r"(\d+)\s*(?:modules?|units?|sections?)\b", re.IGNORECASE)

BEGINNER_MARKERS = ("beginner", "introductory", "introduction", "fundamentals", "basic")
INTERMEDIATE_MARKERS = ("intermediate",)
ADVANCED_MARKERS = ("advanced", "expert", "professional", "specialist")
MIXED_MARKERS = ("all levels", "mixed", "beginner to advanced")

PROGRAM_MARKERS = ("specialization", "certificate", "bootcamp", "learning path", "program")
COURSE_MARKERS = ("course", "module", "training", "learn")
LESSON_MARKERS = ("lesson", "lecture")
CATALOG_PAGE_MARKERS = ("catalog", "all courses", "browse", "course list", "program list")

AUDIENCE_MARKERS: dict[str, tuple[str, ...]] = {
    "beginners": ("beginner", "new to", "no experience", "start here"),
    "developers": ("developer", "engineer", "programmer"),
    "data_scientists": ("data scientist", "ml engineer", "machine learning engineer"),
    "managers": ("manager", "management", "leader", "executive"),
    "students": ("student", "learner"),
    "business": ("business", "sales", "marketing", "product"),
}

AI_TOPIC_TAXONOMY: dict[str, tuple[str, ...]] = {
    "llm_agents": ("llm", "agent", "agents", "gpt", "rag", "prompt", "assistant"),
    "nlp": ("nlp", "natural language", "language model", "text"),
    "cv": ("computer vision", "vision", "image", "cnn"),
    "speech_audio": ("speech", "audio", "asr", "tts"),
    "classical_ml": ("machine learning", "ml", "regression", "classification"),
    "rl": ("reinforcement learning", "rl"),
    "timeseries": ("time series", "forecasting"),
    "gan": ("gan", "generative adversarial"),
    "automl": ("automl",),
    "production_integration": ("production", "deployment", "mlops", "integration"),
    "ai_pm_sales": ("product", "management", "sales", "business"),
    "genetic_algorithms": ("genetic algorithm", "evolutionary"),
}

DifficultyLevel = Literal["beginner", "intermediate", "advanced", "mixed", "unknown"]


def normalize_text(value: str | None) -> str:
    return WHITESPACE_RE.sub(" ", (value or "").strip())


def normalize_lower(value: str | None) -> str:
    return normalize_text(value).lower()


def coerce_difficulty_level(value: str | None) -> DifficultyLevel:
    normalized = (value or "").strip().lower()
    if normalized == "beginner":
        return "beginner"
    if normalized == "intermediate":
        return "intermediate"
    if normalized == "advanced":
        return "advanced"
    if normalized == "mixed":
        return "mixed"
    return "unknown"


def _coerce_document(doc: CrawlDocument | dict[str, Any]) -> dict[str, Any]:
    if isinstance(doc, CrawlDocument):
        return {
            "source_url": doc.source_url,
            "final_url": doc.final_url,
            "status_code": doc.status_code,
            "title_hint": getattr(doc, "title_hint", None),
            "html": doc.html,
            "text": getattr(doc, "text", ""),
            "access_mode": doc.access_mode,
            "content_type": doc.content_type,
            "encoding": doc.encoding,
            "fetched_at_ts": doc.fetched_at_ts,
            "meta": doc.meta,
        }
    return dict(doc)


def _extract_title(doc: dict[str, Any]) -> str:
    for key in ("title_hint", "title"):
        value = doc.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)

    html = doc.get("html")
    if isinstance(html, str) and html:
        lower = html.lower()
        start = lower.find("<title>")
        end = lower.find("</title>")
        if start != -1 and end != -1 and end > start:
            return normalize_text(html[start + 7 : end])

    text = doc.get("text")
    if isinstance(text, str) and text.strip():
        first_line = text.strip().splitlines()[0]
        return normalize_text(first_line[:160])

    return ""


def _extract_description(doc: dict[str, Any]) -> str:
    text = doc.get("text")
    if isinstance(text, str) and text.strip():
        cleaned = normalize_text(text)
        return cleaned[:4000]

    html = doc.get("html")
    if isinstance(html, str) and html.strip():
        return normalize_text(html)[:4000]

    return ""


def _extract_provider_name(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _classify_item_type(title: str, description: str) -> CatalogItemType:
    full_text = normalize_lower(f"{title} {description}")

    if any(marker in full_text for marker in PROGRAM_MARKERS):
        return "program"
    if any(marker in full_text for marker in COURSE_MARKERS):
        return "course"
    if any(marker in full_text for marker in LESSON_MARKERS):
        return "lesson"
    if any(marker in full_text for marker in CATALOG_PAGE_MARKERS):
        return "catalog_page"
    return "unknown"


def _extract_difficulty_level(title: str, description: str) -> DifficultyLevel:
    full_text = normalize_lower(f"{title} {description}")

    if any(marker in full_text for marker in MIXED_MARKERS):
        return "mixed"
    if any(marker in full_text for marker in ADVANCED_MARKERS):
        return "advanced"
    if any(marker in full_text for marker in INTERMEDIATE_MARKERS):
        return "intermediate"
    if any(marker in full_text for marker in BEGINNER_MARKERS):
        return "beginner"
    return "unknown"


def _extract_duration_text(title: str, description: str) -> str:
    full_text = normalize_text(f"{title} {description}")
    hour_match = DURATION_HOURS_RE.search(full_text)
    if hour_match:
        return hour_match.group(0)
    minute_match = DURATION_MINUTES_RE.search(full_text)
    if minute_match:
        return minute_match.group(0)
    return ""


def _extract_duration_hours(title: str, description: str) -> float | None:
    full_text = normalize_text(f"{title} {description}")

    hour_match = DURATION_HOURS_RE.search(full_text)
    if hour_match:
        value = hour_match.group(1).replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    minute_match = DURATION_MINUTES_RE.search(full_text)
    if minute_match:
        value = minute_match.group(1).replace(",", ".")
        try:
            return float(value) / 60.0
        except ValueError:
            return None

    return None


def _extract_int(pattern: re.Pattern[str], title: str, description: str) -> int | None:
    full_text = normalize_text(f"{title} {description}")
    match = pattern.search(full_text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_ai_topics(title: str, description: str) -> list[str]:
    full_text = normalize_lower(f"{title} {description}")
    matched: list[str] = []

    for topic_name, keywords in AI_TOPIC_TAXONOMY.items():
        if any(normalize_lower(keyword) in full_text for keyword in keywords):
            matched.append(topic_name)

    return matched


def _extract_audience_types(title: str, description: str) -> list[str]:
    full_text = normalize_lower(f"{title} {description}")
    audience: list[str] = []

    for audience_name, markers in AUDIENCE_MARKERS.items():
        if any(normalize_lower(marker) in full_text for marker in markers):
            audience.append(audience_name)

    return audience


def _extract_tags_raw(title: str, description: str) -> list[str]:
    tags: list[str] = []
    tags.extend(_extract_ai_topics(title, description))
    tags.extend(_extract_audience_types(title, description))
    return sorted(set(tags))


def _extract_bool_feature(title: str, description: str, markers: tuple[str, ...]) -> bool | None:
    full_text = normalize_lower(f"{title} {description}")
    if any(marker in full_text for marker in markers):
        return True
    return None


def _build_item_id(source_platform: str, canonical_url: str, title: str) -> str:
    seed = f"{source_platform}|{canonical_url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(seed).hexdigest()[:16]


def _extract_crawl_depth(doc: dict[str, Any]) -> int:
    meta = doc.get("meta")
    if isinstance(meta, dict):
        value = meta.get("crawl_depth")
        if isinstance(value, int):
            return value
    return 0


def _extract_extraction_notes(doc: dict[str, Any]) -> list[str]:
    notes: list[str] = []

    status_code = doc.get("status_code")
    if isinstance(status_code, int) and status_code >= 400:
        notes.append(f"http_status:{status_code}")

    access_mode = doc.get("access_mode")
    if isinstance(access_mode, str) and access_mode:
        notes.append(f"access_mode:{access_mode}")

    content_type = doc.get("content_type")
    if isinstance(content_type, str) and content_type:
        notes.append(f"content_type:{content_type}")

    return notes


def _estimate_extraction_confidence(title: str, description: str, item_type: str) -> float:
    score = 0.2
    if title:
        score += 0.3
    if description:
        score += 0.2
    if item_type != "unknown":
        score += 0.2
    if len(description) >= 200:
        score += 0.1
    return min(score, 1.0)


def _document_to_catalog_item(platform_name: str, doc: CrawlDocument | dict[str, Any]) -> CatalogItem:
    d = _coerce_document(doc)
    source_url = str(d.get("source_url", ""))
    canonical_url = str(d.get("final_url", source_url))
    title = _extract_title(d)
    description = _extract_description(d)

    item_type = _classify_item_type(title, description)
    difficulty_level = coerce_difficulty_level(_extract_difficulty_level(title, description))
    duration_text = _extract_duration_text(title, description)
    duration_hours = _extract_duration_hours(title, description)
    lessons_count = _extract_int(LESSONS_RE, title, description)
    modules_count = _extract_int(MODULES_RE, title, description)
    ai_topics = _extract_ai_topics(title, description)
    audience_types = _extract_audience_types(title, description)
    tags_raw = _extract_tags_raw(title, description)

    certificate_available = _extract_bool_feature(
        title, description, ("certificate", "certification", "certified")
    )
    project_based = _extract_bool_feature(
        title, description, ("project", "hands-on", "portfolio")
    )
    mentor_support = _extract_bool_feature(
        title, description, ("mentor", "mentorship", "instructor support", "coach")
    )
    job_support = _extract_bool_feature(
        title, description, ("career support", "job support", "placement", "hire")
    )

    item_id = _build_item_id(platform_name, canonical_url, title)
    extraction_notes = _extract_extraction_notes(d)

    return CatalogItem(
        item_id=item_id,
        source_platform=platform_name,
        source_url=source_url,
        canonical_url=canonical_url,
        item_type=item_type,
        title=title,
        description=description,
        provider_name=_extract_provider_name(canonical_url or source_url),
        language="",
        category_raw="",
        tags_raw=tags_raw,
        difficulty_level=difficulty_level,
        duration_text=duration_text,
        duration_hours=duration_hours,
        lessons_count=lessons_count,
        modules_count=modules_count,
        certificate_available=certificate_available,
        project_based=project_based,
        mentor_support=mentor_support,
        job_support=job_support,
        ai_topics=ai_topics,
        audience_types=audience_types,
        parent_program_id=None,
        child_course_ids=[],
        crawl_depth=_extract_crawl_depth(d),
        extraction_confidence=_estimate_extraction_confidence(title, description, item_type),
        extraction_notes=extraction_notes,
    )


def normalize_documents_to_catalog_items(
    platform_name: str,
    documents: Iterable[CrawlDocument | dict[str, Any]],
) -> list[CatalogItem]:
    return [_document_to_catalog_item(platform_name, doc) for doc in documents]


def normalize_document_to_catalog_items(
    platform_name: str,
    document: CrawlDocument | dict[str, Any],
) -> list[CatalogItem]:
    return normalize_documents_to_catalog_items(platform_name, [document])