#!/usr/bin/env python
"""
Анализ существующего транскрипта через LLM
Запуск: python scripts/analyze_existing.py
"""

import sys
import json
from pathlib import Path

# Добавляем корневую папку проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.secretary_agent.secretary_agent import SecretaryAgent


def main():
    # Путь к папке с транскриптами
    transcript_root = project_root / "src" / "agents" / "secretary_agent" / "transcription_results"
    
    print(f"📁 Поиск транскриптов в: {transcript_root}")
    
    if not transcript_root.exists():
        print(f"❌ Папка не найдена: {transcript_root}")
        return
    
    # Ищем все файлы транскриптов (рекурсивно, включая подпапки)
    transcript_files = list(transcript_root.rglob("transcript_*.txt"))
    
    if not transcript_files:
        print(f"❌ Файлы транскриптов не найдены в: {transcript_root}")
        print("   Доступные папки и файлы:")
        for item in transcript_root.iterdir():
            if item.is_dir():
                print(f"     📁 {item.name}/")
                for f in item.iterdir():
                    print(f"        📄 {f.name}")
            else:
                print(f"     📄 {item.name}")
        return
    
    # Берем самый свежий файл
    transcript_file = max(transcript_files, key=lambda x: x.stat().st_mtime)
    print(f"📄 Найден транскрипт: {transcript_file}")
    
    # Читаем транскрипт
    with open(transcript_file, 'r', encoding='utf-8') as f:
        transcript = f.read()
    
    print(f"📄 Транскрипт загружен: {len(transcript)} символов")
    print("🧠 Запуск LLM-анализа через Ollama...")
    print("-" * 60)
    
    # Анализируем
    agent = SecretaryAgent()
    result = agent._llm_analyze_transcript(transcript)
    
    print("-" * 60)
    
    if result.get("success"):
        print("✅ Анализ выполнен!")
        
        # Сохраняем результат в ту же папку, где лежит транскрипт
        output_file = transcript_file.parent / "analysis_manual.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 Сохранено: {output_file}")
        
        # Сохраняем человекочитаемый отчет
        summary_file = transcript_file.parent / "summary_manual.txt"
        agent._save_human_readable_report(result, summary_file)
        print(f"💾 Отчет сохранен: {summary_file}")
        
        # Показываем краткую сводку
        print("\n📊 КРАТКАЯ СВОДКА:")
        print(f"  Дата встречи: {result.get('meeting_date', 'Не указана')}")
        print(f"  Основные темы: {', '.join(result.get('key_topics', []))}")
        print(f"  Решений: {len(result.get('decisions', []))}")
        print(f"  Задач: {len(result.get('action_items', []))}")
        
        # Выводим полный результат для просмотра
        print("\n📄 ПОЛНЫЙ АНАЛИЗ:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    else:
        print(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        if "raw_response" in result:
            print(f"Ответ LLM: {result['raw_response'][:500]}")


if __name__ == "__main__":
    main()