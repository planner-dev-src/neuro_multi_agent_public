"""secretary_agent — фиксация и анализ совещаний руководителя.

Режимы:
- record: запись с микрофона + транскрибация + LLM-анализ
- transcribe: транскрибация аудио/видео + LLM-анализ
- load: загрузка готовой выжимки (sample_meeting_output.json)

Поддерживаемые LLM-провайдеры:
- Groq (рекомендуемый, бесплатный тир) — GROQ_API_KEY
- DeepSeek — DEEPSEEK_API_KEY
- OpenAI — OPENAI_API_KEY
- Любой совместимый — LLM_BASE_URL + LLM_API_KEY + LLM_MODEL

Ключи задаются в .env файле в корне проекта.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Загружаем .env из корня проекта
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
        print(f"[secretary] .env загружен из {_ENV_PATH}")
except ImportError:
    pass

from src.agents.planner_agent.metrics_schema import StrategyInput
from src.agents.planner_agent.planner_types import RAGChunk


# ---------------------------------------------------------------------------
# Транскрибация
# ---------------------------------------------------------------------------

def transcribe_file(
    file_path: str,
    model_size: str = "base",
    language: str = "ru",
) -> dict[str, Any]:
    """Транскрибация аудио- или видеофайла через whisper."""
    try:
        import whisper
    except ImportError:
        raise ImportError("Whisper не установлен. Выполни: pip install openai-whisper")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    video_extensions = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv", ".wmv"}
    is_video = path.suffix.lower() in video_extensions

    audio_path = file_path
    tmp_audio: Path | None = None
    source_type = "audio"

    if is_video:
        try:
            import ffmpeg
        except ImportError:
            raise ImportError("Для видео требуется: pip install ffmpeg-python")

        tmp_audio = path.parent / f"_tmp_{path.stem}.wav"
        source_type = "video"

        print(f"[secretary] Извлечение аудиодорожки: {path.name}...")
        try:
            ffmpeg.input(str(path)).output(
                str(tmp_audio), acodec="pcm_s16le", ac=1, ar="16000"
            ).run(overwrite_output=True, quiet=True)
            audio_path = str(tmp_audio)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode() if e.stderr else str(e)
            raise RuntimeError(f"Ошибка ffmpeg: {stderr}")

    try:
        print(f"[secretary] Загрузка whisper/{model_size}...")
        model = whisper.load_model(model_size)
        print(f"[secretary] Транскрибация {path.name}...")
        result = model.transcribe(audio_path, language=language)

        return {
            "text": result["text"],
            "segments": [
                {"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
                for s in result.get("segments", [])
            ],
            "language": result.get("language", language),
            "source_type": source_type,
            "original_file": str(path),
        }
    finally:
        if tmp_audio and tmp_audio.exists():
            tmp_audio.unlink(missing_ok=True)


def record_and_transcribe(
    duration: int = 60,
    sample_rate: int = 16000,
    model_size: str = "base",
    language: str = "ru",
) -> dict[str, Any]:
    """Запись с микрофона и транскрибация."""
    try:
        import numpy as np
        import scipy.io.wavfile as wavfile
        import sounddevice as sd
    except ImportError:
        raise ImportError("Требуются: pip install openai-whisper sounddevice scipy numpy")

    print(f"[secretary] Запись ({duration} сек, {sample_rate} Hz)...")
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16)
    sd.wait()
    print("[secretary] Запись завершена.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wavfile.write(tmp.name, sample_rate, recording)
        tmp_path = tmp.name

    try:
        result = transcribe_file(tmp_path, model_size=model_size, language=language)
        result["duration_seconds"] = duration
        result["sample_rate"] = sample_rate
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# LLM-анализ
# ---------------------------------------------------------------------------

_LLM_ANALYSIS_PROMPT = """Проанализируй транскрипт совещания руководителя AI-компании. Выдели структурированную информацию в JSON-формате.

Правила:
1. meeting_date — сегодняшняя дата в формате YYYY-MM-DD
2. participants — список участников
3. transcript_summary — 2-4 предложения на русском
4. key_decisions — список ключевых решений (максимум 5)
5. assigned_tasks — поручения: task, responsible, deadline
6. priority_directions — приоритетные направления ИЗ ТОЛЬКО ЭТОГО СПИСКА:
   classical_ml, nlp, computer_vision, time_series, reinforcement_learning,
   speech_audio, gan, genetic_algorithms, ai_project_management_custom_sales,
   production_integration, llm_agents, automl, data_engineering,
   backend_development, frontend_development, fullstack_development,
   devops_sre, qa_engineering, cybersecurity, product_analytics, product_management_it
7. search_queries — 3-5 поисковых запросов
8. risks — 2-3 риска
9. kpi_targets: revenue_growth (доля), headcount_growth (доля), new_products (целое)

Ответ — ТОЛЬКО валидный JSON, без пояснений.

