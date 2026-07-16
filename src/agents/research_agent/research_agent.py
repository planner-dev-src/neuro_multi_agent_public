"""research_agent — свободный поиск и наполнение RAG.

Режимы:
- search: поиск по запросу → результаты → сохранение в RAG
- crawl: загрузка страницы → извлечение текста → чанки → RAG
- search_and_report: поиск по запросу → формирование отчёта
- run_background_collection: фоновый сбор для наполнения RAG

Использует:
- DuckDuckGo Search (бесплатно, без API-ключа)
- requests + BeautifulSoup (краулинг)
- sentence-transformers + ChromaDB (RAG)

Пример:
    agent = ResearchAgent()
    results = agent.research("тренды AI в корпоративном секторе 2026")
"""

from __future__ import annotations

import hashlib
import time
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse
from datetime import datetime


class ResearchAgent:
    """Агент свободного поиска и наполнения knowledge base."""

    def __init__(self, rag_store=None) -> None:
        if rag_store is None:
            from src.common.rag_store import RAGStore
            self._store = RAGStore()
        else:
            self._store = rag_store
        
        # Кэш для нормализации URL
        self._url_cache: dict[str, str] = {}
        
        # Папка для отчётов
        self._reports_dir = Path("data/reports/research")
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Вспомогательные методы
    # -----------------------------------------------------------------------

    def _normalize_url(self, url: str) -> str:
        """Нормализует URL (убирает UTM-метки, фрагменты, нормализует регистр)."""
        parsed = urlparse(url)
        
        # Убираем UTM-параметры и другие отслеживающие
        query_params = []
        if parsed.query:
            for param in parsed.query.split('&'):
                if not any(param.lower().startswith(f'{k}=') for k in ['utm_', 'fb_', 'ref_']):
                    query_params.append(param)
        
        # Нормализуем путь (убираем trailing slash)
        path = parsed.path.rstrip('/') or '/'
        
        # Собираем заново (без фрагментов)
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            '',  # params устарели
            '&'.join(sorted(query_params)) if query_params else '',
            ''   # fragment убираем
        ))
        
        # Кэшируем
        if url not in self._url_cache:
            self._url_cache[url] = normalized
        
        return self._url_cache[url]

    def _generate_chunk_id(self, source: str, section: str, url: str, index: int) -> str:
        """Генерирует уникальный ID для чанка на основе содержимого."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{source}::{section}::{url_hash}_{index}"

    def _is_text_meaningful(self, text: str, min_words: int = 50) -> bool:
        """Проверяет, содержит ли текст достаточное количество слов."""
        words = text.split()
        return len(words) >= min_words

    def _clean_extracted_text(self, text: str) -> str:
        """
        Очищает текст от навигационных элементов, меню, кнопок и другого мусора.
        """
        if not text:
            return text
        
        # Паттерны для удаления навигационных и служебных элементов
        nav_patterns = [
            # vc.ru навигация
            r'Популярное\s*Свежее\s*Моя лента',
            r'Сообщения\s*Рейтинг\s*Курсы',
            r'Маркет\s*eSIM для поездок',
            r'Викторина\s*Темы\s*AI',
            r'Сервисы\s*Маркетинг\s*Личный опыт',
            r'Деньги\s*Разработка\s*Инвестиции',
            r'Путешествия\s*Карьера\s*Приёмная',
            r'Показать все\s*vc\.ru',
            r'vc\.ru\s*О проекте\s*Правила',
            r'Реклама\s*Приложения\s*Системная тема',
            r'Мы используем\s*рекомендации\.',
            r'Alpina Digital\s*Образование',
            r'\d+\s*мин\.?\s*чтения',
            r'мин\.?\s*чтения',
            r'Подробнее\s*→',
            r'Читать далее\s*→',
            
            # Общие навигационные элементы
            r'Наверх\s*Светлый\s*Темный',
            r'Светлый\s*Темный',
            r'Подпишитесь на нас',
            r'Перейти к контенту',
            r'Назад\s*Статьи',
            r'Автор\s*\w+\s*\w+',
            r'Опубликованный\s*\d+\.\d+\.\d+',
            r'\d+\s*комментари[яй]',
            r'Присоединяйтесь к разговору',
            r'ВКУРСЕ\s*0%',
            r'0%\s*Наверх',
            r'1 из \d+',
            r'для экспертов и бизнеса',
            r'Всего \d+ мест, осталось \d+',
            
            # Англоязычные навигационные элементы
            r'Popular\s*Latest\s*My feed',
            r'Messages\s*Rating\s*Courses',
            r'Market\s*eSIM for travel',
            r'Quiz\s*Topics\s*AI',
            r'Services\s*Marketing\s*Personal experience',
            r'Money\s*Development\s*Investments',
            r'Travel\s*Career\s*Reception',
            r'About\s*Rules\s*Advertising',
            r'Apps\s*System theme',
            r'We use\s*recommendations',
            r'Back to top\s*Light\s*Dark',
            r'Subscribe to us',
            r'Skip to content',
            r'Back\s*Articles',
            r'Author\s*\w+\s*\w+',
            r'Published\s*\d+\.\d+\.\d+',
            r'\d+\s*comments',
            r'Join the conversation',
        ]
        
        for pattern in nav_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Удаляем строки, которые являются приглашениями или рекламой
        invite_patterns = [
            r'Приглашаю всех желающих на мой живой мастер-класс',
            r'Тема: Эстетика нейро-фото и AI-аватар эксперта',
            r'запись будет доступна на геткурс',
        ]
        for pattern in invite_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Удаляем строки, состоящие только из одного слова или короткой фразы-маркера
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Пропускаем строки, состоящие только из одного слова
            if len(line.split()) <= 2 and len(line) < 30:
                # Но сохраняем, если это выглядит как заголовок
                if not (line[0].isupper() and len(line) > 15):
                    continue
            
            # Пропускаем строки, которые выглядят как кнопки или ссылки
            if line in ['Подробнее', 'Читать далее', 'Узнать больше', 'Наверх', 'Назад', 'ВКУРСЕ']:
                continue
            
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # Удаляем повторяющиеся пробелы и пустые строки
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' +', ' ', result)
        
        return result.strip()

    def _fix_encoding(self, content: bytes, response) -> str:
        """Определяет и исправляет кодировку содержимого."""
        try:
            # Сначала пробуем кодировку из заголовка
            if response.encoding:
                return content.decode(response.encoding)
            
            # Пробуем определить через chardet
            try:
                import chardet
                detected = chardet.detect(content)
                if detected and detected.get('encoding'):
                    return content.decode(detected['encoding'])
            except ImportError:
                pass
            
            # Пробуем UTF-8
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                pass
            
            # Пробуем Windows-1251 (русские сайты)
            try:
                return content.decode('windows-1251')
            except UnicodeDecodeError:
                pass
            
            # Пробуем CP866
            try:
                return content.decode('cp866')
            except UnicodeDecodeError:
                pass
            
            # Если ничего не помогло, используем замену
            return content.decode('utf-8', errors='replace')
            
        except Exception:
            return response.text

    # -----------------------------------------------------------------------
    # Поиск
    # -----------------------------------------------------------------------

    def search_web(self, query: str, max_results: int = 10, region: str = "wt-wt") -> list[dict[str, str]]:
        """Поиск в интернете через DuckDuckGo."""
        try:
            from ddgs import DDGS
            print("[research] Использую ddgs (новый пакет)")
        except ImportError:
            try:
                from duckduckgo_search import DDGS
                print("[research] Использую duckduckgo_search (старый пакет)")
            except ImportError:
                raise ImportError(
                    "Требуется DuckDuckGo Search. Выполни:\n"
                    "  pip install ddgs\n"
                    "или\n"
                    "  pip install duckduckgo-search"
                )

        print(f"[research] Поиск: '{query}'...")
        results: list[dict[str, str]] = []

        try:
            with DDGS() as ddgs:
                for item in ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                ):
                    url = item.get("href", "")
                    normalized_url = self._normalize_url(url)
                    
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": url,
                            "normalized_url": normalized_url,
                            "snippet": item.get("body", ""),
                        }
                    )
        except Exception as e:
            print(f"[research] Ошибка поиска DuckDuckGo: {e}")
            return []

        # Удаляем дубликаты по нормализованному URL
        seen_urls = set()
        unique_results = []
        for r in results:
            if r["normalized_url"] not in seen_urls:
                seen_urls.add(r["normalized_url"])
                unique_results.append(r)

        print(f"[research] Найдено результатов: {len(unique_results)} (уникальных)")
        return unique_results

    # -----------------------------------------------------------------------
    # Краулинг страницы
    # -----------------------------------------------------------------------

    def crawl_page(self, url: str) -> dict[str, Any]:
        """Загружает страницу и извлекает текст с корректной обработкой кодировки."""
        import requests
        from bs4 import BeautifulSoup

        print(f"[research] Загрузка: {url}...")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Исправляем кодировку
            html = self._fix_encoding(response.content, response)
            
        except Exception as e:
            print(f"[research] Ошибка загрузки {url}: {e}")
            return {"url": url, "title": "", "text": "", "html": "", "error": str(e)}

        soup = BeautifulSoup(html, "html.parser")

        # Удаляем скрипты, стили, навигацию, футеры, хедеры, aside
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)

        # Очищаем текст от мусора
        text = self._clean_extracted_text(text)

        return {
            "url": url,
            "normalized_url": self._normalize_url(url),
            "title": title,
            "text": text,
            "html": html,
        }

    # -----------------------------------------------------------------------
    # Разбивка на чанки
    # -----------------------------------------------------------------------

    def chunk_text(
        self,
        text: str,
        source: str = "research",
        section: str = "web",
        url: str = "",
        title: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        min_chunk_words: int = 30,
    ) -> list[dict[str, Any]]:
        """Разбивает текст на чанки фиксированного размера."""
        if not text:
            return []

        if not self._is_text_meaningful(text, min_words=min_chunk_words):
            return []

        words = text.split()
        chunks: list[dict[str, Any]] = []

        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_text = " ".join(words[i:i + chunk_size])
            if not chunk_text:
                continue

            if len(chunk_text.split()) < min_chunk_words:
                continue

            chunks.append(
                {
                    "chunk_id": self._generate_chunk_id(source, section, url or title, i),
                    "text": chunk_text,
                    "source": source,
                    "section": section,
                    "title": title,
                    "url": url,
                    "metadata": {
                        "chunk_index": len(chunks),
                        "source_url": url or title,
                        "word_count": len(chunk_text.split()),
                        "char_count": len(chunk_text),
                    },
                }
            )

        return chunks

    # -----------------------------------------------------------------------
    # Основной метод — исследование (для оркестратора)
    # -----------------------------------------------------------------------

    def research(
        self,
        query: str,
        max_search_results: int = 5,
        max_crawl_pages: int = 3,
        chunk_size: int = 500,
        min_text_words: int = 50,
        skip_crawl_errors: bool = True,
    ) -> dict[str, Any]:
        """Выполняет полный цикл исследования по запросу."""
        print(f"\n{'='*60}")
        print(f"[research] ИССЛЕДОВАНИЕ: '{query}'")
        print(f"{'='*60}")
        
        start_time = time.time()

        search_results = self.search_web(query, max_results=max_search_results)

        if not search_results:
            return {
                "query": query,
                "search_results": [],
                "crawled_pages": [],
                "chunks_count": 0,
                "indexed_count": 0,
                "execution_time": time.time() - start_time,
            }

        crawled: list[dict[str, Any]] = []
        all_chunks: list[dict[str, Any]] = []
        seen_normalized_urls = set()

        for result in search_results[:max_crawl_pages]:
            norm_url = result.get("normalized_url", result["url"])
            if norm_url in seen_normalized_urls:
                continue
            seen_normalized_urls.add(norm_url)

            page = self.crawl_page(result["url"])

            if page.get("error"):
                if skip_crawl_errors:
                    continue
                else:
                    crawled.append(page)
                    continue

            if not self._is_text_meaningful(page["text"], min_words=min_text_words):
                continue

            crawled.append(page)

            chunks = self.chunk_text(
                page["text"],
                source="research",
                section="web",
                url=page["url"],
                title=page["title"],
                chunk_size=chunk_size,
                min_chunk_words=30,
            )
            all_chunks.extend(chunks)

        indexed = 0
        if all_chunks:
            try:
                indexed = self._store.index_chunks(all_chunks)
            except Exception as e:
                print(f"[research] Ошибка при индексации в RAG: {e}")

        execution_time = time.time() - start_time

        return {
            "query": query,
            "search_results": search_results,
            "crawled_pages": crawled,
            "chunks_count": len(all_chunks),
            "indexed_count": indexed,
            "execution_time": execution_time,
        }

    # -----------------------------------------------------------------------
    # НОВЫЙ МЕТОД: поиск и формирование отчёта (по запросу руководителя)
    # -----------------------------------------------------------------------

    def search_and_report(
        self,
        query: str,
        max_results: int = 10,
        max_crawl_pages: int = 5,
        generate_report: bool = True,
        save_report: bool = True,
    ) -> dict[str, Any]:
        """
        Выполняет поиск по запросу и формирует исследовательский отчёт.
        """
        print(f"\n{'='*60}")
        print(f"[research] ПОИСК И ОТЧЁТ ПО ЗАПРОСУ: '{query}'")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        search_results = self.search_web(query, max_results=max_results)
        
        if not search_results:
            return {
                "query": query,
                "report": f"По запросу '{query}' ничего не найдено.",
                "sources": [],
                "rag_chunks": [],
                "execution_time": time.time() - start_time,
                "status": "no_results"
            }
        
        crawled_pages = []
        rag_chunks = []
        
        for result in search_results[:max_crawl_pages]:
            page = self.crawl_page(result["url"])
            if page.get("error"):
                continue
            
            if self._is_text_meaningful(page["text"], min_words=50):
                crawled_pages.append(page)
                
                chunks = self.chunk_text(
                    page["text"],
                    source="research_report",
                    section="web",
                    url=page["url"],
                    title=page["title"],
                )
                rag_chunks.extend(chunks)
        
        if rag_chunks:
            try:
                self._store.index_chunks(rag_chunks)
            except Exception as e:
                print(f"[research] Ошибка индексации: {e}")
        
        report = ""
        if generate_report:
            report = self._generate_research_report(query, search_results, crawled_pages)
        
        report_path = None
        if save_report and report:
            report_path = self._save_research_report(query, report, search_results)
        
        execution_time = time.time() - start_time
        
        return {
            "query": query,
            "report": report,
            "report_path": report_path,
            "sources": search_results,
            "crawled_pages": crawled_pages,
            "rag_chunks": rag_chunks,
            "sources_count": len(search_results),
            "crawled_count": len(crawled_pages),
            "chunks_count": len(rag_chunks),
            "execution_time": execution_time,
            "status": "completed"
        }

    def _generate_research_report(
        self,
        query: str,
        search_results: list,
        crawled_pages: list
    ) -> str:
        """Генерирует текстовый исследовательский отчёт."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"ИССЛЕДОВАТЕЛЬСКИЙ ОТЧЁТ")
        lines.append("=" * 70)
        lines.append(f"Запрос: {query}")
        lines.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Найдено источников: {len(search_results)}")
        lines.append(f"Обработано страниц: {len(crawled_pages)}")
        lines.append("=" * 70)
        lines.append("")
        
        if not search_results:
            lines.append("Результатов не найдено.")
            return "\n".join(lines)
        
        lines.append("📚 ИСТОЧНИКИ:")
        lines.append("-" * 70)
        for i, r in enumerate(search_results, 1):
            lines.append(f"{i}. {r.get('title', 'Без названия')}")
            lines.append(f"   URL: {r.get('url', '')}")
            if r.get('snippet'):
                lines.append(f"   Сниппет: {r['snippet'][:200]}...")
            lines.append("")
        
        if crawled_pages:
            lines.append("📄 ВЫДЕРЖКИ ИЗ ПРОАНАЛИЗИРОВАННЫХ СТРАНИЦ:")
            lines.append("-" * 70)
            for page in crawled_pages[:3]:
                lines.append(f"\n🔹 {page.get('title', 'Без названия')}")
                lines.append(f"   URL: {page.get('url', '')}")
                text = page.get('text', '')[:500]
                if text:
                    lines.append(f"   Текст: {text}...")
                lines.append("")
        
        lines.append("=" * 70)
        lines.append("КОНЕЦ ОТЧЁТА")
        lines.append("=" * 70)
        
        return "\n".join(lines)

    def _save_research_report(self, query: str, report: str, search_results: list) -> Path:
        """Сохраняет исследовательский отчёт в файл."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c for c in query if c.isalnum() or c in " _-")[:30]
        filename = self._reports_dir / f"research_{safe_query}_{timestamp}.txt"
        
        filename.write_text(report, encoding='utf-8')
        print(f"[research] Отчёт сохранён: {filename}")
        
        json_filename = self._reports_dir / f"research_{safe_query}_{timestamp}.json"
        json_data = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "sources_count": len(search_results),
            "sources": search_results,
            "report": report
        }
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        return filename

    # -----------------------------------------------------------------------
    # НОВЫЙ МЕТОД: фоновый сбор (для демона)
    # -----------------------------------------------------------------------

    def run_background_collection(
        self,
        sources: list[dict] = None,
        max_items: int = 5,
    ) -> dict[str, Any]:
        """
        Выполняет фоновый сбор данных для наполнения RAG.
        """
        print(f"\n{'='*60}")
        print("[research] ФОНОВЫЙ СБОР ДАННЫХ")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        if sources is None:
            sources = [
                {"name": "arxiv", "query": "artificial intelligence OR machine learning", "max": 3},
                {"name": "github", "query": "machine-learning", "max": 3},
                {"name": "news", "query": "AI trends 2026", "max": 3},
            ]
        
        all_chunks = []
        processed_count = 0
        
        for source in sources:
            try:
                source_name = source.get("name", "unknown")
                query = source.get("query", "")
                max_results = source.get("max", max_items)
                
                print(f"[research] Сбор из источника: {source_name} (запрос: '{query}')")
                
                results = self.search_web(query, max_results=max_results)
                
                if not results:
                    print(f"[research]   Нет результатов для {source_name}")
                    continue
                
                for result in results[:max_results]:
                    page = self.crawl_page(result["url"])
                    if page.get("error"):
                        continue
                    
                    if self._is_text_meaningful(page["text"], min_words=50):
                        chunks = self.chunk_text(
                            page["text"],
                            source=f"background_{source_name}",
                            section="background",
                            url=page["url"],
                            title=page["title"],
                        )
                        all_chunks.extend(chunks)
                        processed_count += 1
                
                print(f"[research]   Обработано: {processed_count} страниц, {len(all_chunks)} чанков")
                
            except Exception as e:
                print(f"[research]   Ошибка сбора из {source.get('name', 'unknown')}: {e}")
        
        indexed = 0
        if all_chunks:
            try:
                indexed = self._store.index_chunks(all_chunks)
                print(f"[research] Индексировано {indexed} чанков в RAG")
            except Exception as e:
                print(f"[research] Ошибка индексации: {e}")
        
        execution_time = time.time() - start_time
        
        return {
            "status": "completed",
            "rag_chunks": all_chunks,
            "indexed_count": indexed,
            "sources_processed": processed_count,
            "chunks_count": len(all_chunks),
            "execution_time": execution_time,
        }

    # -----------------------------------------------------------------------
    # НОВЫЙ МЕТОД: получение статуса
    # -----------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус research_agent."""
        return {
            "agent": "research_agent",
            "rag_count": self._store.count if hasattr(self._store, 'count') else 0,
            "reports_dir": str(self._reports_dir),
            "ready": True,
            "timestamp": datetime.now().isoformat()
        }


