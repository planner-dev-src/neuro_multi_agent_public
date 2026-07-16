"""Оркестратор полного пайплайна.

Режимы:
- full: все агенты → RAG → planner → отчёт
- market_only: только сбор и анализ рынка
- analyze: только analysis существующих данных
- research: запуск research_agent по запросу

Пример:
    python src/orchestrators/workflow.py
    python src/orchestrators/workflow.py --mode market_only
    python src/orchestrators/workflow.py --research "тренды AI в образовании 2026"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.agents.market_analysis_agent import run_market_analysis
from src.agents.market_narrative_agent.market_narrative_agent import MarketNarrativeAgent
from src.agents.metrics_agent.metrics_agent import run_metrics_agent
from src.agents.planner_agent.planner_agent import run_planner
from src.agents.report_agent.report_agent import ReportAgent
from src.agents.research_agent.research_agent import ResearchAgent
from src.agents.secretary_agent.secretary_agent import run_secretary_agent
from src.common.rag_store import RAGStore
from src.orchestrators.router import get_agent


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _chunks_to_dicts(chunks: list) -> list[dict]:
    """Конвертирует RAGChunk-объекты в словари для RAGStore."""
    result = []
    for c in chunks:
        if isinstance(c, dict):
            result.append(c)
        elif is_dataclass(c):
            result.append(asdict(c))
        elif hasattr(c, '__dict__'):
            result.append({
                'chunk_id': getattr(c, 'chunk_id', ''),
                'text': getattr(c, 'text', ''),
                'source': getattr(c, 'source', ''),
                'section': getattr(c, 'section', ''),
                'title': getattr(c, 'title', ''),
                'metadata': getattr(c, 'metadata', {}),
            })
    return result


def _load_latest_gaps() -> list[dict[str, str]]:
    """Загружает последний competitive_gaps CSV."""
    gaps_dir = Path("data/reports/market_analysis_agent")
    files = sorted(gaps_dir.glob("competitive_gaps_*.csv"), key=lambda p: p.stat().st_mtime)
    if files:
        with open(files[-1], "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    return []


def _load_latest_narrative() -> str:
    """Загружает последний нарратив из файла market_narrative_agent."""
    narrative_file = Path("src/agents/market_narrative_agent/results/narrative_latest.txt")
    if narrative_file.exists():
        try:
            with open(narrative_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"⚠️ Ошибка загрузки нарратива: {e}")
    return ""


# ---------------------------------------------------------------------------
# Полный пайплайн
# ---------------------------------------------------------------------------

def run_full_pipeline(
    *,
    source_json_path: str | None = None,
    metrics_path: str | None = None,
    meeting_json_path: str | None = None,
    use_llm: bool = True,
    research_query: str | None = None,
    research_max_results: int = 10,
) -> dict:
    """Запускает полный пайплайн.

    1. research_agent (по запросу руководителя, если указан)
    2. research_agent (фоновый сбор)
    3. secretary_agent → стратегия
    4. market_agent → market_analysis_agent → тренды, gap-зоны
    5. market_narrative_agent → нарратив
    6. metrics_agent → внутренние метрики + критерии
    7. Все чанки → RAG
    8. planner_agent → рекомендации
    9. report_agent → итоговый отчёт
    """
    print("=" * 60)
    print("ЗАПУСК ПОЛНОГО ПАЙПЛАЙНА")
    print("=" * 60)

    store = RAGStore()
    narrative_text = ""
    report_data = {}
    research_report = None
    metrics_result = None
    market_summary = {}

    # -----------------------------------------------------------------------
    # 0. Research Agent — по запросу руководителя (если указан)
    # -----------------------------------------------------------------------
    if research_query:
        print(f"\n[0/8] research_agent (поиск по запросу: '{research_query}')...")
        try:
            research_agent = ResearchAgent()
            research_result = research_agent.search_and_report(
                query=research_query,
                max_results=research_max_results,
                max_crawl_pages=5,
                generate_report=True,
                save_report=True,
            )
            
            if research_result.get("rag_chunks"):
                added = store.index_chunks(_chunks_to_dicts(research_result["rag_chunks"]))
                print(f"  Добавлено чанков в RAG: {added}")
            
            research_report = {
                "query": research_query,
                "report": research_result.get("report", ""),
                "report_path": research_result.get("report_path"),
                "sources": research_result.get("sources", []),
                "sources_count": research_result.get("sources_count", 0),
                "chunks_count": research_result.get("chunks_count", 0),
                "status": research_result.get("status", "completed"),
                "crawled_count": research_result.get("crawled_count", 0)
            }
            report_data["research"] = research_report
            
            print(f"  Найдено источников: {research_result.get('sources_count', 0)}")
            print(f"  Обработано страниц: {research_result.get('crawled_count', 0)}")
            print(f"  Чанков в RAG: {store.count}")
            if research_result.get("report_path"):
                print(f"  Отчёт: {research_result['report_path']}")
                
        except Exception as e:
            print(f"  ⚠️ Ошибка research_agent: {e}")
            research_report = {"error": str(e), "query": research_query}

    # -----------------------------------------------------------------------
    # 0.5 Research Agent — фоновый сбор (всегда запускается)
    # -----------------------------------------------------------------------
    print("\n[0.5/8] research_agent (фоновый сбор)...")
    try:
        research_agent = ResearchAgent()
        research_result = research_agent.run_background_collection(max_items=5)
        if research_result.get("rag_chunks"):
            added = store.index_chunks(_chunks_to_dicts(research_result["rag_chunks"]))
            print(f"  Добавлено чанков в RAG: {added}")
        print(f"  Фоновый сбор завершён, чанков в RAG: {store.count}")
    except Exception as e:
        print(f"  ⚠️ Ошибка фонового сбора: {e}")

    # -----------------------------------------------------------------------
    # 1. Secretary Agent
    # -----------------------------------------------------------------------
    print("\n[1/8] secretary_agent...")
    try:
        secretary_result = run_secretary_agent(
            mode="load",
            meeting_json_path=meeting_json_path,
        )
        
        if secretary_result.get("success"):
            added = store.index_chunks(_chunks_to_dicts(secretary_result.get("rag_chunks", [])))
            meeting = secretary_result.get("meeting", {})
            print(f"  Решения: {len(meeting.get('key_decisions', []))}")
            print(f"  Поручения: {len(meeting.get('assigned_tasks', []))}")
            print(f"  Чанков в RAG: {store.count} (+{added})")
            report_data["secretary"] = secretary_result
        else:
            print(f"  ⚠️ secretary_agent: {secretary_result.get('error', 'Неизвестная ошибка')}")
            report_data["secretary"] = {"error": secretary_result.get('error', 'Unknown')}
            
    except Exception as e:
        print(f"  ⚠️ Ошибка secretary_agent: {e}")
        report_data["secretary"] = {"error": str(e)}

    # -----------------------------------------------------------------------
    # 2. Market Agent + Market Analysis Agent
    # -----------------------------------------------------------------------
    print("\n[2/8] market_agent + market_analysis_agent...")
    try:
        market_result = run_market_analysis(source_json_path=source_json_path)
        
        bundle = market_result.get("bundle")
        if bundle and hasattr(bundle, "rag_chunks"):
            added = store.index_chunks(_chunks_to_dicts(bundle.rag_chunks))
            print(f"  Добавлено чанков в RAG: {added}")
        
        market_summary = market_result.get("summary", {})
        print(f"  Платформ: {market_summary.get('platforms_total', '?')}")
        print(f"  Курсов после очистки: {market_summary.get('catalog_items_total_kept', '?')}")
        print(f"  Трендов: {market_summary.get('trend_signals_total', '?')}")
        print(f"  Gap-зон: {market_summary.get('competitive_gaps_total', '?')}")
        print(f"  Чанков в RAG: {store.count}")
        
        report_data["market_analysis"] = market_result
        
    except Exception as e:
        print(f"  ⚠️ Ошибка market_analysis: {e}")
        market_result = {}
        market_summary = {}
        report_data["market_analysis"] = {"error": str(e)}

    # -----------------------------------------------------------------------
    # 3. Market Narrative Agent
    # -----------------------------------------------------------------------
    print("\n[3/8] market_narrative_agent...")
    try:
        narrative_agent = MarketNarrativeAgent()
        narrative_result = narrative_agent.generate_narrative(
            market_analysis=market_result,
            metrics_data=metrics_result
        )
        narrative_text = narrative_result.get("narrative", "")
        print(f"  Нарратив сгенерирован: {len(narrative_text)} символов")
        report_data["market_narrative"] = {"full_text": narrative_text}
    except Exception as e:
        print(f"  ⚠️ Ошибка market_narrative_agent: {e}")
        narrative_text = _load_latest_narrative()
        report_data["market_narrative"] = {"full_text": narrative_text, "error": str(e)}

    # -----------------------------------------------------------------------
    # 4. Metrics Agent — ИСПРАВЛЕННАЯ ВЕРСИЯ
    # -----------------------------------------------------------------------
    print("\n[4/8] metrics_agent...")
    try:
        gaps_data = _load_latest_gaps()
        metrics_result = run_metrics_agent(
            metrics_path=metrics_path,
            gaps=gaps_data,
        )
        
        if metrics_result.get("status") == "completed":
            rag_chunks = metrics_result.get("rag_chunks", [])
            added = store.index_chunks(_chunks_to_dicts(rag_chunks))
            
            metrics_data = metrics_result.get("metrics_data", {})
            competency_map = metrics_result.get("competency_map", {})
            criteria = metrics_result.get("criteria_assessment", {})
            impact_map = metrics_result.get("impact_map", {})
            
            print(f"  Всего метрик: {metrics_data.get('total', 0)}")
            print(f"  Критических: {len(metrics_data.get('critical', []))}")
            print(f"  Критериев: {criteria.get('total', 0)}")
            print(f"  Чанков в RAG: {store.count} (+{added})")
            
            # ✅ Сохраняем только словарь, НЕ объект MetricsAgent
            metrics_dict = {
                "metrics_data": metrics_data,
                "competency_map": competency_map,
                "criteria_assessment": criteria,
                "impact_map": impact_map,
                "rag_chunks": rag_chunks,
                "status": "completed"
            }
            report_data["metrics"] = metrics_dict
            metrics_result = metrics_dict  # ← тоже словарь для planner_agent
        else:
            error_msg = metrics_result.get('error', 'Неизвестная ошибка')
            print(f"  ⚠️ metrics_agent: {error_msg}")
            metrics_dict = {"error": error_msg, "status": "failed"}
            report_data["metrics"] = metrics_dict
            metrics_result = metrics_dict
            
    except Exception as e:
        print(f"  ⚠️ Ошибка metrics_agent: {e}")
        metrics_dict = {"error": str(e), "status": "failed"}
        report_data["metrics"] = metrics_dict
        metrics_result = metrics_dict

    # -----------------------------------------------------------------------
    # 5. Planner Agent
    # -----------------------------------------------------------------------
    print("\n[5/8] planner_agent...")
    try:
        planner_result = run_planner(
            metrics=metrics_result,
            gaps_csv_path=None,
            trends_csv_path=None,
        )
        
        if planner_result:
            added = store.index_chunks(_chunks_to_dicts(getattr(planner_result, 'rag_chunks', [])))
            print(f"  Рекомендаций по ролям: {len(getattr(planner_result, 'role_recommendations', []))}")
            print(f"  Рекомендаций по продуктам: {len(getattr(planner_result, 'product_recommendations', []))}")
            print(f"  Чанков в RAG: {store.count} (+{added})")
            report_data["planner"] = planner_result
        else:
            print("  ⚠️ planner_agent: результат пустой")
            report_data["planner"] = {"error": "Пустой результат"}
            
    except Exception as e:
        print(f"  ⚠️ Ошибка planner_agent: {e}")
        report_data["planner"] = {"error": str(e)}

    # -----------------------------------------------------------------------
    # 6. Report Agent (итоговый отчёт)
    # -----------------------------------------------------------------------
    print("\n[6/8] report_agent...")
    try:
        report_agent = ReportAgent(use_llm=use_llm)
        report = report_agent.generate_report(report_data)
        report_path = report_agent.save_report(report)
        print(f"  Отчёт сохранён: {report_path}")
    except Exception as e:
        print(f"  ⚠️ Ошибка report_agent: {e}")
        report = {"error": str(e)}
        report_path = None

    # -----------------------------------------------------------------------
    # Результат
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("ПАЙПЛАЙН ЗАВЕРШЁН")
    print("=" * 60)
    print(f"RAG: {store.count} чанков")
    if report_path:
        print(f"Отчёт: {report_path}")
    if research_query and research_report and not research_report.get("error"):
        print(f"Исследование: {research_query}")

    return {
        "status": "completed",
        "rag_count": store.count,
        "report_path": str(report_path) if report_path else None,
        "report": report,
        "research": research_report,
        "narrative": narrative_text,
    }


# ---------------------------------------------------------------------------
# Режимы запуска
# ---------------------------------------------------------------------------

def run_market_only() -> dict:
    """Запускает только market_agent."""
    print("=" * 60)
    print("ЗАПУСК MARKET ONLY")
    print("=" * 60)
    
    market_agent = get_agent("market_agent")
    result = market_agent.run()
    print(f"market_agent: {result.message}")
    
    return {"status": "completed", "result": result}


def run_analyze(source_json_path: str | None = None) -> dict:
    """Запускает только анализ рынка."""
    print("=" * 60)
    print("ЗАПУСК ANALYZE")
    print("=" * 60)
    
    result = run_market_analysis(source_json_path=source_json_path)
    summary = result.get("summary", {})
    
    print(f"Платформ: {summary.get('platforms_total')}")
    print(f"Курсов: {summary.get('catalog_items_total_kept')}")
    print(f"Трендов: {summary.get('trend_signals_total')}")
    print(f"Gap-зон: {summary.get('competitive_gaps_total')}")
    
    return {"status": "completed", "summary": summary}


def run_research_only(query: str, max_results: int = 10) -> dict:
    """Запускает только research_agent по запросу."""
    print("=" * 60)
    print(f"ЗАПУСК RESEARCH: '{query}'")
    print("=" * 60)
    
    research_agent = ResearchAgent()
    result = research_agent.search_and_report(
        query=query,
        max_results=max_results,
        max_crawl_pages=5,
        generate_report=True,
        save_report=True,
    )
    
    print(f"Найдено источников: {result.get('sources_count', 0)}")
    print(f"Обработано страниц: {result.get('crawled_count', 0)}")
    print(f"Сгенерировано чанков: {result.get('chunks_count', 0)}")
    if result.get('report_path'):
        print(f"Отчёт: {result['report_path']}")
    
    return {"status": "completed", "result": result}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Оркестратор полного пайплайна",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Режимы:
  full          Полный пайплайн (все агенты)
  market_only   Только сбор и анализ рынка
  analyze       Только анализ существующих данных
  research      Только research_agent по запросу

Примеры:
  python src/orchestrators/workflow.py
  python src/orchestrators/workflow.py --mode market_only
  python src/orchestrators/workflow.py --mode research --research "тренды AI 2026"
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "market_only", "analyze", "research"],
        default="full",
        help="Режим запуска (по умолчанию: full)",
    )
    
    parser.add_argument("--source-json", default=None, help="Путь к JSON market_agent")
    parser.add_argument("--metrics-json", default=None, help="Путь к JSON метрик")
    parser.add_argument("--meeting-json", default=None, help="Путь к JSON совещания")
    parser.add_argument("--no-llm", action="store_true", help="Отключить LLM")
    
    parser.add_argument(
        "--research",
        type=str,
        help="Запрос для research_agent (в режиме full или research)",
    )
    parser.add_argument(
        "--research-max",
        type=int,
        default=10,
        help="Максимум результатов для research (по умолчанию: 10)",
    )
    
    args = parser.parse_args()
    
    if args.mode == "full":
        run_full_pipeline(
            source_json_path=args.source_json,
            metrics_path=args.metrics_json,
            meeting_json_path=args.meeting_json,
            use_llm=not args.no_llm,
            research_query=args.research,
            research_max_results=args.research_max,
        )
    
    elif args.mode == "market_only":
        run_market_only()
    
    elif args.mode == "analyze":
        run_analyze(source_json_path=args.source_json)
    
    elif args.mode == "research":
        if not args.research:
            print("❌ Ошибка: укажите --research 'запрос'")
            sys.exit(1)
        run_research_only(query=args.research, max_results=args.research_max)


if __name__ == "__main__":
    main()