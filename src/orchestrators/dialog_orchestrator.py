"""Диалоговый оркестратор — retrieval из RAG + LLM-ответ (Ollama).

Режим: командная строка.

Запуск:
    python src/orchestrators/dialog_orchestrator.py

Требуется:
    ollama pull qwen2.5:7b

Команды:
    вопрос       — поиск в RAG + LLM-ответ
    /stats       — статистика RAG
    /sources     — источники в RAG
    /news [N]    — новые поступления за N дней (по умолчанию 3)
    /help        — справка
    /exit        — выход
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.common.rag_store import RAGStore

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

LLM_MODEL = "qwen2.5:7b"
MIN_SEARCH_SCORE = 0.2


# ---------------------------------------------------------------------------
# LLM-клиент (Ollama)
# ---------------------------------------------------------------------------

def _ask_llm(system_prompt: str, user_message: str) -> str:
    import ollama

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        options={"temperature": 0.3, "num_predict": 500},
    )
    return response["message"]["content"].strip()


def _translate_to_russian(text: str) -> str:
    response = _ask_llm(
        "Ты — переводчик. Переведи текст на русский язык. Сохрани технические термины на английском. "
        "Отвечай ТОЛЬКО переводом, без пояснений.",
        text,
    )
    return response


# ---------------------------------------------------------------------------
# Диалоговый цикл
# ---------------------------------------------------------------------------

def run_dialog() -> None:
    print("=" * 60)
    print("ДИАЛОГОВАЯ СИСТЕМА ПОДДЕРЖКИ РЕШЕНИЙ")
    print("=" * 60)
    print(f"LLM: {LLM_MODEL} (локально)")
    print("Задайте вопрос по рынку AI, компетенциям, трендам.")
    print("/stats   — статистика RAG")
    print("/sources — источники в RAG")
    print("/news [N]— новые поступления за N дней")
    print("/help    — справка")
    print("/exit    — выход")
    print()

    store = RAGStore()

    print(f"[dialog] RAG: {store.count} чанков")
    print()

    while True:
        try:
            query = input("🔍 Вопрос > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if not query:
            continue

        if query == "/exit":
            print("До свидания!")
            break

        if query == "/help":
            print("Команды:")
            print("  вопрос       — поиск в RAG + LLM-ответ")
            print("  /stats       — статистика RAG")
            print("  /sources     — источники в RAG")
            print("  /news [N]    — новые поступления за N дней (по умолчанию 3)")
            print("  /help        — справка")
            print("  /exit        — выход")
            print()
            continue

        if query == "/stats":
            print(f"Всего чанков в RAG: {store.count}")
            print()
            continue

        if query == "/sources":
            if store.count == 0:
                print("RAG пуст.")
            else:
                results = store.collection.get()
                sources = set(m.get("source", "?") for m in results.get("metadatas", []))
                for s in sorted(sources):
                    count = sum(1 for m in results.get("metadatas", []) if m.get("source") == s)
                    print(f"  {s}: {count} чанков")
            print()
            continue

        if query.startswith("/news"):
            parts = query.split()
            days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
            _show_news(store, days)
            print()
            continue

        # ---- поиск ----
        results = store.search(query, top_k=8)

        # Фильтруем и дедуплицируем по названию источника
        relevant: list[dict] = []
        seen_titles: set[str] = set()
        for r in results:
            if r["score"] < MIN_SEARCH_SCORE:
                continue
            title_key = r["title"][:80].lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            relevant.append(r)

        if not relevant:
            print("❌ Ничего релевантного не найдено.")
            print("Попробуйте переформулировать запрос или /news для просмотра новых поступлений.\n")
            continue

        # Формируем контекст для LLM
        context_parts = []
        for i, r in enumerate(relevant):
            text = r["text"]
            if _is_english(text[:200]):
                try:
                    text = _translate_to_russian(text[:800])
                except Exception:
                    pass

            context_parts.append(f"[{i+1}] Источник: {r['source']}\n{text}")

        context = "\n\n".join(context_parts)

        # LLM-ответ
        try:
            answer = _ask_llm(
                "Ты — AI-ассистент руководителя IT-компании. Отвечай на русском языке, "
                "кратко и по делу. Используй ТОЛЬКО информацию из контекста. "
                "Если в контексте нет ответа — скажи об этом.\n\n"
                f"Контекст:\n{context}",
                query,
            )
            print(f"\n📝 {answer}\n")

            print("--- Источники ---")
            for r in relevant:
                print(f"  [{r['source']}] {r['title'][:100]}")
            print()

        except Exception as e:
            print(f"\n⚠️ Ошибка LLM: {e}")
            print("Результаты поиска (без генерации):\n")
            for r in relevant:
                print(f"📄 [{r['source']}] {r['title'][:100]}")
                print(f"   {r['text'][:300]}...")
                print(f"   score: {r['score']:.3f}\n")

    print(f"\nСессия завершена. RAG: {store.count} чанков.")


# ---------------------------------------------------------------------------
# Команда /news
# ---------------------------------------------------------------------------

def _show_news(store: RAGStore, days: int = 3) -> None:
    if store.count == 0:
        print("RAG пуст.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    all_data = store.collection.get()
    metadatas = all_data.get("metadatas", [])
    documents = all_data.get("documents", [])

    found = 0
    print(f"\n📰 Новые поступления за последние {days} дн.:")
    print("-" * 60)

    seen_titles = set()
    for i, meta in enumerate(metadatas):
        indexed_at = meta.get("indexed_at", "")
        if indexed_at:
            try:
                if datetime.fromisoformat(indexed_at) < cutoff:
                    continue
            except ValueError:
                continue

        title = meta.get("title", "Без названия")[:100]
        title_key = title.lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        found += 1
        source = meta.get("source", "?")
        print(f"[{source}] {title}")
        if indexed_at:
            print(f"         Дата: {indexed_at[:10]}")
        print()

    if found == 0:
        print("Новых поступлений за указанный период нет.")
    else:
        print(f"Всего: {found} уникальных статей")


# ---------------------------------------------------------------------------
def _is_english(text: str) -> bool:
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    cyrillic = sum(1 for c in text if 'а' <= c <= 'я' or 'А' <= c <= 'Я')
    return latin > cyrillic * 3


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_dialog()