# ---------------------------------------------------------------------------
# Точка входа для тестирования
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agent = ResearchAgent()
    
    print("\n" + "=" * 70)
    print("ТЕСТ RESEARCH AGENT")
    print("=" * 70)
    
    print("\n[1] Тест search_and_report...")
    result = agent.search_and_report(
        query="тренды AI в образовании 2026",
        max_results=3,
        max_crawl_pages=2,
        generate_report=True
    )
    print(f"  Статус: {result.get('status')}")
    print(f"  Источников: {result.get('sources_count', 0)}")
    print(f"  Чанков: {result.get('chunks_count', 0)}")
    if result.get('report_path'):
        print(f"  Отчёт: {result['report_path']}")
    
    print("\n[2] Тест run_background_collection...")
    bg_result = agent.run_background_collection(max_items=2)
    print(f"  Статус: {bg_result.get('status')}")
    print(f"  Источников обработано: {bg_result.get('sources_processed', 0)}")
    print(f"  Чанков: {bg_result.get('chunks_count', 0)}")
    print(f"  Индексировано: {bg_result.get('indexed_count', 0)}")
    
    print("\n[3] Тест get_status...")
    status = agent.get_status()
    print(f"  RAG: {status.get('rag_count', 0)} чанков")
    print(f"  Папка отчётов: {status.get('reports_dir', '')}")
    
    print("\n" + "=" * 70)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 70)