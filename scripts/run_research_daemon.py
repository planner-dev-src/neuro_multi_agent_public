"""Фоновый демон для наполнения RAG из ArXiv.

Запуск:
    python scripts/run_research_daemon.py

Или разовый сбор:
    python scripts/run_research_daemon.py --once

Источники:
- ArXiv API (бесплатно, без ключей)
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.rag_store import RAGStore


# ---------------------------------------------------------------------------
# 12 направлений компании — поисковые запросы для ArXiv
# ---------------------------------------------------------------------------

TOPIC_QUERIES: dict[str, str] = {
    "classical_ml": "machine learning",
    "nlp": "natural language processing",
    "computer_vision": "computer vision",
    "time_series": "time series forecasting",
    "reinforcement_learning": "reinforcement learning",
    "speech_audio": "speech recognition audio processing",
    "gan": "generative adversarial networks",
    "genetic_algorithms": "genetic algorithms evolutionary computation",
    "ai_project_management_custom_sales": "AI project management",
    "production_integration": "MLOps deployment production",
    "llm_agents": "LLM agents autonomous agents",
    "automl": "automated machine learning AutoML",
    "data_engineering": "data engineering pipeline",
    "devops_sre": "DevOps SRE cloud infrastructure",
    "cybersecurity": "AI cybersecurity security",
    "product_analytics": "product analytics data driven",
    "product_management_it": "AI product management",
}


# ---------------------------------------------------------------------------
# ArXiv API
# ---------------------------------------------------------------------------

def fetch_arxiv_papers(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Поиск статей на ArXiv через API.

    Возвращает список: [{title, url, summary, published, authors}, ...]
    """
    base_url = "http://export.arxiv.org/api/query"
    search_query = f"all:{query}"
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"

    print(f"[arxiv] Поиск: '{query}'...")

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            xml_data = response.read().decode("utf-8")
    except Exception as e:
        print(f"[arxiv] Ошибка запроса: {e}")
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    root = ET.fromstring(xml_data)
    papers: list[dict[str, Any]] = []

    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns)
        summary = entry.find("atom:summary", ns)
        link = entry.find("atom:id", ns)
        published = entry.find("atom:published", ns)

        authors = [
            author.find("atom:name", ns).text.strip()
            for author in entry.findall("atom:author", ns)
            if author.find("atom:name", ns) is not None
        ]

        papers.append(
            {
                "title": title.text.strip() if title is not None else "",
                "url": link.text.strip() if link is not None else "",
                "summary": summary.text.strip() if summary is not None else "",
                "published": published.text.strip() if published is not None else "",
                "authors": authors,
            }
        )

    print(f"[arxiv] Найдено: {len(papers)} статей")
    return papers


# ---------------------------------------------------------------------------
# Основной цикл сбора
# ---------------------------------------------------------------------------

def collect_from_arxiv(store: RAGStore, max_per_topic: int = 5) -> int:
    """Собирает статьи из ArXiv по всем направлениям и индексирует в RAG.

    Возвращает количество проиндексированных чанков.
    """
    total_indexed = 0

    for topic_key, query in TOPIC_QUERIES.items():
        papers = fetch_arxiv_papers(query, max_results=max_per_topic)

        if not papers:
            continue

        chunks: list[dict[str, Any]] = []

        for i, paper in enumerate(papers):
            # Заголовок + аннотация как текст чанка
            text = (
                f"Title: {paper['title']}\n"
                f"Authors: {', '.join(paper['authors'][:5])}\n"
                f"Summary: {paper['summary']}"
            )

            chunks.append(
                {
                    "chunk_id": f"arxiv::{topic_key}::{i}_{datetime.now().strftime('%Y%m%d')}",
                    "text": text,
                    "source": "arxiv",
                    "section": topic_key,
                    "title": paper["title"][:200],
                    "metadata": {
                        "url": paper["url"],
                        "published": paper["published"],
                        "topic_key": topic_key,
                        "query": query,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                    },
                }
            )

        indexed = store.index_chunks(chunks)
        total_indexed += indexed
        print(f"[arxiv] {topic_key}: {len(papers)} статей, {indexed} чанков")

        # Пауза между запросами (ArXiv требует вежливости)
        time.sleep(3)

    return total_indexed


# ---------------------------------------------------------------------------
# Демон
# ---------------------------------------------------------------------------

def run_daemon(interval_hours: int = 6, max_per_topic: int = 5) -> None:
    """Запускает бесконечный цикл сбора из ArXiv."""
    store = RAGStore()

    print(f"[daemon] Запуск фонового сборщика ArXiv (интервал: {interval_hours} ч.)")
    print(f"[daemon] RAG: {store.count} чанков в хранилище")

    while True:
        print(f"\n{'='*60}")
        print(f"[daemon] Цикл сбора: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        try:
            indexed = collect_from_arxiv(store, max_per_topic=max_per_topic)
            print(f"[daemon] Проиндексировано: {indexed} чанков")
            print(f"[daemon] Всего в RAG: {store.count} чанков")
        except Exception as e:
            print(f"[daemon] Ошибка цикла: {e}")

        print(f"[daemon] Следующий сбор через {interval_hours} ч.")
        time.sleep(interval_hours * 3600)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Фоновый сборщик ArXiv → RAG")
    parser.add_argument("--once", action="store_true", help="Однократный сбор и выход")
    parser.add_argument("--interval", type=int, default=6, help="Интервал между сборами в часах (для демона)")
    parser.add_argument("--max", type=int, default=5, help="Максимум статей на тему")
    args = parser.parse_args()

    if args.once:
        store = RAGStore()
        indexed = collect_from_arxiv(store, max_per_topic=args.max)
        print(f"\nГотово. Проиндексировано: {indexed} чанков. Всего в RAG: {store.count}")
    else:
        run_daemon(interval_hours=args.interval, max_per_topic=args.max)


if __name__ == "__main__":
    main()