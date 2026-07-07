from __future__ import annotations


import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag


TEXT_OUTPUT_ROOT = Path("data/normalized_text/market_agent")


WHITESPACE_RE = re.compile(r"\s+")
SCRIPT_STYLE_RE = re.compile(r"^(script|style|noscript)$", re.IGNORECASE)

CARD_CONTAINER_HINTS = (
    "card",
    "course",
    "program",
    "product",
    "item",
    "tile",
    "result",
    "offer",
    "catalog",
    "edu-program",
)

LINK_TEXT_HINTS = (
    "подробнее",
    "о курсе",
    "о программе",
    "learn more",
    "details",
    "program",
    "course",
    "курс",
    "программа",
)

PROGRAM_PATH_HINTS = (
    "/course",
    "/courses",
    "/program",
    "/programs",
    "/profession",
    "/professions",
    "/track",
    "/tracks",
    "/bootcamp",
    "/specialization",
    "/catalog/",
    "/edu/dpo/",
)

CATALOG_PATH_HINTS = (
    "/catalog",
    "/courses",
    "/navigation",
    "/education",
    "/edu/dpo",
    "/programs",
)

PAGINATION_QUERY_KEYS = (
    "page",
    "p",
)

PAGINATION_TEXT_HINTS = (
    "next",
    "далее",
    "след",
    "ещё",
    "more",
    "load more",
    "show more",
)

JSONLD_TYPES_OF_INTEREST = {
    "course",
    "courseinstance",
    "itemlist",
    "listitem",
    "educationaloccupationalprogram",
    "creativeworkseries",
}



def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return WHITESPACE_RE.sub(" ", text)



def _normalize_url(url: str) -> str:
    url = _normalize_text(url)
    if not url:
        return ""

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    normalized_query = urlencode(query_pairs, doseq=True)
    normalized = parsed._replace(fragment="", query=normalized_query)
    return urlunparse(normalized)



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



def _looks_like_program_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if any(token in path for token in PROGRAM_PATH_HINTS):
        return True

    return bool(
        re.search(
            r"/(python|java|qa|ml|ai|data|analytics|backend|frontend|devops|sql|design|marketing)([-/]|$)",
            path,
        )
    )



def _looks_like_catalog_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(token in path for token in CATALOG_PATH_HINTS)



def _looks_like_pagination_url(url: str) -> bool:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    for key in PAGINATION_QUERY_KEYS:
        if key in query and str(query.get(key, "")).strip():
            return True

    path = parsed.path.lower()
    if re.search(r"/page/\d+/?$", path):
        return True

    return False



def _absolute_url(source_url: str, href: str) -> str:
    href = _normalize_text(href)
    if not href:
        return ""

    if href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return ""

    return _normalize_url(urljoin(source_url, href))



def _same_host_or_subdomain(source_url: str, candidate_url: str) -> bool:
    source_host = _host_of(source_url)
    candidate_host = _host_of(candidate_url)

    if not source_host or not candidate_host:
        return False

    return candidate_host == source_host or candidate_host.endswith("." + source_host) or source_host.endswith("." + candidate_host)



def _get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")



def _visible_text_lines(soup: BeautifulSoup) -> list[str]:
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()

    texts: list[str] = []
    for node in soup.stripped_strings:
        text = _normalize_text(node)
        if not text:
            continue
        texts.append(text)

    deduped: list[str] = []
    seen: set[str] = set()
    for text in texts:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)

    return deduped



def _extract_page_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return _normalize_text(soup.title.string)

    for selector in ("h1", "[data-testid*=title]", "[class*=title]"):
        element = soup.select_one(selector)
        if element:
            text = _normalize_text(element.get_text(" ", strip=True))
            if text:
                return text

    return ""



def _extract_meta_description(soup: BeautifulSoup) -> str:
    element = soup.find("meta", attrs={"name": re.compile("^description$", re.IGNORECASE)})
    if element and element.get("content"):
        return _normalize_text(element.get("content"))

    element = soup.find("meta", attrs={"property": re.compile("^og:description$", re.IGNORECASE)})
    if element and element.get("content"):
        return _normalize_text(element.get("content"))

    return ""



def _extract_candidate_card_nodes(soup: BeautifulSoup) -> list[Tag]:
    candidates: list[Tag] = []

    selectors = [
        "article",
        "[class*=card]",
        "[class*=course]",
        "[class*=program]",
        "[class*=catalog]",
        "[class*=product]",
        "[data-testid*=card]",
        "[data-testid*=course]",
        "[data-testid*=program]",
        "[data-qa*=card]",
        "[data-qa*=course]",
        "[data-qa*=program]",
    ]

    for selector in selectors:
        for node in soup.select(selector):
            if isinstance(node, Tag):
                candidates.append(node)

    deduped: list[Tag] = []
    seen: set[int] = set()

    for node in candidates:
        ident = id(node)
        if ident in seen:
            continue
        seen.add(ident)
        deduped.append(node)

    return deduped



