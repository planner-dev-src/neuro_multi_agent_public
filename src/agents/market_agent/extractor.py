from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

try:
    import trafilatura
except Exception:
    trafilatura = None


TEXT_OUTPUT_ROOT = Path("data/market_text")


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "unknown"


def _normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_with_trafilatura(html: str) -> str:
    if not html or trafilatura is None:
        return ""

    try:
        text = trafilatura.extract(
            html,
            output_format="txt",
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        return _normalize_text(text or "")
    except Exception:
        return ""


def _extract_with_bs4(html: str) -> str:
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return _normalize_text(text)
    except Exception:
        return ""


def _build_text_output_path(platform_name: str, source_tag: str) -> Path:
    platform_slug = _slugify(platform_name)
    source_slug = _slugify(source_tag)
    return TEXT_OUTPUT_ROOT / platform_slug / f"{source_slug}.txt"


def _save_text(text: str, platform_name: str, source_tag: str) -> str | None:
    if not text:
        return None

    output_path = _build_text_output_path(platform_name, source_tag)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return str(output_path)


def extract_text_with_meta(html: str, platform_name: str, source_tag: str) -> dict:
    trafilatura_text = _extract_with_trafilatura(html)
    bs_text = _extract_with_bs4(html)

    final_text = trafilatura_text or bs_text
    extraction_method = "trafilatura" if trafilatura_text else "bs4" if bs_text else "empty"

    saved_text_path = _save_text(final_text, platform_name, source_tag)
    preview = final_text[:300].replace("\n", " ").strip()

    return {
        "platform_name": platform_name,
        "source_tag": source_tag,
        "text": final_text,
        "text_length": len(final_text),
        "preview": preview,
        "saved_text_path": saved_text_path,
        "extraction_method": extraction_method,
        "trafilatura_text_length": len(trafilatura_text),
        "bs_text_length": len(bs_text),
    }