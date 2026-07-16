"""
Secretary Agent - отвечает за обработку аудио и транскрибацию
"""

import os
import json
import time
import subprocess
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
from pathlib import Path

# ==================== УЛУЧШЕННЫЙ ПРОМПТ С ДЕТАЛЬНЫМ АНАЛИЗОМ ====================

_LLM_ANALYSIS_PROMPT = """
Ты — профессиональный секретарь-аналитик на русском языке.

ВАЖНО: ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
ВСЕ ПОЛЯ JSON ДОЛЖНЫ БЫТЬ ЗАПОЛНЕНЫ НА РУССКОМ ЯЗЫКЕ.
Исключение — общепринятые сокращения (API, JSON, AI, VPN, IT, HR, KPI, CI/CD, ML, NLP и т.п.)

Твоя задача — извлечь из транскрипта выступления/совещания руководителя максимум управленчески значимой информации.

Транскрипт:
{transcript}

Извлеки и структурируй следующую информацию (ОТВЕТ ТОЛЬКО НА РУССКОМ):

1. **Основные тезисы руководителя** — 3-5 ключевых мыслей, установок, стратегических ориентиров
2. **Принятые решения** — что именно решено, кем, в какие сроки
3. **Поручения и задачи** — кому, что, к какому сроку
4. **Выявленные риски и проблемы** — что беспокоит руководителя, какие угрозы он видит
5. **Ключевые темы обсуждения** — о чём говорили (не технические детали, а смысловые блоки)
6. **Общая тональность и настроение** — уверенность, тревога, срочность, готовность к изменениям

Формат ответа (строго JSON на РУССКОМ языке):
{{
  "meeting_date": "ГГГГ-ММ-ДД или null",
  "main_theses": [
    "тезис 1 на русском",
    "тезис 2 на русском"
  ],
  "decisions": [
    {{
      "decision": "Что решили на русском",
      "who": "Кто озвучил/принял на русском",
      "deadline": "Срок или null"
    }}
  ],
  "action_items": [
    {{
      "task": "Что нужно сделать на русском",
      "assignee": "Кому поручено на русском",
      "deadline": "Срок или null"
    }}
  ],
  "risks": [
    {{
      "risk": "Описание риска на русском",
      "owner": "Кто ответственен на русском",
      "priority": "high/medium/low"
    }}
  ],
  "key_topics": ["тема1 на русском", "тема2 на русском"],
  "tone_and_mood": "Описание тональности на русском",
  "summary": "Краткая сводка встречи на русском (2-3 предложения)"
}}

Важно:
1. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
2. Все поля JSON должны быть на русском языке
3. Верни только JSON, без пояснений
4. Если информация отсутствует, используй null или пустые списки
"""

# ==================== КЛАСС АГЕНТА ====================