def _extract_anchor_text(anchor: Tag) -> str:
    return _normalize_text(anchor.get_text(" ", strip=True))



def _extract_node_title(node: Tag) -> str:
    for selector in ("h1", "h2", "h3", "h4", "[class*=title]", "[class*=name]", "a"):
        target = node.select_one(selector)
        if target:
            text = _normalize_text(target.get_text(" ", strip=True))
            if len(text) >= 3:
                return text

    text = _normalize_text(node.get_text(" ", strip=True))
    return text[:200]



def _extract_node_description(node: Tag, title: str = "") -> str:
    text = _normalize_text(node.get_text(" ", strip=True))
    if not text:
        return ""

    if title and text.startswith(title):
        text = _normalize_text(text[len(title):])

    return text[:1500]



def _extract_node_tags(node: Tag) -> list[str]:
    tags: list[str] = []

    for selector in (
        "[class*=tag]",
        "[class*=badge]",
        "[class*=label]",
        "[class*=chip]",
        "[data-testid*=tag]",
        "[data-testid*=badge]",
    ):
        for el in node.select(selector):
            text = _normalize_text(el.get_text(" ", strip=True))
            if text and len(text) <= 80:
                tags.append(text)

    deduped: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)

    return deduped[:20]



def _extract_duration_text(node: Tag) -> str:
    text = _normalize_text(node.get_text(" ", strip=True))
    if not text:
        return ""

    patterns = [
        r"\b\d+(?:[.,]\d+)?\s*(?:ч|час(?:а|ов)?|hours?|hrs?|h)\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:мес(?:яц(?:а|ев)?)?\.?)\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:нед(?:ел[яьиь])?)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _normalize_text(match.group(0))

    return ""



def _best_card_link(node: Tag, source_url: str) -> tuple[str, str]:
    best_url = ""
    best_text = ""

    anchors = node.find_all("a", href=True)
    for anchor in anchors:
        href = anchor.get("href", "")
        absolute = _absolute_url(source_url, href)
        if not absolute:
            continue

        text = _extract_anchor_text(anchor)
        score = 0

        if _looks_like_program_url(absolute):
            score += 5
        if text and any(hint in text.lower() for hint in LINK_TEXT_HINTS):
            score += 3
        if text and len(text) >= 3:
            score += 1

        if not best_url:
            best_url = absolute
            best_text = text

        if score >= 5:
            return absolute, text

    return best_url, best_text



def _node_looks_like_catalog_card(node: Tag, source_url: str) -> bool:
    classes = " ".join(node.get("class", [])) if node.get("class") else ""
    attrs_blob = " ".join(
        [
            classes,
            _normalize_text(node.get("id")),
            _normalize_text(node.get("data-testid")),
            _normalize_text(node.get("data-qa")),
        ]
    ).lower()

    text = _normalize_text(node.get_text(" ", strip=True))
    title = _extract_node_title(node)
    link, _ = _best_card_link(node, source_url)

    if any(hint in attrs_blob for hint in CARD_CONTAINER_HINTS):
        return True

    if link and title and len(title) >= 3:
        return True

    if len(text) >= 20 and len(text) <= 2000 and node.find("a", href=True):
        return True

    return False



def extract_text_with_meta(
    *,
    html: str,
    platform_name: str,
    source_tag: str,
) -> dict[str, Any]:
    soup = _get_soup(html)
    title = _extract_page_title(soup)
    description = _extract_meta_description(soup)
    lines = _visible_text_lines(soup)

    combined_parts: list[str] = []
    if title:
        combined_parts.append(title)
    if description and description != title:
        combined_parts.append(description)
    combined_parts.extend(lines)

    seen: set[str] = set()
    final_parts: list[str] = []
    for part in combined_parts:
        normalized = _normalize_text(part)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        final_parts.append(normalized)

    text = "\n".join(final_parts).strip()

    TEXT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_platform = re.sub(r"[^a-zA-Z0-9]+", "_", platform_name).strip("_") or "platform"
    safe_source = re.sub(r"[^a-zA-Z0-9]+", "_", source_tag).strip("_") or "source"
    saved_path = TEXT_OUTPUT_ROOT / f"{safe_platform}__{safe_source}.txt"
    saved_path.write_text(text, encoding="utf-8")

    return {
        "text": text,
        "saved_text_path": str(saved_path),
        "extraction_method": "visible_text_bs4",
    }



def extract_catalog_items_from_html(
    *,
    html: str,
    platform_name: str,
    source_url: str,
) -> list[dict[str, Any]]:
    soup = _get_soup(html)
    nodes = _extract_candidate_card_nodes(soup)

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for node in nodes:
        if not _node_looks_like_catalog_card(node, source_url):
            continue

        title = _extract_node_title(node)
        description = _extract_node_description(node, title=title)
        url, link_text = _best_card_link(node, source_url)
        tags = _extract_node_tags(node)
        duration_text = _extract_duration_text(node)
        raw_text = _normalize_text(node.get_text(" ", strip=True))

        if not title and not url:
            continue

        item_type = "program" if _looks_like_program_url(url) else "catalog_item"
        key = (_url_key(url), title.lower().strip())

        if key in seen:
            continue
        seen.add(key)

        items.append(
            {
                "platform_name": platform_name,
                "source_url": source_url,
                "url": url,
                "title": title or link_text or url,
                "description": description,
                "tags": tags,
                "duration_text": duration_text,
                "item_type": item_type,
                "raw_text": raw_text[:3000],
                "selector_used": "html_card_heuristics",
                "extraction_confidence": 0.72,
                "extraction_notes": [
                    "source:html",
                    "heuristic:card_node",
                ],
            }
        )

    return items



def _iter_jsonld_objects(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if obj is None:
            return

        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return

        if isinstance(obj, dict):
            result.append(obj)

            if "@graph" in obj:
                walk(obj.get("@graph"))

            if "itemListElement" in obj:
                walk(obj.get("itemListElement"))

            if "hasCourse" in obj:
                walk(obj.get("hasCourse"))

            if "item" in obj:
                walk(obj.get("item"))

    walk(value)
    return result



def _load_jsonld_blocks(soup: BeautifulSoup) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.IGNORECASE)}):
        raw = script.string or script.get_text(" ", strip=False)
        raw = (raw or "").strip()
        if not raw:
            continue

        try:
            parsed = json.loads(raw)
        except Exception:
            continue

        blocks.extend(_iter_jsonld_objects(parsed))

    return blocks



