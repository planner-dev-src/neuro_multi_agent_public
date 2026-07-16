"""
Модуль транскрибации аудио/видео файлов
Использует SecretaryAgent для обработки
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.secretary_agent.secretary_agent import (
    SecretaryAgent,
    transcribe_file,
    analyze_transcript,
    process_audio_file
)


def extract_audio_from_video(video_path: str) -> Optional[str]:
    """
    Извлечение аудио из видеофайла с помощью ffmpeg
    
    Args:
        video_path: Путь к видеофайлу
        
    Returns:
        Путь к извлеченному аудиофайлу или None
    """
    try:
        import subprocess
        
        # Создаем временный файл для аудио
        audio_path = os.path.splitext(video_path)[0] + "_audio.wav"
        
        # Извлекаем аудио с помощью ffmpeg
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",  # Без видео
            "-acodec", "pcm_s16le",  # Кодек PCM
            "-ar", "16000",  # Частота дискретизации 16kHz
            "-ac", "1",  # Моно
            "-y",  # Перезаписать файл
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ Ошибка ffmpeg: {result.stderr}")
            return None
            
        print(f"✅ Аудио извлечено: {audio_path}")
        return audio_path
        
    except FileNotFoundError:
        print("❌ ffmpeg не найден. Установите ffmpeg:")
        print("  Windows: скачайте с https://ffmpeg.org/")
        print("  Linux: sudo apt install ffmpeg")
        print("  Mac: brew install ffmpeg")
        return None
    except Exception as e:
        print(f"❌ Ошибка извлечения аудио: {e}")
        return None


def main():
    """Основная функция для запуска транскрибации из командной строки"""
    parser = argparse.ArgumentParser(
        description="Транскрибация аудио/видео файлов с LLM-анализом"
    )
    parser.add_argument(
        "file",
        help="Путь к аудио или видео файлу"
    )
    parser.add_argument(
        "--model",
        default="medium",  # ← ИЗМЕНЕНО: теперь medium по умолчанию
        choices=["medium", "large"],  # ← ИЗМЕНЕНО: только medium и large
        help="Размер модели Whisper (по умолчанию: medium)"
    )
    parser.add_argument(
        "--language",
        default="ru",
        help="Язык распознавания (по умолчанию: ru)"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Запустить LLM-анализ транскрипта"
    )
    parser.add_argument(
        "--output",
        help="Файл для сохранения результата (JSON)"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Не удалять временные файлы"
    )
    
    args = parser.parse_args()
    
    # Проверяем существование файла
    if not os.path.exists(args.file):
        print(f"❌ Файл не найден: {args.file}")
        sys.exit(1)
    
    # Определяем тип файла
    file_ext = os.path.splitext(args.file)[1].lower()
    audio_file = args.file
    
    # Если это видео, извлекаем аудио
    if file_ext in ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv']:
        print(f"🎬 Обнаружен видеофайл, извлекаем аудио...")
        audio_file = extract_audio_from_video(args.file)
        if audio_file is None:
            print("❌ Не удалось извлечь аудио из видео")
            sys.exit(1)
    
    print("=" * 60)
    print("🎙️  НАЧАЛО ТРАНСКРИБАЦИИ")
    print("=" * 60)
    print(f"📁 Файл: {args.file}")
    print(f"📝 Модель: {args.model}")  # ← Будет medium или large
    print(f"🌐 Язык: {args.language}")
    print(f"🔍 LLM-анализ: {'Включен' if args.llm else 'Отключен'}")
    print("-" * 60)
    
    # Создаем агента с выбранной моделью
    agent = SecretaryAgent(
        model_size=args.model,  # ← Передаем medium или large
        language=args.language
    )
    
    # Выполняем транскрибацию
    print("🔄 Транскрибация аудио...")
    result = agent.process_audio(audio_file, analyze=args.llm)
    
    # Удаляем временный аудиофайл
    if not args.no_cleanup and audio_file != args.file:
        try:
            os.remove(audio_file)
            print(f"🧹 Временный файл удален: {audio_file}")
        except:
            pass
    
    # Выводим результаты
    if result["success"]:
        print("\n✅ ТРАНСКРИБАЦИЯ УСПЕШНО ЗАВЕРШЕНА")
        print("=" * 60)
        
        # Выводим метаданные
        print(f"\n📊 МЕТАДАННЫЕ:")
        print(f"  Модель: {result['metadata']['model']}")
        print(f"  Язык: {result['metadata']['language']}")
        print(f"  Время обработки: {result['metadata']['timestamp']}")
        
        # Выводим транскрипт (первые 500 символов)
        print("\n📝 ТРАНСКРИПТ (первые 500 символов):")
        print("-" * 60)
        transcript_preview = result["transcript"][:500] + "..." if len(result["transcript"]) > 500 else result["transcript"]
        print(transcript_preview)
        print("-" * 60)
        
        # Выводим LLM-анализ если есть
        if args.llm and "analysis" in result:
            analysis = result["analysis"]
            if analysis.get("success"):
                print("\n🔍 LLM-АНАЛИЗ ВСТРЕЧИ:")
                print("=" * 60)
                
                print(f"\n📅 Дата встречи: {analysis.get('meeting_date', 'Не указана')}")
                print(f"📋 Сводка: {analysis.get('summary', 'Нет')}")
                
                if analysis.get('key_topics'):
                    print(f"\n🏷️ Основные темы:")
                    for topic in analysis['key_topics']:
                        print(f"  • {topic}")
                
                if analysis.get('decisions'):
                    print(f"\n📌 Принятые решения:")
                    for decision in analysis['decisions']:
                        print(f"  • {decision}")
                
                if analysis.get('action_items'):
                    print(f"\n✅ Задачи и поручения:")
                    for item in analysis['action_items']:
                        task_str = f"  • {item.get('task', '')}"
                        if item.get('assignee'):
                            task_str += f" (Исполнитель: {item['assignee']})"
                        if item.get('deadline'):
                            task_str += f" [Дедлайн: {item['deadline']}]"
                        print(task_str)
                
                if analysis.get('participants'):
                    print(f"\n👥 Участники:")
                    for participant in analysis['participants']:
                        print(f"  • {participant}")
                
                print("\n" + "=" * 60)
            else:
                print(f"\n⚠️ Ошибка LLM-анализа: {analysis.get('error', 'Неизвестная ошибка')}")
                if "raw_response" in analysis:
                    print(f"Ответ LLM: {analysis['raw_response'][:200]}...")
        
        # Сохраняем результат в файл
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Результат сохранен в: {args.output}")
            except Exception as e:
                print(f"\n❌ Ошибка сохранения результата: {e}")
    
    else:
        print(f"\n❌ ОШИБКА ТРАНСКРИБАЦИИ:")
        print(f"  {result.get('error', 'Неизвестная ошибка')}")
        sys.exit(1)
    
    print("\n✅ Готово!")


if __name__ == "__main__":
    main()