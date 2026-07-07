from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field, is_dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse


WHITESPACE_RE = re.compile(r"\s+")
HOURS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ч|час(?:а|ов)?|hours?|hrs?|h)\b", re.IGNORECASE)
MONTHS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:мес(?:яц(?:а|ев)?)?\.?)\b", re.IGNORECASE)
WEEKS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:нед(?:ел[яьиь])?)\b", re.IGNORECASE)
LESSONS_RE = re.compile(r"(\d+)\s*(?:урок(?:а|ов)?|lessons?)\b", re.IGNORECASE)
MODULES_RE = re.compile(r"(\d+)\s*(?:модул(?:ь|я|ей)|modules?)\b", re.IGNORECASE)

AI_MARKERS = (
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "llm",
    "nlp",
    "computer vision",
    "искусственный интеллект",
    "машинное обучение",
    "нейросет",
    "генератив",
)

BEGINNER_MARKERS = (
    "с нуля",
    "beginner",
    "начинающ",
    "junior",
    "basic",
    "для новичков",
)

ADVANCED_MARKERS = (
    "advanced",
    "pro",
    "middle",
    "senior",
    "продвинут",
)

CERTIFICATE_MARKERS = (
    "certificate",
    "certification",
    "сертификат",
    "диплом",
)

MENTOR_MARKERS = (
    "mentor",
    "ментор",
    "наставник",
    "куратор",
)

JOB_MARKERS = (
    "job",
    "career",
    "трудоустрой",
    "карьер",
    "стажиров",
)

PROJECT_MARKERS = (
    "project",
    "pet-project",
    "проект",
    "портфолио",
)

# Тайтлы, которые точно не являются курсами
NOISE_TITLE_PATTERNS = (
    re.compile(r"^(регистрация|войти|вход|личный кабинет)", re.IGNORECASE),
    re.compile(r"^(скидка|акция|бесплатно|попробовать)", re.IGNORECASE),
    re.compile(r"^(главная|каталог|навигация|поиск)", re.IGNORECASE),
    re.compile(r"^(политика|условия|конфиденциальность|соглашение)", re.IGNORECASE),
    re.compile(r"^(отзывы|вопросы|помощь|поддержка|контакты)", re.IGNORECASE),
    re.compile(r"^(с нуля|\d+ месяцев|\d+ года|pro)", re.IGNORECASE),
)


def _looks_like_noise_title(title: str) -> bool:
    return any(pattern.search(title) for pattern in NOISE_TITLE_PATTERNS)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return WHITESPACE_RE.sub(" ", text)


def _normalize_list(values: Any) -> list[str]:
    if values is None:
        return []

    if isinstance(values, (list, tuple, set)):
        result = [_normalize_text(item) for item in values]
        return [item for item in result if item]

    text = _normalize_text(values)
    if not text:
        return []

    parts = re.split(r"[|,/;\n]+", text)
    result = [_normalize_text(part) for part in parts]
    return [item for item in result if item]


def _normalize_url(value: Any) -> str:
    return _normalize_text(value)


def _host_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _slugify(value: str) -> str:
    value = _normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "item"


def _stable_item_id(platform_name: str, canonical_url: str, title: str) -> str:
    base = "|".join(
        [
            _normalize_text(platform_name).lower(),
            _normalize_text(canonical_url).lower(),
            _normalize_text(title).lower(),
        ]
    )
    digest = hashlib.md5(base.encode("utf-8")).hexdigest()[:12]
    platform_slug = _slugify(platform_name)
    title_slug = _slugify(title)[:48]
    return f"{platform_slug}__{title_slug}__{digest}"


def _coerce_float(value: Any) -> float | None:
    text = _normalize_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _extract_duration_hours(text: str) -> float | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    match = HOURS_RE.search(normalized)
    if match:
        value = _coerce_float(match.group(1))
        return value

    match = WEEKS_RE.search(normalized)
    if match:
        value = _coerce_float(match.group(1))
        if value is not None:
            return round(value * 7 * 2, 2)

    match = MONTHS_RE.search(normalized)
    if match:
        value = _coerce_float(match.group(1))
        if value is not None:
            return round(value * 4 * 7 * 2, 2)

    return None


