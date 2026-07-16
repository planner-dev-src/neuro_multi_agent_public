from __future__ import annotations

import argparse
import json
from pathlib import Path

from .market_analysis_agent import MarketAnalysisAgent


def find_latest_market_agent_report() -> str | None:
    """Находит самый свежий отчёт market_agent в папке data/reports/market_agent/"""
    reports_dir = Path("data/reports/market_agent")
    if not reports_dir.exists():
        return None
    
    # Ищем файлы JSON с отчётами
    json_files = list(reports_dir.glob("market_agent_*.json"))
    if not json_files:
        return None
    
    # Берём самый свежий по времени создания
    latest = max(json_files, key=lambda x: x.stat().st_mtime)
    return str(latest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run market analysis agent")
    parser.add_argument(
        "--source-json",
        dest="source_json_path",
        default=None,
        help="Path to market_agent JSON report (if not specified, uses latest report)",
    )
    parser.add_argument(
        "--input-csv",
        dest="input_csv_path",
        default=None,
        help="Path to platforms CSV file (for direct analysis)",
    )
    args = parser.parse_args()

    # Определяем путь к исходным данным
    source_path = args.source_json_path
    
    # Если путь не указан, ищем последний отчёт
    if not source_path:
        latest = find_latest_market_agent_report()
        if latest:
            source_path = latest
            print(f"📁 Использую последний отчёт: {source_path}")
        else:
            print("⚠️ Не найден отчёт market_agent. Запустите market_agent сначала.")
            return

    # Создаём агента и запускаем анализ
    agent = MarketAnalysisAgent()
    result = agent.run(source_json_path=source_path)

    # result — это словарь
    print(f"\n✅ {result.get('message', 'Анализ завершен')}")
    print("\n📊 РЕЗУЛЬТАТЫ АНАЛИЗА:")
    print("=" * 60)
    
    payload = result.get("payload", {})
    
    # Выводим информацию о платформах из payload
    platforms_analyzed = payload.get("platforms_analyzed", 0)
    print(f"\n📈 Платформ проанализировано: {platforms_analyzed}")
    
    # Выводим тренды
    trends = payload.get("market_trends", [])
    if trends:
        print(f"\n📈 РЫНОЧНЫЕ ТРЕНДЫ:")
        for trend in trends[:5]:
            print(f"  • {trend}")
    
    # Выводим конкурентов
    competitors = payload.get("competitors", [])
    if competitors:
        print(f"\n🏢 КОНКУРЕНТЫ:")
        for comp in competitors[:5]:
            print(f"  • {comp.get('name', 'Unknown')}")
    
    # Выводим рекомендации
    recommendations = payload.get("recommendations", [])
    if recommendations:
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        for rec in recommendations[:5]:
            print(f"  • {rec}")
    
    # Выводим информацию о файлах
    files = result.get("files", {})
    if files:
        print("\n📁 СОХРАНЕННЫЕ ФАЙЛЫ:")
        for key, path in files.items():
            print(f"  • {key}: {path}")
    
    print("\n" + "=" * 60)
    print("✅ АНАЛИЗ ЗАВЕРШЕН!")


if __name__ == "__main__":
    main()