def _jsonld_type_names(obj: dict[str, Any]) -> set[str]:
    raw_type = obj.get("@type")
    values: list[str] = []

    if isinstance(raw_type, str):
        values = [raw_type]
    elif isinstance(raw_type, list):
        values = [str(item) for item in raw_type]

    return {value.strip().lower() for value in values if str(value).strip()}



def _jsonld_extract_name(obj: dict[str, Any]) -> str:
    for key in ("name", "headline", "title"):
        value = _normalize_text(obj.get(key))
        if value:
            return value
    return ""



def _jsonld_extract_description(obj: dict[str, Any]) -> str:
    for key in ("description", "abstract"):
        value = _normalize_text(obj.get(key))
        if value:
            return value
    return ""



def _jsonld_extract_url(obj: dict[str, Any], source_url: str) -> str:
    for key in ("url", "@id"):
        value = _normalize_text(obj.get(key))
        if value:
            return _absolute_url(source_url, value) if not urlparse(value).scheme else _normalize_url(value)
    return ""



def _jsonld_extract_provider(obj: dict[str, Any]) -> str:
    provider = obj.get("provider") or obj.get("publisher") or obj.get("sourceOrganization")

    if isinstance(provider, dict):
        return _normalize_text(provider.get("name"))

    if isinstance(provider, list):
        for item in provider:
            if isinstance(item, dict):
                name = _normalize_text(item.get("name"))
                if name:
                    return name
            else:
                name = _normalize_text(item)
                if name:
                    return name

    return _normalize_text(provider)



def _jsonld_extract_tags(obj: dict[str, Any]) -> list[str]:
    tags: list[str] = []

    for key in ("keywords", "about", "skills"):
        value = obj.get(key)

        if isinstance(value, str):
            for part in re.split(r"[,;|/]+", value):
                part = _normalize_text(part)
                if part:
                    tags.append(part)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    name = _normalize_text(item.get("name"))
                    if name:
                        tags.append(name)
                else:
                    text = _normalize_text(item)
                    if text:
                        tags.append(text)

        elif isinstance(value, dict):
            name = _normalize_text(value.get("name"))
            if name:
                tags.append(name)

    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)

    return deduped[:20]



def _jsonld_extract_duration_text(obj: dict[str, Any]) -> str:
    for key in ("timeRequired", "duration"):
        value = _normalize_text(obj.get(key))
        if value:
            return value
    return ""



