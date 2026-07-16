#!/usr/bin/env python
"""
Интеграционный тест всей системы
Запуск: python tests/integration/test_full_integration.py
"""

import sys
import json
from pathlib import Path

# Добавляем корневую папку проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.metrics_agent.metrics_agent import MetricsAgent
from src.agents.market_analysis_agent.market_analysis_agent import MarketAnalysisAgent
from src.agents.market_narrative_agent.market_narrative_agent import MarketNarrativeAgent
from src.agents.planner_agent.planner_agent import PlannerAgent
from src.agents.report_agent.report_agent import ReportAgent


def test_full_integration():
    """
    Запускает всех агентов и формирует итоговый отчет
    """
    
    print("=" * 80)
    print("🧪 ИНТЕГРАЦИОННЫЙ ТЕСТ ВСЕЙ СИСТЕМЫ")
    print("=" * 80)
    
    all_data = {}
    
    # 1. Metrics Agent
    print("\n📊 Шаг 1: Запуск Metrics Agent...")
    metrics_agent = MetricsAgent()
    metrics_agent.load_demo_metrics()
    
    all_data["metrics"] = {
        "metrics": metrics_agent.metrics,
        "competency_map": metrics_agent.build_competency_map(),
        "criteria_coverage": metrics_agent.analyze_criteria_coverage(),
        "impact_map": metrics_agent.build_impact_map(),
        "rag_chunks": metrics_agent.generate_rag_chunks()
    }
    print("✅ Metrics Agent завершен")
    
    # 2. Market Analysis Agent
    print("\n📈 Шаг 2: Запуск Market Analysis Agent...")
    market_agent = MarketAnalysisAgent()
    market_data = market_agent.collect_market_data()
    
    metrics_context = {"rag_chunks": all_data["metrics"]["rag_chunks"]}
    market_analysis = market_agent.analyze_with_metrics(market_data, metrics_context)
    all_data["market_analysis"] = market_analysis
    print("✅ Market Analysis Agent завершен")
    
    # 3. Market Narrative Agent
    print("\n📝 Шаг 3: Запуск Market Narrative Agent...")
    narrative_agent = MarketNarrativeAgent()
    narrative = narrative_agent.generate_narrative(market_analysis, metrics_context)
    all_data["market_narrative"] = {"full_text": narrative}
    print("✅ Market Narrative Agent завершен")
    
    # 4. Planner Agent
    print("\n📋 Шаг 4: Запуск Planner Agent...")
    planner_agent = PlannerAgent()
    plan = planner_agent.plan(
        metrics_data=all_data["metrics"],
        market_analysis=all_data["market_analysis"],
        narrative=narrative
    )
    all_data["planner"] = {
        "actions": [vars(a) for a in plan.actions],
        "summary": plan.summary,
        "priorities": plan.priorities,
        "timeline": plan.timeline,
        "risks": plan.risks,
        "success_criteria": plan.success_criteria
    }
    print("✅ Planner Agent завершен")
    
    # 5. Report Agent
    print("\n📄 Шаг 5: Формирование итогового отчета...")
    report_agent = ReportAgent()
    report = report_agent.generate_report(all_data)
    filepath = report_agent.save_report(report)
    print(f"✅ Отчет сохранен: {filepath}")
    
    # Вывод сводки
    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 80)
    
    metrics = all_data["metrics"]
    plan = all_data["planner"]
    
    print(f"\n📊 Метрики:")
    print(f"  • Покрытие критериев: {metrics['criteria_coverage'].get('overall_progress', 0):.1f}%")
    print(f"  • Пробелы в компетенциях: {metrics['competency_map'].get('gaps', [])}")
    
    print(f"\n📋 План:")
    print(f"  • Всего действий: {len(plan['actions'])}")
    print(f"  • Рисков: {len(plan['risks'])}")
    
    print("\n" + "=" * 80)
    print("✅ ИНТЕГРАЦИОННЫЙ ТЕСТ УСПЕШНО ЗАВЕРШЕН!")
    print("=" * 80)
    
    return all_data, report


def test_quick():
    """
    Быстрый тест - только Metrics + Planner + Report
    Для быстрой проверки
    """
    print("=" * 80)
    print("🧪 БЫСТРЫЙ ИНТЕГРАЦИОННЫЙ ТЕСТ")
    print("=" * 80)
    
    all_data = {}
    
    # 1. Metrics Agent
    print("\n📊 Запуск Metrics Agent...")
    metrics_agent = MetricsAgent()
    metrics_agent.load_demo_metrics()
    
    all_data["metrics"] = {
        "metrics": metrics_agent.metrics,
        "competency_map": metrics_agent.build_competency_map(),
        "criteria_coverage": metrics_agent.analyze_criteria_coverage(),
        "impact_map": metrics_agent.build_impact_map(),
        "rag_chunks": metrics_agent.generate_rag_chunks()
    }
    
    # 2. Market Analysis Agent (с демо-данными)
    print("\n📈 Запуск Market Analysis Agent...")
    market_agent = MarketAnalysisAgent()
    market_data = market_agent.collect_market_data()
    metrics_context = {"rag_chunks": all_data["metrics"]["rag_chunks"]}
    market_analysis = market_agent.analyze_with_metrics(market_data, metrics_context)
    all_data["market_analysis"] = market_analysis
    
    # 3. Planner Agent
    print("\n📋 Запуск Planner Agent...")
    planner_agent = PlannerAgent()
    plan = planner_agent.plan(
        metrics_data=all_data["metrics"],
        market_analysis=all_data["market_analysis"],
        narrative="Быстрый тест"
    )
    all_data["planner"] = {
        "actions": [vars(a) for a in plan.actions],
        "summary": plan.summary,
        "priorities": plan.priorities,
        "risks": plan.risks,
        "success_criteria": plan.success_criteria
    }
    
    # 4. Report Agent
    print("\n📄 Формирование отчета...")
    report_agent = ReportAgent()
    report = report_agent.generate_report(all_data)
    filepath = report_agent.save_report(report)
    
    print(f"\n✅ Отчет сохранен: {filepath}")
    print("✅ БЫСТРЫЙ ТЕСТ ЗАВЕРШЕН!")
    
    return all_data, report


def save_test_results(all_data: dict, report: dict):
    """
    Сохраняет результаты теста в файл для анализа
    """
    results_dir = project_root / "tests" / "integration" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Сохраняем все данные
    with open(results_dir / f"test_results_{timestamp}.json", 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Результаты сохранены: {results_dir / f'test_results_{timestamp}.json'}")


if __name__ == "__main__":
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="Интеграционные тесты")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Быстрый тест (только Metrics + Planner + Report)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Сохранить результаты в файл"
    )
    args = parser.parse_args()
    
    if args.quick:
        all_data, report = test_quick()
    else:
        all_data, report = test_full_integration()
    
    if args.save:
        save_test_results(all_data, report)