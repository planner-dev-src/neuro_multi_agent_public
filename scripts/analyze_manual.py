#!/usr/bin/env python
"""
Ручной анализ конкретного транскрипта
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.secretary_agent.secretary_agent import SecretaryAgent


def main():
    # Указываем путь напрямую
    transcript_file = Path(
        "src/agents/secretary_agent/transcription_results/meeting_ceo_audio/transcript_20260710_161630.txt"
    )
    
    if not transcript_file.exists():
        print(f"❌ Файл не найден: {transcript_file}")
        return
    
    print(f"📄 Файл: {transcript_file}")
    
    with open(transcript_file, 'r', encoding='utf-8') as f:
        transcript = f.read()
    
    print(f"📄 Транскрипт: {len(transcript)} символов")
    print("🧠 Запуск LLM-анализа...")
    
    agent = SecretaryAgent()
    result = agent._llm_analyze_transcript(transcript)
    
    if result.get("success"):
        print("✅ Анализ выполнен!")
        
        output_file = transcript_file.parent / "analysis_manual.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 Сохранено: {output_file}")
        
        print("\n📊 РЕЗУЛЬТАТ:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"❌ Ошибка: {result.get('error')}")


if __name__ == "__main__":
    main()