def _jsonld_to_catalog_item(
    *,
    obj: dict[str, Any],
    platform_name: str,
    source_url: str,
) -> dict[str, Any] | None:
    type_names = _jsonld_type_names(obj)
    if not type_names.intersection(JSONLD_TYPES_OF_INTEREST):
        return None

    title = _jsonld_extract_name(obj)
    description = _jsonld_extract_description(obj)
    url = _jsonld_extract_url(obj, source_url)
    provider_name = _jsonld_extract_provider(obj)
    tags = _jsonld_extract_tags(obj)
    duration_text = _jsonld_extract_duration_text(obj)

    nested_item = obj.get("item")
    if isinstance(nested_item, dict):
        title = title or _jsonld_extract_name(nested_item)
        description = description or _jsonld_extract_description(nested_item)
        nested_url = _jsonld_extract_url(nested_item, source_url)
        url = url or nested_url
        provider_name = provider_name or _jsonld_extract_provider(nested_item)
        nested_tags = _jsonld_extract_tags(nested_item)
        if nested_tags:
            tags = tags or nested_tags
        duration_text = duration_text or _jsonld_extract_duration_text(nested_item)

    if not title and not url:
        return None

    item_type = "program"
    if "course" in type_names or "courseinstance" in type_names:
        item_type = "course"
    elif "educationaloccupationalprogram" in type_names:
        item_type = "program"
    elif "itemlist" in type_names or "listitem" in type_names:
        item_type = "catalog_item"

    return {
        "platform_name": platform_name,
        "source_url": source_url,
        "url": url,
        "title": title or url,
        "description": description,
        "provider_name": provider_name,
        "tags": tags,
        "duration_text": duration_text,
        "item_type": item_type,
        "raw_text": _normalize_text(json.dumps(obj, ensure_ascii=False))[:3000],
        "selector_used": "jsonld",
        "extraction_confidence": 0.86,
        "extraction_notes": [
            "source:jsonld",
            f"jsonld_types:{','.join(sorted(type_names))}",
        ],
    }



def extract_catalog_items_from_jsonld(
    *,
    html: str,
    platform_name: str,
    source_url: str,
) -> list[dict[str, Any]]:
    soup = _get_soup(html)
    blocks = _load_jsonld_blocks(soup)

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for obj in blocks:
        item = _jsonld_to_catalog_item(
            obj=obj,
            platform_name=platform_name,
            source_url=source_url,
        )
        if not item:
            continue

        key = (_url_key(_normalize_text(item.get("url"))), _normalize_text(item.get("title")).lower())
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items



def _anchor_candidates(soup: BeautifulSoup, source_url: str) -> list[tuple[str, str, str]]:
    anchors: list[tuple[str, str, str]] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        absolute = _absolute_url(source_url, href)
        if not absolute:
            continue
        text = _extract_anchor_text(anchor)
        rel = _normalize_text(" ".join(anchor.get("rel", [])) if anchor.get("rel") else "")
        anchors.append((absolute, text, rel))

    return anchors



def extract_discovered_catalog_links(
    *,
    html: str,
    source_url: str,
) -> list[str]:
    soup = _get_soup(html)
    anchors = _anchor_candidates(soup, source_url)

    discovered: list[str] = []
    seen: set[str] = set()

    for absolute, text, rel in anchors:
        if not _same_host_or_subdomain(source_url, absolute):
            continue

        path = urlparse(absolute).path.lower()
        text_lower = text.lower()

        should_take = False

        if _looks_like_program_url(absolute):
            should_take = True
        elif _looks_like_catalog_url(absolute):
            should_take = True
        elif any(hint in text_lower for hint in LINK_TEXT_HINTS):
            should_take = True
        elif any(token in path for token in ("/education", "/program", "/course", "/catalog")):
            should_take = True

        if not should_take:
            continue

        key = _url_key(absolute)
        if not key or key in seen:
            continue

        seen.add(key)
        discovered.append(absolute)

    return discovered



def extract_pagination_links(
    *,
    html: str,
    source_url: str,
) -> list[str]:
    soup = _get_soup(html)
    anchors = _anchor_candidates(soup, source_url)

    pagination_links: list[str] = []
    seen: set[str] = set()

    for absolute, text, rel in anchors:
        if not _same_host_or_subdomain(source_url, absolute):
            continue

        text_lower = text.lower()
        rel_lower = rel.lower()

        should_take = False

        if "next" in rel_lower:
            should_take = True
        elif _looks_like_pagination_url(absolute):
            should_take = True
        elif any(hint in text_lower for hint in PAGINATION_TEXT_HINTS):
            should_take = True
        elif re.fullmatch(r"\d{1,4}", text_lower):
            should_take = True

        if not should_take:
            continue

        key = _url_key(absolute)
        if not key or key in seen:
            continue

        seen.add(key)
        pagination_links.append(absolute)

    return pagination_links