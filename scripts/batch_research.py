"""Пакетный сбор статей с Habr.com по AI/ML направлениям.

Источники:
- habr.com/ru/hubs/<tag>/articles/ — статьи по тегам
- Пагинация: page1, page2, page3...

Запуск:
    python scripts/batch_research.py

Собирает статьи по каждому тегу,
краулит их, сохраняет чанки в RAG.
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.rag_store import RAGStore


# ---------------------------------------------------------------------------
# Хабы Хабра, соответствующие 12 направлениям
# ---------------------------------------------------------------------------

HABR_HUBS: dict[str, str] = {
    "machine_learning": "machine_learning",
    "deep_learning": "deep_learning",
    "nlp": "natural_language_processing",
    "computer_vision": "computer_vision",
    "data_science": "data_science",
    "bigdata": "bigdata",
    "robotics": "robotics",
    "algorithms": "algorithms",
    "programming": "programming",
    "devops": "devops",
    "cybersecurity": "information_security",
    "management": "project_management",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ARTICLES_PER_HUB = 10
PAGES_TO_CHECK = 3


# ---------------------------------------------------------------------------
# Сбор ссылок с Хабра
# ---------------------------------------------------------------------------

def collect_from_habr(hub_slug: str, max_articles: int = 10, pages: int = 3) -> list[dict[str, str]]:
    """Собирает статьи из хаба Хабра с пагинацией."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for page in range(1, pages + 1):
        url = f"https://habr.com/ru/hubs/{hub_slug}/articles/page{page}/"
        print(f"     📄 Страница {page}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                break
        except Exception as e:
            print(f"        ⚠️ Ошибка: {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.select("a.tm-title__link")

        if not links:
            break

        for link in links:
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if not href or not title or len(title) < 10:
                continue

            if href.startswith("/"):
                href = "https://habr.com" + href
            elif not href.startswith("http"):
                continue

            key = href.lower().rstrip("/")
            if key in seen:
                continue
            seen.add(key)

            results.append({"title": title[:200], "url": href, "source": f"habr_{hub_slug}"})

            if len(results) >= max_articles:
                break

        if len(results) >= max_articles:
            break

        time.sleep(1)

    return results


# ---------------------------------------------------------------------------
# Краулинг статьи
# ---------------------------------------------------------------------------

def crawl_article(url: str) -> dict[str, Any]:
    """Загружает страницу статьи и извлекает текст."""
    print(f"     📄 {url[:100]}...")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        return {"url": url, "title": "", "text": "", "error": str(e)}

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title else ""
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()

    return {"url": url, "title": title, "text": text}


# ---------------------------------------------------------------------------
# Разбивка на чанки
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    source: str,
    url: str,
    title: str = "",
    chunk_size: int = 500,
) -> list[dict[str, Any]]:
    if not text:
        return []

    words = text.split()
    chunks: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).isoformat()

    for i in range(0, len(words), chunk_size - 100):
        chunk_text = " ".join(words[i:i + chunk_size])
        if not chunk_text:
            continue

        chunks.append(
            {
                "chunk_id": f"habr::{source}::{url[:60]}_{i}_{int(time.time())}",
                "text": chunk_text,
                "source": source,
                "section": "habr",
                "title": title or url,
                "metadata": {"url": url, "chunk_index": i, "indexed_at": ts},
            }
        )

    return chunks


# ---------------------------------------------------------------------------
# Основной цикл
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("СБОР СТАТЕЙ С HABR.COM ПО НАПРАВЛЕНИЯМ")
    print("=" * 60)

    store = RAGStore()
    total_articles = 0
    total_indexed = 0

    for topic_key, hub_slug in HABR_HUBS.items():
        print(f"\n{'─' * 60}")
        print(f"📚 {topic_key} (habr.com/ru/hubs/{hub_slug}/)")
        print(f"{'─' * 60}")

        articles = collect_from_habr(hub_slug, max_articles=ARTICLES_PER_HUB, pages=PAGES_TO_CHECK)

        if not articles:
            print("  Статей не найдено.")
            continue

        print(f"  Найдено: {len(articles)} статей")
        total_articles += len(articles)

        for article in articles:
            try:
                page = crawl_article(article["url"])
                if page.get("error"):
                    continue

                chunks = chunk_text(
                    page["text"],
                    source=f"habr_{article['source']}",
                    url=article["url"],
                    title=article["title"],
                )

                if chunks:
                    total_indexed += store.index_chunks(chunks)
            except Exception as e:
                print(f"        ❌ Ошибка: {e}")

            time.sleep(2)

        time.sleep(2)

    print("\n" + "=" * 60)
    print("СБОР ЗАВЕРШЁН")
    print("=" * 60)
    print(f"Всего статей: {total_articles}")
    print(f"Всего проиндексировано: {total_indexed} чанков")
    print(f"Итоговый размер RAG: {store.count} чанков")


if __name__ == "__main__":
    main()