"""Фоновый демон для ежедневного пополнения RAG.

Источники:
- habr.com — хабы (каждые 6 часов)
- tproger.ru — /tag/ai, /news, /new (каждые 12 часов, Playwright + кнопка «Загрузить ещё»)
- arxiv.org — API (каждые 6 часов)

Запуск:
    python scripts/run_daily_daemon.py
    python scripts/run_daily_daemon.py --once  # однократный сбор

Сохраняет новые статьи в RAG с проверкой дубликатов по URL.
Фильтрует нерелевантные статьи по AI/ML ключевым словам.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.rag_store import RAGStore


# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

HABR_HUBS = [
    "machine_learning",
    "natural_language_processing",
    "bigdata",
    "algorithms",
    "programming",
    "devops",
]

TPROGER_PAGES = [
    "https://tproger.ru/tag/ai",
    "https://tproger.ru/news",
    "https://tproger.ru/new",
]

TPROGER_MAX_CLICKS = 5

# Ключевые слова для фильтрации AI/ML статей
AI_ML_KEYWORDS = [
    # Русские
    "искусственный интеллект", "машинное обучение", "нейросет", "нейронн",
    "глубокое обучение", "языковая модель", "языковые модели",
    "чат-бот", "чат бот", "чатбот",
    "компьютерное зрение", "обработка языка", "распознавание речи",
    "трансформер", "transformer", "attention",
    "генеративн", "GAN", "диффузи",
    "обучение с подкреплением", "reinforcement learning",
    "агент", "agent", "LLM", "GPT", "Claude", "Gemini", "Copilot",
    "промпт", "prompt", "RAG",
    "MLOps", "ML", "DL", "NLP", "CV", "RL",
    "датасет", "dataset", "бенчмарк", "benchmark",
    "обучени", "модел",
    "AutoML",
    "data science", "data scientist",
    "глубок", "deep learning",
    "embedding", "эмбеддинг",
    "hugging face", "openai", "anthropic", "deepseek", "qwen",
    # Английские
    "artificial intelligence", "machine learning", "neural network",
    "deep learning", "language model", "computer vision",
    "natural language", "speech recognition",
    "generative adversarial", "reinforcement learning",
    "large language model", "foundation model",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# RAG с проверкой дубликатов
# ---------------------------------------------------------------------------

class DedupRAGStore(RAGStore):
    def is_url_indexed(self, url: str) -> bool:
        try:
            data = self.collection.get(where={"url": url})
            return len(data.get("ids", [])) > 0
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Фильтр релевантности
# ---------------------------------------------------------------------------

def _is_ai_ml_relevant(title: str, text: str) -> bool:
    """Проверяет, относится ли статья к AI/ML тематике."""
    combined = f"{title} {text[:2000]}".lower()
    return any(kw.lower() in combined for kw in AI_ML_KEYWORDS)


# ---------------------------------------------------------------------------
# Habr
# ---------------------------------------------------------------------------

def collect_habr(store: DedupRAGStore) -> int:
    total = 0

    for hub_slug in HABR_HUBS:
        url = f"https://habr.com/ru/hubs/{hub_slug}/articles/page1/"
        print(f"  [habr] {hub_slug}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                continue
        except Exception:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.select("a.tm-title__link")

        new_articles = 0
        skipped = 0
        for link in links:
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if not href or not title or len(title) < 10:
                continue
            if href.startswith("/"):
                href = "https://habr.com" + href
            if store.is_url_indexed(href):
                continue

            # Проверяем релевантность по заголовку ДО загрузки
            if not _is_ai_ml_relevant(title, ""):
                skipped += 1
                continue

            article = _crawl(href)
            if article.get("error"):
                continue

            chunks = _chunk(article["text"], source=f"habr_{hub_slug}", url=href, title=article["title"])
            if chunks:
                store.index_chunks(chunks)
                total += len(chunks)
                new_articles += 1
                print(f"    + {title[:80]}")

            time.sleep(1.5)

        if skipped:
            print(f"    Пропущено нерелевантных: {skipped}")
        print(f"    Новых статей: {new_articles}")
        time.sleep(2)

    return total


# ---------------------------------------------------------------------------
# Tproger
# ---------------------------------------------------------------------------

def collect_tproger(store: DedupRAGStore) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [tproger] Playwright не установлен, пропускаю.")
        return 0

    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        for page_url in TPROGER_PAGES:
            print(f"  [tproger] {page_url}...")
            page = context.new_page()

            try:
                page.goto(page_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                for _ in range(TPROGER_MAX_CLICKS):
                    try:
                        load_more = page.locator("text=Загрузить ещё").first
                        if load_more.is_visible():
                            load_more.click()
                            page.wait_for_timeout(1500)
                    except Exception:
                        break

                links = page.evaluate("""() => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors).map(a => ({
                        href: a.href, text: a.textContent.trim()
                    }));
                }""")

                new_articles = 0
                skipped = 0
                for link in links:
                    href = link["href"]
                    title = link["text"]

                    if not href or not title or len(title) < 10:
                        continue
                    if "tproger.ru" not in href:
                        continue
                    if store.is_url_indexed(href):
                        continue
                    if not _is_ai_ml_relevant(title, ""):
                        skipped += 1
                        continue

                    article = _crawl(href)
                    if article.get("error"):
                        continue

                    chunks = _chunk(article["text"], source="tproger", url=href, title=article["title"])
                    if chunks:
                        store.index_chunks(chunks)
                        total += len(chunks)
                        new_articles += 1
                        print(f"    + {title[:80]}")

                    time.sleep(1.5)

                if skipped:
                    print(f"    Пропущено нерелевантных: {skipped}")
                print(f"    Новых статей: {new_articles}")

            except Exception as e:
                print(f"    ⚠️ Ошибка: {e}")
            finally:
                page.close()

            time.sleep(3)

        browser.close()

    return total


# ---------------------------------------------------------------------------
# ArXiv
# ---------------------------------------------------------------------------

def collect_arxiv(store: DedupRAGStore) -> int:
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET

    queries = [
        "machine learning",
        "natural language processing",
        "computer vision",
        "reinforcement learning",
        "generative adversarial networks",
        "large language model agent",
    ]

    total = 0

    for query in queries:
        print(f"  [arxiv] '{query}'...")

        params = urllib.parse.urlencode({
            "search_query": f"all:{query}",
            "start": 0, "max_results": 5,
            "sortBy": "submittedDate", "sortOrder": "descending",
        })
        url = f"http://export.arxiv.org/api/query?{params}"

        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                xml_data = resp.read().decode("utf-8")
        except Exception:
            continue

        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        root = ET.fromstring(xml_data)

        new_articles = 0
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            link_el = entry.find("atom:id", ns)

            article_url = link_el.text.strip() if link_el is not None else ""
            if store.is_url_indexed(article_url):
                continue

            title = title_el.text.strip() if title_el is not None else ""
            summary = summary_el.text.strip() if summary_el is not None else ""

            text = f"Title: {title}\nSummary: {summary}"
            chunks = _chunk(text, source="arxiv", url=article_url, title=title)

            if chunks:
                store.index_chunks(chunks)
                total += len(chunks)
                new_articles += 1
                print(f"    + {title[:80]}")

        print(f"    Новых статей: {new_articles}")
        time.sleep(3)

    return total


# ---------------------------------------------------------------------------
# Общие утилиты
# ---------------------------------------------------------------------------

def _crawl(url: str) -> dict[str, Any]:
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
    return {"url": url, "title": title, "text": text.strip()}


def _chunk(text: str, source: str, url: str, title: str = "") -> list[dict[str, Any]]:
    if not text:
        return []
    words = text.split()
    chunks = []
    ts = datetime.now(timezone.utc).isoformat()
    for i in range(0, len(words), 400):
        c = " ".join(words[i:i + 500])
        if c:
            chunks.append({
                "chunk_id": f"daily::{source}::{url[:60]}_{i}_{int(time.time())}",
                "text": c,
                "source": source,
                "section": "daily",
                "title": title or url,
                "metadata": {"url": url, "indexed_at": ts},
            })
    return chunks


# ---------------------------------------------------------------------------
# Демон
# ---------------------------------------------------------------------------

def run_daemon(interval_hours: int = 6) -> None:
    store = DedupRAGStore()
    print(f"[daemon] Запуск (интервал: {interval_hours} ч.). RAG: {store.count} чанков")

    while True:
        print(f"\n{'='*60}")
        print(f"[daemon] Цикл: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        try:
            n = collect_habr(store)
            print(f"[daemon] Habr: +{n} чанков (всего: {store.count})")
        except Exception as e:
            print(f"[daemon] Habr error: {e}")

        try:
            n = collect_arxiv(store)
            print(f"[daemon] ArXiv: +{n} чанков (всего: {store.count})")
        except Exception as e:
            print(f"[daemon] ArXiv error: {e}")

        if datetime.now().hour % 12 < interval_hours:
            try:
                n = collect_tproger(store)
                print(f"[daemon] Tproger: +{n} чанков (всего: {store.count})")
            except Exception as e:
                print(f"[daemon] Tproger error: {e}")

        print(f"[daemon] Следующий цикл через {interval_hours} ч.")
        time.sleep(interval_hours * 3600)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ежедневный демон пополнения RAG")
    parser.add_argument("--once", action="store_true", help="Однократный сбор")
    parser.add_argument("--interval", type=int, default=6, help="Интервал (часы)")
    args = parser.parse_args()

    if args.once:
        store = DedupRAGStore()
        print(f"RAG: {store.count} чанков\n")

        h = collect_habr(store)
        print(f"Habr: +{h} чанков")

        a = collect_arxiv(store)
        print(f"ArXiv: +{a} чанков")

        t = collect_tproger(store)
        print(f"Tproger: +{t} чанков")

        print(f"\nИтого: {store.count} чанков")
    else:
        run_daemon(interval_hours=args.interval)


if __name__ == "__main__":
    main()