Транскрипт:
{transcript}"""


def _resolve_llm_client() -> tuple[Any, str]:
    """Находит доступного LLM-провайдера по переменным окружения."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Требуется openai: pip install openai")

    # 1. Явные переменные
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL")

    if base_url and api_key:
        print(f"[secretary] Использую LLM: {base_url} ({model or 'default'})")
        return OpenAI(api_key=api_key, base_url=base_url), model or "default"

    # 2. Groq (рекомендуемый, бесплатный тир)
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        print(f"[secretary] Использую Groq: {model}")
        return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1"), model

    # 3. DeepSeek
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        model = model or "deepseek-chat"
        print(f"[secretary] Использую DeepSeek: {model}")
        return OpenAI(api_key=api_key, base_url="https://api.deepseek.com"), model

    # 4. OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        model = model or "gpt-4o-mini"
        print(f"[secretary] Использую OpenAI: {model}")
        return OpenAI(api_key=api_key), model

    raise RuntimeError(
        "LLM не настроен. Создай .env файл с одним из ключей:\n"
        "  GROQ_API_KEY=...      (рекомендуемый, бесплатный)\n"
        "  DEEPSEEK_API_KEY=...\n"
        "  OPENAI_API_KEY=...\n"
        "  LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=..."
    )


def _llm_analyze_transcript(transcript_text: str) -> dict[str, Any]:
    """Отправляет транскрипт в LLM, получает структурированный анализ."""
    client, model = _resolve_llm_client()

    print(f"[secretary] LLM-анализ транскрипта...")

    # Groq не поддерживает response_format={"type": "json_object"},
    # поэтому запрашиваем JSON в промпте
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Ты — аналитик совещаний. Отвечай ТОЛЬКО валидным JSON, без пояснений и маркеров ```.",
            },
            {"role": "user", "content": _LLM_ANALYSIS_PROMPT.format(transcript=transcript_text[:15000])},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    # Убираем возможные ```json ... ``` если модель их добавила
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def _fallback_analyze_transcript(transcript_text: str) -> dict[str, Any]:
    """Запасной анализатор — базовые эвристики."""
    print("[secretary] LLM недоступен, использую эвристики...")
    text_lower = transcript_text.lower()

    topic_keywords = {
        "llm_agents": ["llm", "agent", "langchain", "rag"],
        "nlp": ["nlp", "natural language", "обработка языка"],
        "classical_ml": ["machine learning", "машинное обучение", "ml"],
        "computer_vision": ["computer vision", "компьютерное зрение"],
        "production_integration": ["mlops", "production", "продакшн"],
        "reinforcement_learning": ["reinforcement", "подкрепление"],
        "gan": ["gan", "генеративно-состязательны"],
        "genetic_algorithms": ["genetic algorithm", "генетически"],
        "data_engineering": ["data engineer", "инженер данных"],
        "devops_sre": ["devops", "sre", "инфраструктур"],
        "cybersecurity": ["кибербезопасност", "security"],
    }

    found_topics = [t for t, kw in topic_keywords.items() if any(k in text_lower for k in kw)]

    return {
        "meeting_date": "2026-07-07",
        "participants": ["Руководитель"],
        "transcript_summary": transcript_text[:300] + "...",
        "key_decisions": ["Требуется LLM-анализ"],
        "assigned_tasks": [{"task": "Требуется LLM-анализ", "responsible": "TBD", "deadline": "TBD"}],
        "priority_directions": found_topics or ["llm_agents", "nlp"],
        "search_queries": ["тренды AI 2026"],
        "risks": ["Требуется LLM-анализ"],
        "kpi_targets": {"revenue_growth": 0.15, "headcount_growth": 0.10, "new_products": 1},
    }


# ---------------------------------------------------------------------------
# Модель результата
# ---------------------------------------------------------------------------

class MeetingOutput:
    def __init__(
        self,
        meeting_date: str = "",
        participants: list[str] | None = None,
        transcript_summary: str = "",
        key_decisions: list[str] | None = None,
        assigned_tasks: list[dict[str, str]] | None = None,
        priority_directions: list[str] | None = None,
        search_queries: list[str] | None = None,
        risks: list[str] | None = None,
        kpi_targets: dict[str, float | int] | None = None,
        raw_transcript: str = "",
    ) -> None:
        self.meeting_date = meeting_date
        self.participants = participants or []
        self.transcript_summary = transcript_summary
        self.key_decisions = key_decisions or []
        self.assigned_tasks = assigned_tasks or []
        self.priority_directions = priority_directions or []
        self.search_queries = search_queries or []
        self.risks = risks or []
        self.kpi_targets = kpi_targets or {}
        self.raw_transcript = raw_transcript


def _meeting_to_strategy(meeting: MeetingOutput) -> StrategyInput:
    return StrategyInput(
        priority_topics=meeting.priority_directions,
        target_revenue_growth=float(meeting.kpi_targets.get("revenue_growth", 0.0)),
        target_headcount_growth=float(meeting.kpi_targets.get("headcount_growth", 0.0)),
        hire_priority_roles=[],
        upskill_priority_topics=meeting.priority_directions,
        narrative=meeting.transcript_summary,
    )


def _build_meeting_rag_chunks(meeting: MeetingOutput) -> list[RAGChunk]:
    chunks: list[RAGChunk] = []

    chunks.append(
        RAGChunk(
            chunk_id="secretary::summary",
            source="secretary",
            section="meeting_summary",
            title=f"Совещание от {meeting.meeting_date}",
            text=meeting.transcript_summary,
            metadata={"meeting_date": meeting.meeting_date, "participants": meeting.participants},
        )
    )

    for i, d in enumerate(meeting.key_decisions):
        chunks.append(
            RAGChunk(
                chunk_id=f"secretary::decision::{i}",
                source="secretary",
                section="key_decisions",
                title=f"Решение #{i + 1}",
                text=d,
                metadata={"meeting_date": meeting.meeting_date},
            )
        )

    for t in meeting.assigned_tasks:
        tn = t.get("task", "")[:40]
        chunks.append(
            RAGChunk(
                chunk_id=f"secretary::task::{tn}",
                source="secretary",
                section="assigned_tasks",
                title=f"Поручение: {t.get('task', '')[:80]}",
                text=f"Задача: {t.get('task', '')}. Ответственный: {t.get('responsible', '')}. Срок: {t.get('deadline', '')}.",
                metadata=t,
            )
        )

    for r in meeting.risks:
        chunks.append(
            RAGChunk(
                chunk_id=f"secretary::risk::{r[:40]}",
                source="secretary",
                section="risks",
                title=f"Риск: {r[:80]}",
                text=r,
                metadata={"meeting_date": meeting.meeting_date},
            )
        )

    return chunks


def load_meeting_output(path: str | Path | None = None) -> MeetingOutput:
    if path is None:
        path = Path(__file__).resolve().parent / "sample_meeting_output.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return MeetingOutput(
        meeting_date=str(data.get("meeting_date", "")),
        participants=[str(p) for p in data.get("participants", []) or []],
        transcript_summary=str(data.get("transcript_summary", "")),
        key_decisions=[str(d) for d in data.get("key_decisions", []) or []],
        assigned_tasks=[dict(t) for t in data.get("assigned_tasks", []) or []],
        priority_directions=[str(d) for d in data.get("priority_directions", []) or []],
        search_queries=[str(q) for q in data.get("search_queries", []) or []],
        risks=[str(r) for r in data.get("risks", []) or []],
        kpi_targets={str(k): v for k, v in (data.get("kpi_targets") or {}).items()},
        raw_transcript=str(data.get("raw_transcript", "")),
    )


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def run_secretary_agent(
    *,
    mode: str = "load",
    file_path: str | None = None,
    meeting_json_path: str | Path | None = None,
    record_duration: int = 60,
    model_size: str = "base",
    language: str = "ru",
    use_llm: bool = True,
) -> dict[str, Any]:
    transcript = None

    if mode == "record":
        transcript = record_and_transcribe(duration=record_duration, model_size=model_size, language=language)
        analysis = _llm_analyze_transcript(transcript["text"]) if use_llm else _fallback_analyze_transcript(transcript["text"])
        meeting = MeetingOutput(raw_transcript=transcript["text"], **analysis)

    elif mode == "transcribe":
        if not file_path:
            raise ValueError("Для mode='transcribe' требуется file_path")
        transcript = transcribe_file(file_path, model_size=model_size, language=language)
        analysis = _llm_analyze_transcript(transcript["text"]) if use_llm else _fallback_analyze_transcript(transcript["text"])
        meeting = MeetingOutput(raw_transcript=transcript["text"], **analysis)

    elif mode == "load":
        meeting = load_meeting_output(meeting_json_path)

    else:
        raise ValueError(f"Неизвестный режим: {mode}. Допустимые: record, transcribe, load")

    return {
        "meeting": meeting,
        "strategy_input": _meeting_to_strategy(meeting),
        "search_queries": meeting.search_queries,
        "rag_chunks": _build_meeting_rag_chunks(meeting),
        "transcript": transcript,
    }


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    result = run_secretary_agent(mode="load")
    m = result["meeting"]
    print("=" * 60)
    print("SECRETARY AGENT — РЕЗУЛЬТАТ")
    print("=" * 60)
    print(f"\nДата: {m.meeting_date}")
    print(f"Участники: {', '.join(m.participants)}")
    print(f"\n--- Содержание ---\n{m.transcript_summary}")
    print(f"\n--- Решения ---")
    for d in m.key_decisions:
        print(f"  • {d}")
    print(f"\n--- Поручения ---")
    for t in m.assigned_tasks:
        print(f"  • {t['task']} → {t['responsible']} (до {t['deadline']})")
    print(f"\n--- Направления ---\n  {', '.join(m.priority_directions)}")
    print(f"\n--- Поиск ---")
    for q in m.search_queries:
        print(f"  • {q}")
    print(f"\n--- Риски ---")
    for r in m.risks:
        print(f"  • {r}")
    print(f"\nRAG-чанков: {len(result['rag_chunks'])}")