class SecretaryAgent:
    """Агент секретаря для обработки аудио и транскрибации"""
    
    # Константа для папки с результатами (относительно корня проекта)
    RESULTS_DIR_NAME = "transcription_results"
    
    def __init__(self, model_size: str = "medium", language: str = "ru", device: str = "cpu"):
        self.model_size = model_size
        self.language = language
        self.device = device
        self._whisper_available = self._check_whisper()
        self._ollama_available = self._check_ollama()
        
        # Определяем корневую папку проекта
        self._project_root = self._get_project_root()
        self._results_base_dir = self._project_root / "src" / "agents" / "secretary_agent" / self.RESULTS_DIR_NAME
        
        # Создаем папку для результатов при инициализации
        self._results_base_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Папка для результатов: {self._results_base_dir}")
        
    def _get_project_root(self) -> Path:
        """
        Определяет корневую папку проекта
        Ищет маркеры проекта: .git, pyproject.toml, setup.py, src/
        """
        current = Path(__file__).resolve().parent
        
        # Поднимаемся вверх, пока не найдем маркер проекта
        for parent in [current] + list(current.parents):
            # Проверяем маркеры проекта
            if (parent / ".git").exists():
                return parent
            if (parent / "pyproject.toml").exists():
                return parent
            if (parent / "setup.py").exists():
                return parent
            # Проверяем, есть ли папка src (проект с src-структурой)
            if (parent / "src").exists() and (parent / "src" / "agents").exists():
                return parent
        
        # Если не нашли, используем родительскую папку secretary_agent
        return current.parent.parent.parent
        
    def _check_whisper(self) -> bool:
        try:
            import whisper
            return True
        except ImportError:
            return False
    
    def _check_ollama(self) -> bool:
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _get_output_paths(self, audio_path: str) -> Dict[str, str]:
        """
        Генерирует пути для сохранения результатов в папке проекта
        
        Args:
            audio_path: Путь к исходному аудио/видео файлу
            
        Returns:
            Dict с путями для разных типов файлов
        """
        # Используем имя исходного файла без расширения
        base_name = Path(audio_path).stem
        
        # Создаем подпапку для конкретного файла (для организации)
        file_results_dir = self._results_base_dir / base_name
        file_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Временная метка
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        paths = {
            "base_dir": str(self._results_base_dir),
            "file_dir": str(file_results_dir),
            "transcript": str(file_results_dir / f"transcript_{timestamp}.txt"),
            "transcript_raw": str(file_results_dir / f"transcript_raw_{timestamp}.txt"),
            "analysis": str(file_results_dir / f"analysis_{timestamp}.json"),
            "full_result": str(file_results_dir / f"full_result_{timestamp}.json"),
            "summary": str(file_results_dir / f"summary_{timestamp}.txt"),
            "source_file": audio_path,
            "source_name": base_name,
        }
        
        # Отладочный вывод
        print(f"\n📁 ПУТИ ДЛЯ СОХРАНЕНИЯ:")
        print(f"  Проект: {self._project_root}")
        print(f"  Папка результатов: {self._results_base_dir}")
        print(f"  Подпапка файла: {file_results_dir}")
        print(f"  Исходный файл: {base_name}")
        
        return paths
    
    def _save_results(self, result: Dict[str, Any], audio_path: str) -> Dict[str, str]:
        """
        Сохраняет все результаты в папку проекта
        
        Args:
            result: Результат обработки
            audio_path: Путь к исходному файлу
            
        Returns:
            Dict с путями сохраненных файлов
        """
        paths = self._get_output_paths(audio_path)
        saved_files = {}
        
        try:
            # 1. Сохраняем полный результат в JSON
            with open(paths["full_result"], 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            saved_files["full_result"] = paths["full_result"]
            print(f"  ✅ Сохранен full_result: {paths['full_result']}")
            
            # 2. Сохраняем транскрипт в TXT
            if "transcript" in result:
                with open(paths["transcript"], 'w', encoding='utf-8') as f:
                    f.write(result["transcript"])
                saved_files["transcript"] = paths["transcript"]
                print(f"  ✅ Сохранен transcript: {paths['transcript']}")
            
            # 3. Сохраняем сырой транскрипт с таймкодами
            if "segments" in result and result["segments"]:
                with open(paths["transcript_raw"], 'w', encoding='utf-8') as f:
                    for segment in result["segments"]:
                        start = segment.get("start", 0)
                        end = segment.get("end", 0)
                        text = segment.get("text", "")
                        f.write(f"[{start:.1f}s - {end:.1f}s] {text}\n")
                saved_files["transcript_raw"] = paths["transcript_raw"]
                print(f"  ✅ Сохранен transcript_raw: {paths['transcript_raw']}")
            
            # 4. Сохраняем анализ в JSON
            if "analysis" in result and result["analysis"].get("success"):
                with open(paths["analysis"], 'w', encoding='utf-8') as f:
                    json.dump(result["analysis"], f, ensure_ascii=False, indent=2)
                saved_files["analysis"] = paths["analysis"]
                print(f"  ✅ Сохранен analysis: {paths['analysis']}")
                
                # 5. Сохраняем человекочитаемый отчет
                self._save_human_readable_report(result["analysis"], paths["summary"])
                saved_files["summary"] = paths["summary"]
                print(f"  ✅ Сохранен summary: {paths['summary']}")
            
            print(f"\n💾 ВСЕ ФАЙЛЫ СОХРАНЕНЫ В: {paths['file_dir']}")
            print(f"   Всего файлов: {len(saved_files)}")
            
        except Exception as e:
            print(f"❌ ОШИБКА при сохранении файлов: {e}")
            import traceback
            traceback.print_exc()
        
        return saved_files
    
    def _save_human_readable_report(self, analysis: Dict[str, Any], filepath: str):
        """Сохраняет человекочитаемый отчет о совещании"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("ОТЧЕТ О СОВЕЩАНИИ\n")
                f.write("=" * 80 + "\n")
                f.write(f"Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # Резюме
                if "summary" in analysis:
                    f.write("📋 РЕЗЮМЕ\n")
                    f.write("-" * 40 + "\n")
                    f.write(analysis["summary"] + "\n\n")
                
                # Основные тезисы
                if "main_theses" in analysis and analysis["main_theses"]:
                    f.write("📌 ОСНОВНЫЕ ТЕЗИСЫ РУКОВОДИТЕЛЯ\n")
                    f.write("-" * 40 + "\n")
                    for i, thesis in enumerate(analysis["main_theses"], 1):
                        f.write(f"{i}. {thesis}\n")
                    f.write("\n")
                
                # Решения
                if "decisions" in analysis and analysis["decisions"]:
                    f.write("📋 ПРИНЯТЫЕ РЕШЕНИЯ\n")
                    f.write("-" * 40 + "\n")
                    for i, decision in enumerate(analysis["decisions"], 1):
                        f.write(f"{i}. {decision.get('decision', '')}\n")
                        if decision.get('who'):
                            f.write(f"   Кто: {decision['who']}\n")
                        if decision.get('deadline'):
                            f.write(f"   Срок: {decision['deadline']}\n")
                    f.write("\n")
                
                # Поручения
                if "action_items" in analysis and analysis["action_items"]:
                    f.write("✅ ПОРУЧЕНИЯ И ЗАДАЧИ\n")
                    f.write("-" * 40 + "\n")
                    for i, task in enumerate(analysis["action_items"], 1):
                        f.write(f"{i}. {task.get('task', '')}\n")
                        if task.get('assignee'):
                            f.write(f"   Исполнитель: {task['assignee']}\n")
                        if task.get('deadline'):
                            f.write(f"   Срок: {task['deadline']}\n")
                    f.write("\n")
                
                # Риски
                if "risks" in analysis and analysis["risks"]:
                    f.write("⚠️ ВЫЯВЛЕННЫЕ РИСКИ\n")
                    f.write("-" * 40 + "\n")
                    for i, risk in enumerate(analysis["risks"], 1):
                        f.write(f"{i}. {risk.get('risk', '')}\n")
                        if risk.get('owner'):
                            f.write(f"   Ответственный: {risk['owner']}\n")
                        if risk.get('severity'):
                            severity_ru = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}.get(risk['severity'], risk['severity'])
                            f.write(f"   Серьёзность: {severity_ru}\n")
                    f.write("\n")
                
                # Ключевые темы
                if "key_topics" in analysis and analysis["key_topics"]:
                    f.write("📚 КЛЮЧЕВЫЕ ТЕМЫ ОБСУЖДЕНИЯ\n")
                    f.write("-" * 40 + "\n")
                    for topic in analysis["key_topics"]:
                        f.write(f"  • {topic}\n")
                    f.write("\n")
                
                # Тональность
                if "tone_and_mood" in analysis and analysis["tone_and_mood"]:
                    f.write("🎭 ТОНАЛЬНОСТЬ И НАСТРОЕНИЕ\n")
                    f.write("-" * 40 + "\n")
                    f.write(analysis["tone_and_mood"] + "\n\n")
                
                f.write("\n" + "=" * 80 + "\n")
                
        except Exception as e:
            print(f"⚠️ Ошибка при сохранении отчета: {e}")
    
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        if not os.path.exists(audio_path):
            return {
                "success": False,
                "error": f"Файл не найден: {audio_path}"
            }
        
        ext = os.path.splitext(audio_path)[1].lower()
        if ext not in ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.mp4']:
            return {
                "success": False,
                "error": f"Неподдерживаемый формат: {ext}"
            }
        
        if self._whisper_available:
            try:
                return self._transcribe_with_whisper(audio_path)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Ошибка Whisper: {str(e)}"
                }
        else:
            return {
                "success": False,
                "error": "Whisper не установлен. Установите: pip install openai-whisper"
            }
    
    def _transcribe_with_whisper(self, audio_path: str) -> Dict[str, Any]:
        import whisper
        
        print(f"🔄 Загрузка модели Whisper {self.model_size}...")
        model = whisper.load_model(self.model_size, device=self.device)
        
        print(f"🎙️ Транскрибация аудио... (это может занять время)")
        result = model.transcribe(
            audio_path,
            language=self.language,
            task="transcribe",
            verbose=False
        )
        
        return {
            "success": True,
            "text": result["text"],
            "segments": result.get("segments", []),
            "language": result.get("language", self.language),
            "model": f"whisper-{self.model_size}",
            "timestamp": datetime.now().isoformat()
        }
    
    def _chunk_transcript(self, transcript: str, max_length: int = 5000) -> List[str]:
        """Разбивает длинный транскрипт на чанки"""
        if len(transcript) <= max_length:
            return [transcript]
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        sentences = re.split(r'(?<=[.!?])\s+', transcript)
        
        for sentence in sentences:
            sentence_length = len(sentence)
            if current_length + sentence_length > max_length and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0
            current_chunk.append(sentence)
            current_length += sentence_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _call_ollama_with_retry(self, prompt: str, max_retries: int = 3, timeout: int = 120) -> Dict[str, Any]:
        """Вызов Ollama с повторными попытками"""
        import requests
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                print(f"  Попытка {attempt + 1}/{max_retries}...")
                
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "qwen2.5:7b",
                        "prompt": prompt,
                        "system": "Ты — русскоязычный ассистент. Отвечай только на русском языке. Все поля JSON должны быть на русском языке.",
                        "stream": False,
                        "temperature": 0.3,
                        "format": "json",
                        "options": {
                            "num_predict": 2048,
                            "top_k": 40,
                            "top_p": 0.9,
                            "repeat_penalty": 1.1,
                        }
                    },
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "response": response.json()
                    }
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                last_error = f"Таймаут (попытка {attempt + 1})"
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10
                    print(f"  ⏳ Таймаут, ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                continue
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
        
        return {
            "success": False,
            "error": last_error
        }
    
    def _llm_analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """Анализ транскрипта с помощью LLM"""
        if not self._ollama_available:
            return {
                "success": False,
                "error": "Ollama недоступен. Запустите Ollama локально: ollama serve"
            }
        
        try:
            print("🧠 Отправка транскрипта на LLM-анализ...")
            
            chunks = self._chunk_transcript(transcript, max_length=5000)
            
            if len(chunks) > 1:
                print(f"📄 Транскрипт разбит на {len(chunks)} частей")
                
                all_results = []
                for i, chunk in enumerate(chunks, 1):
                    print(f"\n  📝 Часть {i}/{len(chunks)} (длина: {len(chunk)} символов)...")
                    
                    prompt = _LLM_ANALYSIS_PROMPT.format(transcript=chunk)
                    result = self._call_ollama_with_retry(prompt=prompt, max_retries=3, timeout=90)
                    
                    if result["success"]:
                        response_data = result["response"]
                        try:
                            chunk_analysis = json.loads(response_data["response"])
                            all_results.append(chunk_analysis)
                            print(f"  ✅ Часть {i} обработана")
                        except json.JSONDecodeError:
                            text = response_data["response"]
                            json_match = re.search(r'\{.*\}', text, re.DOTALL)
                            if json_match:
                                try:
                                    chunk_analysis = json.loads(json_match.group())
                                    all_results.append(chunk_analysis)
                                    print(f"  ✅ Часть {i} обработана (JSON извлечен)")
                                except:
                                    print(f"  ⚠️ Не удалось распарсить JSON для части {i}")
                            else:
                                print(f"  ⚠️ Не найден JSON в ответе для части {i}")
                    else:
                        print(f"  ❌ Ошибка части {i}: {result.get('error', 'Unknown')}")
                
                if all_results:
                    merged = all_results[0]
                    for chunk_result in all_results[1:]:
                        for key in ["main_theses", "decisions", "action_items", "risks", "key_topics"]:
                            if key in chunk_result and chunk_result[key]:
                                if key not in merged:
                                    merged[key] = []
                                merged[key].extend(chunk_result[key])
                    
                    merged["success"] = True
                    print(f"\n  ✅ Анализ завершен. Найдено:")
                    print(f"     - Тезисов: {len(merged.get('main_theses', []))}")
                    print(f"     - Решений: {len(merged.get('decisions', []))}")
                    print(f"     - Задач: {len(merged.get('action_items', []))}")
                    print(f"     - Рисков: {len(merged.get('risks', []))}")
                    return merged
                else:
                    return {
                        "success": False,
                        "error": "Не удалось обработать ни одной части"
                    }
            
            # Один чанк
            print("  📝 Анализ полного транскрипта...")
            prompt = _LLM_ANALYSIS_PROMPT.format(transcript=transcript)
            result = self._call_ollama_with_retry(prompt=prompt, max_retries=3, timeout=180)
            
            if result["success"]:
                response_data = result["response"]
                try:
                    analysis = json.loads(response_data["response"])
                    analysis["success"] = True
                    print("  ✅ Анализ завершен")
                    return analysis
                except json.JSONDecodeError:
                    text = response_data["response"]
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        try:
                            analysis = json.loads(json_match.group())
                            analysis["success"] = True
                            print("  ✅ Анализ завершен (JSON извлечен)")
                            return analysis
                        except:
                            pass
                    
                    return {
                        "success": False,
                        "error": "Не удалось распарсить JSON",
                        "raw_response": text[:500]
                    }
            else:
                return {
                    "success": False,
                    "error": f"Ошибка: {result.get('error', 'Unknown')}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка LLM-анализа: {str(e)}"
            }
    
    def process_audio(self, audio_path: str, analyze: bool = True, auto_save: bool = True) -> Dict[str, Any]:
        """Полная обработка аудио: транскрибация + анализ + сохранение"""
        # Транскрибация
        transcript_result = self.transcribe_audio(audio_path)
        
        if not transcript_result["success"]:
            return transcript_result
        
        result = {
            "success": True,
            "transcript": transcript_result["text"],
            "segments": transcript_result.get("segments", []),
            "metadata": {
                "model": transcript_result.get("model", "unknown"),
                "language": transcript_result.get("language", "ru"),
                "timestamp": transcript_result.get("timestamp", datetime.now().isoformat()),
                "source_file": audio_path
            }
        }
        
        # LLM-анализ
        if analyze and transcript_result["text"].strip():
            print("\n" + "=" * 60)
            analysis_result = self._llm_analyze_transcript(transcript_result["text"])
            result["analysis"] = analysis_result
            print("=" * 60)
        else:
            result["analysis"] = {
                "success": False,
                "error": "Транскрипт пуст или анализ отключен"
            }
        
        # Автоматическое сохранение
        if auto_save and result["success"]:
            print("\n💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ...")
            saved_files = self._save_results(result, audio_path)
            result["saved_files"] = saved_files
            result["saved_files_list"] = list(saved_files.values())
        
        return result


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def transcribe_file(audio_path: str, model_size: str = "medium", language: str = "ru") -> Dict[str, Any]:
    agent = SecretaryAgent(model_size=model_size, language=language)
    return agent.transcribe_audio(audio_path)


def analyze_transcript(transcript: str) -> Dict[str, Any]:
    agent = SecretaryAgent()
    return agent._llm_analyze_transcript(transcript)


def process_audio_file(audio_path: str, model_size: str = "medium", language: str = "ru", analyze: bool = True) -> Dict[str, Any]:
    agent = SecretaryAgent(model_size=model_size, language=language)
    return agent.process_audio(audio_path, analyze=analyze)


# ============================================================
# ФУНКЦИЯ ЗАПУСКА (для оркестратора)
# ============================================================

def run_secretary_agent(
    mode: str = "load",
    meeting_json_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    model_size: str = "medium",
    language: str = "ru",
    analyze: bool = True,
    auto_save: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Запускает secretary_agent для извлечения решений и поручений.
    
    Args:
        mode: Режим работы ("load" - загрузка из JSON, "process" - обработка аудио, "latest" - последний результат)
        meeting_json_path: Путь к JSON-файлу с транскриптом (для режима "load")
        audio_path: Путь к аудиофайлу (для режима "process")
        model_size: Размер модели Whisper
        language: Язык распознавания
        analyze: Выполнять LLM-анализ
        auto_save: Автоматически сохранять результаты
        **kwargs: Дополнительные параметры
        
    Returns:
        Dict: Результаты работы агента
    """
    print("📋 Запуск secretary_agent...")
    
    agent = SecretaryAgent(model_size=model_size, language=language)
    
    # Режим 1: Загрузка из JSON файла
    if mode == "load":
        # Если путь не указан, ищем последний файл
        if meeting_json_path is None:
            results_dir = agent._results_base_dir
            # Сначала ищем full_result_*.json
            json_files = list(results_dir.glob("*/full_result_*.json"))
            if not json_files:
                json_files = list(results_dir.glob("full_result_*.json"))
            if json_files:
                latest = max(json_files, key=lambda p: p.stat().st_mtime)
                meeting_json_path = str(latest)
                print(f"   Использую последний файл: {meeting_json_path}")
            else:
                # Если нет full_result, ищем analysis_*.json
                json_files = list(results_dir.glob("*/analysis_*.json"))
                if not json_files:
                    json_files = list(results_dir.glob("analysis_*.json"))
                if json_files:
                    latest = max(json_files, key=lambda p: p.stat().st_mtime)
                    meeting_json_path = str(latest)
                    print(f"   Использую последний analysis файл: {meeting_json_path}")
                else:
                    # Ищем любые JSON файлы
                    json_files = list(results_dir.glob("*.json"))
                    if json_files:
                        latest = max(json_files, key=lambda p: p.stat().st_mtime)
                        meeting_json_path = str(latest)
                        print(f"   Использую последний JSON файл: {meeting_json_path}")
                    else:
                        return {
                            "success": False,
                            "error": "Не найден JSON-файл с транскриптом. Укажите meeting_json_path или сначала обработайте аудио.",
                            "status": "failed"
                        }
        
        try:
            with open(meeting_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ============================================================
            # РЕКУРСИВНЫЙ ПОИСК КЛЮЧЕЙ В ЛЮБОЙ СТРУКТУРЕ JSON
            # ============================================================
            def find_keys(obj, keys_to_find):
                """Рекурсивно ищет ключи в JSON любой структуры."""
                results = {}
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        # Если ключ найден и значение не пустое
                        if key in keys_to_find and value:
                            if key not in results or not results[key]:
                                results[key] = value
                        # Рекурсивный поиск во вложенных структурах
                        elif isinstance(value, (dict, list)):
                            nested = find_keys(value, keys_to_find)
                            for k, v in nested.items():
                                if k not in results or not results[k]:
                                    results[k] = v
                elif isinstance(obj, list):
                    for item in obj:
                        nested = find_keys(item, keys_to_find)
                        for k, v in nested.items():
                            if k not in results or not results[k]:
                                results[k] = v
                return results
            
            # Ключи для поиска
            search_keys = [
                "decisions", "decision", "key_decisions",
                "action_items", "action_item", "tasks", "assigned_tasks",
                "main_theses", "theses", "key_points",
                "risks", "risk",
                "key_topics", "topics",
                "tone_and_mood", "tone",
                "summary", "meeting_date"
            ]
            
            # Ищем данные
            found = find_keys(data, search_keys)
            
            # Если нашли ключевые данные
            if found.get("decisions") or found.get("action_items") or found.get("main_theses"):
                result = {
                    "success": True,
                    "meeting": {
                        "key_decisions": found.get("decisions", found.get("decision", [])),
                        "assigned_tasks": found.get("action_items", found.get("tasks", [])),
                        "main_theses": found.get("main_theses", found.get("theses", [])),
                        "risks": found.get("risks", []),
                        "key_topics": found.get("key_topics", found.get("topics", [])),
                        "tone_and_mood": found.get("tone_and_mood", found.get("tone", "")),
                        "summary": found.get("summary", ""),
                        "meeting_date": found.get("meeting_date")
                    },
                    "rag_chunks": _generate_secretary_rag_chunks(found),
                    "status": "completed",
                    "source": meeting_json_path
                }
                print(f"   ✅ Загружены данные из {meeting_json_path}")
                return result
            
            # Проверка analysis.success (если есть поле analysis)
            if "analysis" in data and isinstance(data["analysis"], dict):
                analysis = data.get("analysis", {})
                if analysis.get("success"):
                    result = {
                        "success": True,
                        "meeting": {
                            "key_decisions": analysis.get("decisions", analysis.get("decision", [])),
                            "assigned_tasks": analysis.get("action_items", analysis.get("tasks", [])),
                            "main_theses": analysis.get("main_theses", analysis.get("theses", [])),
                            "risks": analysis.get("risks", []),
                            "key_topics": analysis.get("key_topics", analysis.get("topics", [])),
                            "tone_and_mood": analysis.get("tone_and_mood", analysis.get("tone", "")),
                            "summary": analysis.get("summary", ""),
                            "meeting_date": analysis.get("meeting_date")
                        },
                        "rag_chunks": _generate_secretary_rag_chunks(analysis),
                        "status": "completed",
                        "source": meeting_json_path
                    }
                    print(f"   ✅ Загружен анализ из {meeting_json_path}")
                    return result
            
            print(f"   ⚠️ Не найдены решения и поручения в {meeting_json_path}")
            print(f"   Доступные ключи в файле: {list(data.keys()) if isinstance(data, dict) else 'не словарь'}")
            return {
                "success": False,
                "error": "Не найдены решения и поручения в файле",
                "source": meeting_json_path,
                "status": "failed"
            }
                
        except json.JSONDecodeError as e:
            print(f"   ⚠️ Ошибка парсинга JSON: {e}")
            return {
                "success": False,
                "error": f"Невалидный JSON: {e}",
                "source": meeting_json_path,
                "status": "failed"
            }
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки из {meeting_json_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": meeting_json_path,
                "status": "failed"
            }
    
    # Режим 2: Обработка аудио
    elif mode == "process" and audio_path:
        result = agent.process_audio(
            audio_path=audio_path,
            analyze=analyze,
            auto_save=auto_save
        )
        
        if result.get("success"):
            analysis = result.get("analysis", {})
            return {
                "success": True,
                "meeting": {
                    "key_decisions": analysis.get("decisions", analysis.get("decision", [])),
                    "assigned_tasks": analysis.get("action_items", analysis.get("tasks", [])),
                    "main_theses": analysis.get("main_theses", analysis.get("theses", [])),
                    "risks": analysis.get("risks", []),
                    "key_topics": analysis.get("key_topics", analysis.get("topics", [])),
                    "tone_and_mood": analysis.get("tone_and_mood", analysis.get("tone", "")),
                    "summary": analysis.get("summary", ""),
                    "meeting_date": analysis.get("meeting_date")
                },
                "rag_chunks": _generate_secretary_rag_chunks(analysis),
                "transcript": result.get("transcript", ""),
                "saved_files": result.get("saved_files", {}),
                "status": "completed"
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Ошибка обработки аудио"),
                "status": "failed"
            }
    
    # Режим 3: Загрузка последнего сохранённого результата
    elif mode == "latest":
        results_dir = agent._results_base_dir
        json_files = list(results_dir.glob("*/full_result_*.json"))
        
        if not json_files:
            json_files = list(results_dir.glob("full_result_*.json"))
        
        if json_files:
            latest = max(json_files, key=lambda p: p.stat().st_mtime)
            try:
                with open(latest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                analysis = data.get("analysis", {})
                return {
                    "success": True,
                    "meeting": {
                        "key_decisions": analysis.get("decisions", analysis.get("decision", [])),
                        "assigned_tasks": analysis.get("action_items", analysis.get("tasks", [])),
                        "main_theses": analysis.get("main_theses", analysis.get("theses", [])),
                        "risks": analysis.get("risks", []),
                        "key_topics": analysis.get("key_topics", analysis.get("topics", [])),
                        "tone_and_mood": analysis.get("tone_and_mood", analysis.get("tone", "")),
                        "summary": analysis.get("summary", ""),
                        "meeting_date": analysis.get("meeting_date")
                    },
                    "rag_chunks": _generate_secretary_rag_chunks(analysis),
                    "source": str(latest),
                    "status": "completed"
                }
            except Exception as e:
                print(f"   ⚠️ Ошибка загрузки последнего результата: {e}")
        
        return {
            "success": False,
            "error": "Не найдены сохранённые результаты",
            "status": "failed"
        }
    
    else:
        return {
            "success": False,
            "error": f"Неизвестный режим: {mode}. Доступны: load, process, latest",
            "status": "failed"
        }


def _generate_secretary_rag_chunks(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Генерирует RAG-чанки из анализа транскрипта.
    
    Args:
        analysis: Анализ транскрипта от LLM
        
    Returns:
        List: Список RAG-чанков
    """
    chunks = []
    
    decisions = analysis.get("decisions", analysis.get("decision", []))
    tasks = analysis.get("action_items", analysis.get("tasks", []))
    theses = analysis.get("main_theses", analysis.get("theses", []))
    risks = analysis.get("risks", [])
    topics = analysis.get("key_topics", analysis.get("topics", []))
    
    # Если данные найдены в разных полях, пытаемся объединить
    if not decisions and "decision" in analysis:
        decisions = analysis.get("decision", [])
    if not tasks and "tasks" in analysis:
        tasks = analysis.get("tasks", [])
    if not theses and "theses" in analysis:
        theses = analysis.get("theses", [])
    
    # Если всё ещё пусто, пробуем найти в корневых полях
    if not decisions and "decisions" in analysis:
        decisions = analysis.get("decisions", [])
    
    if not any([decisions, tasks, theses, risks, topics]):
        return chunks
    
    # 1. Чанк с резюме встречи
    if analysis.get("summary"):
        chunks.append({
            "chunk_id": f"secretary_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "text": f"Сводка встречи: {analysis.get('summary', '')}",
            "source": "secretary_agent",
            "section": "summary",
            "title": "Резюме встречи",
            "metadata": {
                "type": "meeting_summary",
                "timestamp": datetime.now().isoformat()
            }
        })
    
    # 2. Чанк с ключевыми тезисами
    if theses:
        if isinstance(theses, dict):
            # Если theses - словарь, пытаемся извлечь значения
            theses_list = []
            for key, value in theses.items():
                if isinstance(value, str):
                    theses_list.append(value)
                elif isinstance(value, list):
                    theses_list.extend(value)
            theses = theses_list
        elif isinstance(theses, str):
            theses = [theses]
        
        theses_text = "Основные тезисы руководителя:\n" + "\n".join([f"- {t}" for t in theses if t])
        chunks.append({
            "chunk_id": f"secretary_theses_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "text": theses_text,
            "source": "secretary_agent",
            "section": "theses",
            "title": "Ключевые тезисы руководителя",
            "metadata": {
                "type": "main_theses",
                "count": len(theses),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    # 3. Чанк с решениями
    if decisions:
        if isinstance(decisions, dict):
            decisions = [decisions]
        elif isinstance(decisions, str):
            decisions = [{"decision": decisions}]
        
        decisions_text = "Принятые решения:\n" + "\n".join([
            f"- {d.get('decision', d) if isinstance(d, dict) else d}" + 
            (f" (ответственный: {d.get('who', 'не указан')})" if isinstance(d, dict) and d.get('who') else "")
            for d in decisions
        ])
        chunks.append({
            "chunk_id": f"secretary_decisions_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "text": decisions_text,
            "source": "secretary_agent",
            "section": "decisions",
            "title": "Принятые решения",
            "metadata": {
                "type": "decisions",
                "count": len(decisions),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    # 4. Чанк с поручениями и задачами
    if tasks:
        if isinstance(tasks, dict):
            tasks = [tasks]
        elif isinstance(tasks, str):
            tasks = [{"task": tasks}]
        
        tasks_text = "Поручения и задачи:\n" + "\n".join([
            f"- {t.get('task', t) if isinstance(t, dict) else t}" +
            (f" (исполнитель: {t.get('assignee', 'не назначен')})" if isinstance(t, dict) and t.get('assignee') else "")
            for t in tasks
        ])
        chunks.append({
            "chunk_id": f"secretary_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "text": tasks_text,
            "source": "secretary_agent",
            "section": "tasks",
            "title": "Поручения и задачи",
            "metadata": {
                "type": "action_items",
                "count": len(tasks),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    # 5. Чанк с рисками
    if risks:
        if isinstance(risks, dict):
            risks = [risks]
        elif isinstance(risks, str):
            risks = [{"risk": risks}]
        
        risks_text = "Выявленные риски:\n" + "\n".join([
            f"- {r.get('risk', r) if isinstance(r, dict) else r}" +
            (f" (ответственный: {r.get('owner', 'не указан')})" if isinstance(r, dict) and r.get('owner') else "")
            for r in risks
        ])
        chunks.append({
            "chunk_id": f"secretary_risks_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "text": risks_text,
            "source": "secretary_agent",
            "section": "risks",
            "title": "Выявленные риски",
            "metadata": {
                "type": "risks",
                "count": len(risks),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    # 6. Чанк с ключевыми темами
    if topics:
        if isinstance(topics, dict):
            topics = list(topics.values())
        elif isinstance(topics, str):
            topics = [topics]
        
        topics_text = "Ключевые темы обсуждения:\n" + "\n".join([f"- {t}" for t in topics if t])
        chunks.append({
            "chunk_id": f"secretary_topics_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "text": topics_text,
            "source": "secretary_agent",
            "section": "topics",
            "title": "Ключевые темы обсуждения",
            "metadata": {
                "type": "key_topics",
                "count": len(topics),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    # 7. Чанк с общей информацией
    if analysis.get("tone_and_mood") or analysis.get("tone") or analysis.get("meeting_date"):
        info_parts = []
        if analysis.get("meeting_date"):
            info_parts.append(f"Дата встречи: {analysis['meeting_date']}")
        if analysis.get("tone_and_mood"):
            info_parts.append(f"Тональность: {analysis['tone_and_mood']}")
        elif analysis.get("tone"):
            info_parts.append(f"Тональность: {analysis['tone']}")
        
        if info_parts:
            chunks.append({
                "chunk_id": f"secretary_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "text": "Общая информация:\n" + "\n".join(info_parts),
                "source": "secretary_agent",
                "section": "general",
                "title": "Общая информация о встрече",
                "metadata": {
                    "type": "general_info",
                    "timestamp": datetime.now().isoformat()
                }
            })
    
    return chunks


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

def main():
    """Тестовый запуск агента"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Secretary Agent - обработка аудио")
    parser.add_argument("audio", help="Путь к аудиофайлу")
    parser.add_argument("--model", default="medium", choices=["medium", "large"],
                       help="Размер модели Whisper (по умолчанию: medium)")
    parser.add_argument("--language", default="ru", help="Язык распознавания")
    parser.add_argument("--no-analyze", action="store_true", help="Отключить LLM-анализ")
    parser.add_argument("--no-save", action="store_true", help="Отключить автоматическое сохранение")
    parser.add_argument("--output", help="Дополнительный файл для сохранения результата (JSON)")
    
    args = parser.parse_args()
    
    # Проверяем существование файла
    if not os.path.exists(args.audio):
        print(f"❌ Файл не найден: {args.audio}")
        sys.exit(1)
    
    agent = SecretaryAgent(model_size=args.model, language=args.language)
    
    print(f"🔊 Обработка аудио: {args.audio}")
    print(f"📝 Модель: {args.model}, Язык: {args.language}")
    print("-" * 50)
    
    result = agent.process_audio(
        args.audio, 
        analyze=not args.no_analyze,
        auto_save=not args.no_save
    )
    
    if result["success"]:
        print("\n✅ Транскрибация завершена")
        
        if "saved_files" in result:
            print("\n📁 СОХРАНЕННЫЕ ФАЙЛЫ:")
            print("=" * 60)
            for key, path in result["saved_files"].items():
                print(f"  {key}: {path}")
            print("=" * 60)
            
            if "full_result" in result["saved_files"]:
                results_dir = Path(result["saved_files"]["full_result"]).parent
                print(f"\n📂 Откройте папку: {results_dir}")
        
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Дополнительная копия: {args.output}")
            except Exception as e:
                print(f"\n⚠️ Ошибка сохранения: {e}")
        
        # Краткая сводка
        if "analysis" in result and result["analysis"].get("success"):
            analysis = result["analysis"]
            print(f"\n📊 КРАТКАЯ СВОДКА:")
            print("-" * 50)
            print(f"  Тезисов: {len(analysis.get('main_theses', []))}")
            print(f"  Решений: {len(analysis.get('decisions', []))}")
            print(f"  Задач: {len(analysis.get('action_items', []))}")
            print(f"  Рисков: {len(analysis.get('risks', []))}")
            
            if analysis.get('action_items'):
                print(f"\n  📌 Задачи:")
                for i, task in enumerate(analysis['action_items'][:3], 1):
                    print(f"    {i}. {task.get('task', '')[:60]}...")
                    if task.get('assignee'):
                        print(f"       → {task['assignee']}")
        
    else:
        print(f"\n❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        sys.exit(1)


if __name__ == "__main__":
    main()