def _extract_int_by_pattern(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(_normalize_text(text))
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = _normalize_text(text).lower()
    return any(marker in lowered for marker in markers)


def _infer_item_type(url: str, title: str, description: str, tags: list[str]) -> str:
    haystack = " | ".join([url, title, description, *tags]).lower()

    if any(token in haystack for token in ("profession", "професс", "program", "программа")):
        return "program"
    if any(token in haystack for token in ("course", "курс", "bootcamp", "интенсив")):
        return "course"
    return "catalog_item"


def _infer_language(text: str, platform_name: str) -> str:
    haystack = f"{platform_name} {text}".lower()
    if re.search(r"[а-яё]", haystack):
        return "ru"
    return "en"


def _infer_difficulty(text: str) -> str:
    lowered = _normalize_text(text).lower()
    if _contains_any(lowered, BEGINNER_MARKERS):
        return "beginner"
    if _contains_any(lowered, ADVANCED_MARKERS):
        return "advanced"
    return ""


def _infer_ai_topics(text: str, tags: list[str]) -> list[str]:
    haystack = " | ".join([text, *tags]).lower()
    result: list[str] = []

    if "machine learning" in haystack or "машинное обучение" in haystack:
        result.append("machine_learning")
    if "deep learning" in haystack or "глубок" in haystack:
        result.append("deep_learning")
    if "nlp" in haystack or "natural language" in haystack:
        result.append("nlp")
    if "computer vision" in haystack or "computer-vision" in haystack:
        result.append("computer_vision")
    if any(marker in haystack for marker in AI_MARKERS):
        if "artificial_intelligence" not in result:
            result.append("artificial_intelligence")

    return result


def _infer_audience_types(text: str) -> list[str]:
    lowered = _normalize_text(text).lower()
    result: list[str] = []

    if any(token in lowered for token in ("начина", "с нуля", "нович")):
        result.append("beginners")
    if any(token in lowered for token in ("junior", "middle", "senior", "опыт")):
        result.append("professionals")
    if any(token in lowered for token in ("школьник", "student", "студент")):
        result.append("students")
    if any(token in lowered for token in ("manager", "менедж", "руковод")):
        result.append("managers")

    return result


def _pick_provider_name(platform_name: str, raw: dict[str, Any]) -> str:
    for key in ("provider_name", "provider", "organization", "school_name"):
        value = _normalize_text(raw.get(key))
        if value:
            return value
    return _normalize_text(platform_name)


def _pick_source_url(raw: dict[str, Any], fallback_url: str = "") -> str:
    for key in ("source_url", "page_url", "requested_url"):
        value = _normalize_url(raw.get(key))
        if value:
            return value
    return _normalize_url(fallback_url)


def _pick_canonical_url(raw: dict[str, Any], fallback_url: str = "") -> str:
    for key in ("canonical_url", "url", "page_url", "source_url", "requested_url"):
        value = _normalize_url(raw.get(key))
        if value:
            return value
    return _normalize_url(fallback_url)


def _raw_to_text_blob(raw: dict[str, Any]) -> str:
    parts: list[str] = []

    for key in (
        "title",
        "description",
        "raw_text",
        "duration_text",
        "provider_name",
        "item_type",
        "selector_used",
    ):
        value = _normalize_text(raw.get(key))
        if value:
            parts.append(value)

    for tag in _normalize_list(raw.get("tags")):
        parts.append(tag)

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Усиленная дедупликация
# ---------------------------------------------------------------------------

def _title_similarity(a: str, b: str) -> float:
    """Коэффициент схожести двух заголовков (0.0 – 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _canonical_url_key(url: str) -> str:
    """Нормализует URL для сравнения: убирает query-параметры, fragment, www, trailing slash."""
    if not url:
        return ""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def _dedupe_raw_catalog_items(
    raw_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Дедупликация сырых элементов каталога перед нормализацией.

    Правила (по приоритету):
    1. Точное совпадение canonical_url — удаляем дубликат
    2. Точное совпадение title в рамках одной платформы — удаляем дубликат
    3. Нечёткое совпадение title (схожесть > 90%) + совпадение платформы — удаляем дубликат
    """
    if len(raw_items) <= 1:
        return raw_items

    # Группируем по платформам для более точной дедупликации
    by_platform: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in raw_items:
        platform = str(item.get("platform_name", "") or "").strip().lower()
        by_platform.setdefault(platform, []).append(item)

    deduped: list[dict[str, Any]] = []
    total_removed = 0

    for platform, items in by_platform.items():
        kept: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        seen_fuzzy: list[str] = []  # список нормализованных тайтлов для нечёткого сравнения

        for item in items:
            # Правило 1: точное совпадение URL
            url_key = _canonical_url_key(
                _pick_canonical_url(item, item.get("url", ""))
            )
            if url_key and url_key in seen_urls:
                total_removed += 1
                continue

            # Правило 2: точное совпадение title
            title = _normalize_text(item.get("title", "")).lower().strip()
            if title and title in seen_titles:
                total_removed += 1
                continue

            # Правило 3: нечёткое совпадение title (схожесть > 90%)
            is_duplicate = False
            if title and len(title) > 10:
                for existing_title in seen_fuzzy:
                    if _title_similarity(title, existing_title) > 0.9:
                        is_duplicate = True
                        break

            if is_duplicate:
                total_removed += 1
                continue

            if url_key:
                seen_urls.add(url_key)
            if title:
                seen_titles.add(title)
                if len(title) > 10:
                    seen_fuzzy.append(title)
            kept.append(item)

        deduped.extend(kept)

    if total_removed > 0:
        print(
            f"  [dedup] Удалено дубликатов: {total_removed} "
            f"(было {len(raw_items)}, осталось {len(deduped)})"
        )

    return deduped


def _dedupe_catalog_items(items: list[CatalogItem]) -> list[CatalogItem]:
    """Финальная дедупликация нормализованных элементов."""
    deduped: list[CatalogItem] = []
    seen_urls: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()

    for item in items:
        # Приоритет: URL
        url_key = _canonical_url_key(item.canonical_url)
        if url_key and url_key in seen_urls:
            continue

        # Запасной ключ: (url, title)
        key = (
            _canonical_url_key(item.canonical_url),
            _normalize_text(item.title).lower(),
        )
        if not key[0] and not key[1]:
            continue
        if key in seen_keys:
            continue

        if url_key:
            seen_urls.add(url_key)
        seen_keys.add(key)
        deduped.append(item)

    return deduped


# ---------------------------------------------------------------------------
# CatalogItem
# ---------------------------------------------------------------------------

@dataclass
class CatalogItem:
    item_id: str
    source_platform: str
    source_url: str
    canonical_url: str
    item_type: str
    title: str
    description: str
    provider_name: str
    language: str
    category_raw: str
    tags_raw: list[str] = field(default_factory=list)
    difficulty_level: str = ""
    duration_text: str = ""
    duration_hours: float | None = None
    lessons_count: int | None = None
    modules_count: int | None = None
    certificate_available: bool | None = None
    project_based: bool | None = None
    mentor_support: bool | None = None
    job_support: bool | None = None
    ai_topics: list[str] = field(default_factory=list)
    audience_types: list[str] = field(default_factory=list)
    parent_program_id: str | None = None
    child_course_ids: list[str] = field(default_factory=list)
    crawl_depth: int = 0
    extraction_confidence: float | None = None
    extraction_notes: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Построение CatalogItem
# ---------------------------------------------------------------------------

def _build_catalog_item_from_raw_card(
    *,
    platform_name: str,
    raw_card: dict[str, Any],
) -> CatalogItem | None:
    title = _normalize_text(raw_card.get("title"))
    description = _normalize_text(raw_card.get("description"))
    canonical_url = _pick_canonical_url(raw_card)
    source_url = _pick_source_url(raw_card, canonical_url)

    if not title and not canonical_url and not description:
        return None

    # Пропускаем явный мусор
    if title and _looks_like_noise_title(title):
        return None

    tags = _normalize_list(raw_card.get("tags"))
    category_raw = tags[0] if tags else ""
    text_blob = _raw_to_text_blob(raw_card)

    item_type = _normalize_text(raw_card.get("item_type"))
    if not item_type:
        item_type = _infer_item_type(canonical_url, title, description, tags)

    duration_text = _normalize_text(raw_card.get("duration_text"))
    if not duration_text:
        duration_text = _normalize_text(raw_card.get("raw_text"))

    duration_hours = _extract_duration_hours(duration_text or text_blob)
    lessons_count = _extract_int_by_pattern(LESSONS_RE, text_blob)
    modules_count = _extract_int_by_pattern(MODULES_RE, text_blob)

    extraction_confidence = raw_card.get("extraction_confidence")
    if extraction_confidence is not None:
        try:
            extraction_confidence = float(extraction_confidence)
        except Exception:
            extraction_confidence = None

    title_for_id = title or canonical_url or source_url or "item"
    item_id = _stable_item_id(platform_name, canonical_url or source_url, title_for_id)

    combined_text = " | ".join(
        part for part in [title, description, text_blob] if part
    )

    certificate_available: bool | None = None
    mentor_support: bool | None = None
    job_support: bool | None = None
    project_based: bool | None = None

    if combined_text:
        certificate_available = _contains_any(combined_text, CERTIFICATE_MARKERS)
        mentor_support = _contains_any(combined_text, MENTOR_MARKERS)
        job_support = _contains_any(combined_text, JOB_MARKERS)
        project_based = _contains_any(combined_text, PROJECT_MARKERS)

    crawl_depth_raw = raw_card.get("crawl_depth", 0)
    try:
        crawl_depth = int(crawl_depth_raw)
    except Exception:
        crawl_depth = 0

    extraction_notes = _normalize_list(raw_card.get("extraction_notes"))
    selector_used = _normalize_text(raw_card.get("selector_used"))
    if selector_used:
        extraction_notes.append(f"selector:{selector_used}")

    return CatalogItem(
        item_id=item_id,
        source_platform=_normalize_text(platform_name),
        source_url=source_url or canonical_url,
        canonical_url=canonical_url or source_url,
        item_type=item_type,
        title=title or canonical_url or source_url,
        description=description,
        provider_name=_pick_provider_name(platform_name, raw_card),
        language=_infer_language(combined_text, platform_name),
        category_raw=category_raw,
        tags_raw=tags,
        difficulty_level=_infer_difficulty(combined_text),
        duration_text=duration_text,
        duration_hours=duration_hours,
        lessons_count=lessons_count,
        modules_count=modules_count,
        certificate_available=certificate_available,
        project_based=project_based,
        mentor_support=mentor_support,
        job_support=job_support,
        ai_topics=_infer_ai_topics(combined_text, tags),
        audience_types=_infer_audience_types(combined_text),
        parent_program_id=_normalize_text(raw_card.get("parent_program_id")) or None,
        child_course_ids=_normalize_list(raw_card.get("child_course_ids")),
        crawl_depth=crawl_depth,
        extraction_confidence=extraction_confidence,
        extraction_notes=extraction_notes,
    )


def _document_to_mapping(document: Any) -> dict[str, Any]:
    if document is None:
        return {}

    if isinstance(document, dict):
        return dict(document)

    if is_dataclass(document):
        try:
            data = asdict(document)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    if hasattr(document, "model_dump"):
        try:
            data = document.model_dump()
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    result: dict[str, Any] = {}
    for key in (
        "url",
        "final_url",
        "source_url",
        "title",
        "title_hint",
        "text",
        "html",
        "status_code",
        "content_type",
        "encoding",
        "meta",
        "access_mode",
        "description",
        "summary",
    ):
        try:
            value = getattr(document, key)
        except Exception:
            continue
        result[key] = value

    return result


def _build_catalog_item_from_document(
    *,
    platform_name: str,
    document: Any,
) -> CatalogItem | None:
    data = _document_to_mapping(document)
    if not data:
        return None

    meta = data.get("meta", {}) or {}
    if not isinstance(meta, dict):
        meta = {}

    canonical_url = _normalize_url(
        data.get("final_url") or data.get("url") or data.get("source_url") or meta.get("effective_url")
    )
    source_url = _normalize_url(
        meta.get("requested_url") or data.get("url") or data.get("source_url") or canonical_url
    )

    title = _normalize_text(data.get("title") or data.get("title_hint"))
    text = _normalize_text(data.get("text"))
    description = _normalize_text(data.get("description") or data.get("summary"))

    if not description and text:
        description = text[:1200]

    if not title:
        if text:
            title = text[:120].split(" | ")[0].strip()
        elif canonical_url:
            title = canonical_url

    if not title and not canonical_url and not description:
        return None

    if title and _looks_like_noise_title(title):
        return None

    item_type = _infer_item_type(
        canonical_url,
        title,
        description,
        [],
    )

    combined_text = " | ".join(part for part in [title, description, text] if part)
    duration_text = _normalize_text(meta.get("duration_text"))
    duration_hours = _extract_duration_hours(duration_text or combined_text)

    try:
        crawl_depth = int(meta.get("crawl_depth", 0))
    except Exception:
        crawl_depth = 0

    extraction_notes = [
        "fallback:document_normalization",
    ]
    access_mode = _normalize_text(data.get("access_mode"))
    if access_mode:
        extraction_notes.append(f"access_mode:{access_mode}")

    item_id = _stable_item_id(
        platform_name,
        canonical_url or source_url,
        title or canonical_url or source_url or "document",
    )

    return CatalogItem(
        item_id=item_id,
        source_platform=_normalize_text(platform_name),
        source_url=source_url or canonical_url,
        canonical_url=canonical_url or source_url,
        item_type=item_type,
        title=title or canonical_url or source_url,
        description=description,
        provider_name=_normalize_text(platform_name),
        language=_infer_language(combined_text, platform_name),
        category_raw="",
        tags_raw=[],
        difficulty_level=_infer_difficulty(combined_text),
        duration_text=duration_text,
        duration_hours=duration_hours,
        lessons_count=_extract_int_by_pattern(LESSONS_RE, combined_text),
        modules_count=_extract_int_by_pattern(MODULES_RE, combined_text),
        certificate_available=_contains_any(combined_text, CERTIFICATE_MARKERS) if combined_text else None,
        project_based=_contains_any(combined_text, PROJECT_MARKERS) if combined_text else None,
        mentor_support=_contains_any(combined_text, MENTOR_MARKERS) if combined_text else None,
        job_support=_contains_any(combined_text, JOB_MARKERS) if combined_text else None,
        ai_topics=_infer_ai_topics(combined_text, []),
        audience_types=_infer_audience_types(combined_text),
        parent_program_id=None,
        child_course_ids=[],
        crawl_depth=crawl_depth,
        extraction_confidence=None,
        extraction_notes=extraction_notes,
    )


# ---------------------------------------------------------------------------
# Главная функция нормализации
# ---------------------------------------------------------------------------

def normalize_documents_to_catalog_items(
    *,
    platform_name: str,
    documents: list[Any] | None = None,
    raw_catalog_items: list[dict[str, Any]] | None = None,
) -> list[CatalogItem]:
    documents = documents or []
    raw_catalog_items = raw_catalog_items or []

    # Этап 1: дедупликация сырых данных (до нормализации)
    raw_catalog_items = _dedupe_raw_catalog_items(raw_catalog_items)

    normalized_items: list[CatalogItem] = []

    for raw_card in raw_catalog_items:
        try:
            item = _build_catalog_item_from_raw_card(
                platform_name=platform_name,
                raw_card=raw_card,
            )
        except Exception:
            item = None

        if item is not None:
            normalized_items.append(item)

    if not normalized_items:
        for document in documents:
            try:
                item = _build_catalog_item_from_document(
                    platform_name=platform_name,
                    document=document,
                )
            except Exception:
                item = None

            if item is not None:
                normalized_items.append(item)

    else:
        existing_keys = {
            (
                _canonical_url_key(item.canonical_url),
                _normalize_text(item.title).lower(),
            )
            for item in normalized_items
        }

        for document in documents:
            try:
                fallback_item = _build_catalog_item_from_document(
                    platform_name=platform_name,
                    document=document,
                )
            except Exception:
                fallback_item = None

            if fallback_item is None:
                continue

            fallback_key = (
                _canonical_url_key(fallback_item.canonical_url),
                _normalize_text(fallback_item.title).lower(),
            )
            if fallback_key in existing_keys:
                continue

            if fallback_item.canonical_url and _host_of(fallback_item.canonical_url):
                normalized_items.append(fallback_item)
                existing_keys.add(fallback_key)

    # Этап 2: финальная дедупликация нормализованных элементов
    return _dedupe_catalog_items(normalized_items)