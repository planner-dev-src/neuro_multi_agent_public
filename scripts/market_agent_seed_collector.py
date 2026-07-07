"""Одноразовый сборщик URL'ов курсов с JS-платформ через Playwright.

Запускать из корня проекта:
    python scripts/market_agent_seed_collector.py

Требования: pip install playwright && playwright install chromium

На выходе: data/input/seeds/  — по одному .txt на платформу,
           готовые для вставки в pipeline.py как EXTRA_SEEDS.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

PROJECT_ROOT = Path.cwd()
OUTPUT_DIR = PROJECT_ROOT / "data" / "input" / "seeds"


TARGETS: dict[str, dict[str, Any]] = {
    "otus": {
        "start_urls": [
            "https://otus.ru/catalog/courses",
            "https://otus.ru/catalog/courses?categories=neural_networks",
            "https://otus.ru/catalog/courses?categories=it-bez-programmirovanija",
            "https://otus.ru/catalog/courses?categories=neural_networks%2Cit-bez-programmirovanija",
            "https://otus.ru/catalog/courses?categories=programmirovanie",
            "https://otus.ru/catalog/courses?categories=data_science",
            "https://otus.ru/catalog/courses?categories=analitika_i_analiz",
            "https://otus.ru/catalog/courses?categories=infrastruktura",
            "https://otus.ru/catalog/courses?categories=upravlenie",
            "https://otus.ru/catalog/courses?categories=testirovanie",
            "https://otus.ru/catalog/courses?categories=bezopasnost",
        ],
        "wait_selector": "a[href*='/lessons/']",
        "link_filter": lambda href: "/lessons/" in href and href.count("/") >= 4,
        "max_scrolls": 15,
        "goto_timeout": 90000,
        "wait_until": "load",
    },
    "netology": {
        "start_urls": ["https://netology.ru/navigation"],
        "wait_selector": "a[href*='/programs/']",
        "link_filter": lambda href: "/programs/" in href or "/courses/" in href,
        "max_scrolls": 20,
        "goto_timeout": 90000,
        "wait_until": "load",
    },
    "skillbox": {
        "start_urls": ["https://skillbox.ru/courses/"],
        "wait_selector": "a[href*='/course/']",
        "link_filter": lambda href: "/course/" in href or "/profession/" in href,
        "max_scrolls": 20,
        "goto_timeout": 90000,
        "wait_until": "load",
    },
    "yandex-practicum": {
        "start_urls": ["https://practicum.yandex.ru/catalog/"],
        "wait_selector": "a[href*='/']",
        "link_filter": lambda href: (
            any(
                token in href
                for token in [
                    "/data-scientist",
                    "/data-analyst",
                    "/python-developer",
                    "/java-developer",
                    "/frontend-developer",
                    "/backend-developer",
                    "/qa-engineer",
                    "/qa-automation",
                    "/data-engineer",
                    "/devops",
                    "/catalog/",
                ]
            )
            and "?" not in href
        ),
        "max_scrolls": 15,
    },
    "karpov-courses": {
        "start_urls": ["https://karpov.courses"],
        "wait_selector": "a[href*='/']",
        "link_filter": lambda href: (
            any(
                token in href
                for token in [
                    "/ml-start",
                    "/analytics",
                    "/dataengineer",
                    "/deep-learning",
                    "/ml-hard",
                    "/ml-engineering",
                    "/systemdesign",
                    "/simulator",
                    "/simulator-ds",
                    "/simulator-sql",
                    "/docker",
                    "/mathsds",
                    "/pythonzero",
                    "/clickhouse",
                    "/datavisualization",
                    "/superset",
                    "/excel-google",
                    "/big-data",
                    "/career/guide",
                    "/dsintens",
                ]
            )
            and "?" not in href
        ),
        "max_scrolls": 10,
        "goto_timeout": 60000,
        "wait_until": "load",
    },
}


def _normalize_url(url: str, base: str) -> str:
    absolute = urljoin(base, url)
    parsed = urlparse(absolute)
    cleaned = parsed._replace(fragment="", query="").geturl()
    return cleaned.rstrip("/")


def _collect_links(
    start_urls: list[str],
    wait_selector: str,
    link_filter,
    max_scrolls: int,
    goto_timeout: int = 60000,
    wait_until: str = "networkidle",
) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright не установлен. Выполни:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    collected: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        for start_url in start_urls:
            page = context.new_page()
            base_domain = urlparse(start_url).netloc
            print(f"\n🔍 Собираю ссылки с {start_url} ...")

            try:
                page.goto(
                    start_url,
                    wait_until=wait_until,
                    timeout=goto_timeout,
                )
                page.wait_for_timeout(3000)

                for scroll in range(max_scrolls):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(1500)

                    links = page.evaluate(
                        """() => {
                            const anchors = document.querySelectorAll('a[href]');
                            return Array.from(anchors).map(a => a.href);
                        }"""
                    )

                    new_found = 0
                    for link in links:
                        normalized = _normalize_url(link, start_url)
                        if link_filter(normalized) and urlparse(normalized).netloc == base_domain:
                            if normalized not in collected:
                                collected.add(normalized)
                                new_found += 1

                    if new_found:
                        print(f"  Скролл {scroll + 1}/{max_scrolls}: +{new_found} новых ссылок (всего: {len(collected)})")

                    if scroll > 5 and new_found == 0:
                        print(f"  Новых ссылок нет, остановка на скролле {scroll + 1}")
                        break

            except Exception as e:
                print(f"  ⚠️ Ошибка при сборе с {start_url}: {e}")
            finally:
                page.close()

        browser.close()

    result = sorted(collected)
    print(f"\n  ✅ Всего собрано: {len(result)} уникальных URL'ов")
    return result


def _save_seeds(platform_name: str, urls: list[str]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    file_path = OUTPUT_DIR / f"{platform_name}_seeds.txt"
    print(f"  📝 Сохраняю {len(urls)} URL'ов в {file_path}")

    file_path.write_text("\n".join(urls), encoding="utf-8")
    print(f"  ✅ Файл создан: {file_path.exists()}")

    json_path = OUTPUT_DIR / f"{platform_name}_seeds.json"
    json_path.write_text(
        json.dumps(
            {"platform": platform_name, "count": len(urls), "urls": urls},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return file_path


def main() -> None:
    print("=" * 60)
    print("Market Agent Seed Collector")
    print("Одноразовый сбор URL'ов курсов с JS-платформ")
    print("=" * 60)

    print(f"📁 OUTPUT_DIR: {OUTPUT_DIR}")

    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, Any]] = {}

    for platform_name, config in TARGETS.items():
        try:
            urls = _collect_links(
                start_urls=config["start_urls"],
                wait_selector=config["wait_selector"],
                link_filter=config["link_filter"],
                max_scrolls=config["max_scrolls"],
                goto_timeout=config.get("goto_timeout", 60000),
                wait_until=config.get("wait_until", "networkidle"),
            )

            if urls:
                file_path = _save_seeds(platform_name, urls)
                results[platform_name] = {
                    "count": len(urls),
                    "file": str(file_path),
                    "sample": urls[:5],
                }
            else:
                print(f"  ⚠️ Нет URL'ов для сохранения ({platform_name})")
                results[platform_name] = {
                    "count": 0,
                    "file": "",
                    "sample": [],
                }

        except ImportError as e:
            print(f"\n❌ {e}")
            return
        except Exception as e:
            print(f"\n❌ Ошибка для {platform_name}: {e}")
            results[platform_name] = {"count": 0, "file": "", "error": str(e)}

    print("\n" + "=" * 60)
    print("Результаты сбора:")
    print("=" * 60)

    for platform, info in results.items():
        print(f"\n{platform}:")
        print(f"  URL'ов собрано: {info.get('count', 0)}")
        if info.get("file"):
            print(f"  Сохранено в: {info['file']}")
        if info.get("error"):
            print(f"  Ошибка: {info['error']}")

    print(f"\n📁 Файлы в: {OUTPUT_DIR}")
    print("Добавь эти URL'ы в pipeline.py как *_EXTRA_SEEDS")


if __name__ == "__main__":
    main()