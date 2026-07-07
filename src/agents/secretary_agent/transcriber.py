"""Демонстрационный скрипт транскрибации аудио/видео.

Использование:
    python transcriber.py <путь_к_файлу> [--output <путь_к_результату>]

Поддерживает mp3, wav, m4a, mp4, avi, mov, webm.
Результат сохраняется в .txt и .json рядом с исходным файлом
(или в указанную папку через --output).

Требуется:
    pip install openai-whisper ffmpeg-python
    + ffmpeg в системе
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.agents.secretary_agent.secretary_agent import transcribe_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Транскрибация аудио/видеофайлов через Whisper"
    )
    parser.add_argument("file", help="Путь к аудио- или видеофайлу")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Папка для сохранения результатов (по умолчанию — рядом с исходным файлом)",
    )
    parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Размер модели Whisper (по умолчанию: base)",
    )
    parser.add_argument(
        "--language", "-l",
        default="ru",
        help="Язык (по умолчанию: ru)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Выполнить LLM-анализ после транскрибации",
    )

    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)

    # Транскрибация
    result = transcribe_file(str(file_path), model_size=args.model, language=args.language)

    # Определяем папку для результатов
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = file_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = file_path.stem

    # Сохраняем TXT
    txt_path = output_dir / f"{stem}_transcript_{timestamp}.txt"
    txt_content = f"Транскрибация: {file_path.name}\n"
    txt_content += f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    txt_content += f"Тип: {result['source_type']}\n"
    txt_content += f"Язык: {result['language']}\n"
    txt_content += f"Сегментов: {len(result['segments'])}\n"
    txt_content += "=" * 60 + "\n\n"

    for seg in result["segments"]:
        txt_content += f"[{seg['start']:.1f}s – {seg['end']:.1f}s] {seg['text']}\n"

    txt_content += "\n" + "=" * 60 + "\n"
    txt_content += "ПОЛНЫЙ ТЕКСТ:\n"
    txt_content += "=" * 60 + "\n\n"
    txt_content += result["text"] + "\n"

    txt_path.write_text(txt_content, encoding="utf-8")

    # Сохраняем JSON
    json_path = output_dir / f"{stem}_transcript_{timestamp}.json"
    json_content = {
        "source_file": str(file_path),
        "transcribed_at": datetime.now().isoformat(),
        "source_type": result["source_type"],
        "language": result["language"],
        "model": args.model,
        "segments_count": len(result["segments"]),
        "segments": result["segments"],
        "full_text": result["text"],
    }
    json_path.write_text(
        json.dumps(json_content, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Вывод в консоль
    print("\n" + "=" * 60)
    print("ТРАНСКРИБАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)
    print(f"Тип источника: {result['source_type']}")
    print(f"Язык: {result['language']}")
    print(f"Сегментов: {len(result['segments'])}")
    print(f"Текст сохранён: {txt_path}")
    print(f"JSON сохранён:  {json_path}")
    print()

    for seg in result["segments"]:
        print(f"[{seg['start']:.1f}s – {seg['end']:.1f}s] {seg['text']}")

    print(f"\n--- Полный текст ---\n{result['text']}")

    # LLM-анализ (опционально)
    if args.llm:
        print("\n" + "=" * 60)
        print("LLM-АНАЛИЗ ТРАНСКРИПТА")
        print("=" * 60)

        try:
            from src.agents.secretary_agent.secretary_agent import _llm_analyze_transcript

            analysis = _llm_analyze_transcript(result["text"])

            analysis_path = output_dir / f"{stem}_analysis_{timestamp}.json"
            analysis_path.write_text(
                json.dumps(analysis, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            print(f"Анализ сохранён: {analysis_path}")
            print(f"\nКраткое содержание: {analysis.get('transcript_summary', '—')}")
            print(f"Решения: {len(analysis.get('key_decisions', []))}")
            print(f"Поручения: {len(analysis.get('assigned_tasks', []))}")
            print(f"Направления: {', '.join(analysis.get('priority_directions', []))}")
            print(f"Риски: {len(analysis.get('risks', []))}")

        except Exception as e:
            print(f"❌ Ошибка LLM-анализа: {e}")


if __name__ == "__main__":
    main()