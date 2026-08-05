"""
Веб-интерфейс для мультиагентной системы
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime
import sys
import os
import json
import asyncio
import traceback
import re

# Добавляем путь к проекту для импорта агентов
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

app = FastAPI(title="AI-Ассистент Руководителя")

# Пути
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _get_iso_date(filepath: Path) -> str:
    """Возвращает ISO-дату модификации файла"""
    return datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()


def _check_ollama() -> bool:
    """Проверяет доступность Ollama"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def _query_ollama(prompt: str, system_prompt: str = "", timeout: int = 60) -> str:
    """Отправляет запрос в Ollama и возвращает ответ"""
    import requests
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "system": system_prompt or "Ты — AI-ассистент руководителя компании. Отвечай кратко, по делу, на русском языке.",
                "stream": False,
                "temperature": 0.3,
                "options": {
                    "num_predict": 1024,
                    "top_k": 40,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                }
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "")
        else:
            return ""
    except Exception as e:
        print(f"[Ollama] Ошибка: {e}")
        return ""


def _search_rag(query: str, max_chunks: int = 5) -> list:
    """Ищет релевантные чанки в RAG"""
    try:
        from src.common.rag_store import RAGStore
        store = RAGStore()
        results = store.search(query, top_k=max_chunks)
        return results if results else []
    except Exception as e:
        print(f"[RAG] Ошибка поиска: {e}")
        return []


def _classify_intent(message: str) -> dict:
    """
    Двухуровневая классификация намерений.
    Уровень 1: ключевые слова (быстро, всегда доступно)
    Уровень 2: LLM/Ollama (точно, если доступно)
    """
    try:
        from src.common.intent_classifier import classify_intent
        return classify_intent(message)
    except ImportError:
        pass
    
    # Fallback: простая классификация по ключевым словам
    return _simple_intent_classify(message)


def _simple_intent_classify(message: str) -> dict:
    """Простая классификация по ключевым словам (без отдельного модуля)"""
    message_lower = message.lower()
    
    # Проверяем паттерны создания задачи
    task_patterns = [
        r'созда(й|ть|йте)\s+задач', r'добав(ь|ить|ьте)\s+задач',
        r'постав(ь|ить|ьте)\s+задач', r'поруч', r'назнач(ь|ить|ьте)',
        r'запланиру(й|ем|йте)', r'сдела(й|ть)\s+задач'
    ]
    for p in task_patterns:
        if re.search(p, message_lower):
            return {"intent": "create_task", "confidence": 0.85, "method": "keywords", "params": {}}
    
    # Проверяем паттерны запроса плана
    plan_patterns = [
        r'покажи\s+план', r'какой\s+план', r'что\s+делать',
        r'текущие\s+задач', r'список\s+задач', r'активные\s+задач',
        r'мой\s+план', r'какие\s+задач', r'статус\s+(задач|проекта)'
    ]
    for p in plan_patterns:
        if re.search(p, message_lower):
            return {"intent": "show_plan", "confidence": 0.85, "method": "keywords", "params": {}}
    
    # Проверяем паттерны исследования
    research_patterns = [
        r'исследу(й|ем|йте)', r'найди\s+информаци', r'поищи',
        r'тренды?\s+(в|на|по)', r'анализ\s+рынк', r'конкуренты',
        r'расскажи\s+(о|про)', r'сдела(й|те)\s+обзор'
    ]
    for p in research_patterns:
        if re.search(p, message_lower):
            return {"intent": "research", "confidence": 0.8, "method": "keywords", "params": {}}
    
    return {"intent": "question", "confidence": 0.5, "method": "keywords", "params": {}}


def _get_tasks_context() -> str:
    """Получает контекст из текущих задач"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        registry = MetricsRegistry()
        decisions = registry.get_all_decisions()
        
        if not decisions:
            return "Задач нет."
        
        lines = ["ТЕКУЩИЕ ЗАДАЧИ:"]
        for d in decisions[:10]:
            priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(d.priority, "⚪")
            assignee = f" → {d.assignee}" if d.assignee else ""
            deadline = f" (до {d.deadline})" if d.deadline else ""
            lines.append(f"{priority_emoji} {d.description}{assignee}{deadline}")
        
        return "\n".join(lines)
    except Exception as e:
        print(f"[Tasks] Ошибка получения задач: {e}")
        return "Ошибка загрузки задач."


def _get_plan_context() -> str:
    """Получает контекст из последнего плана действий"""
    try:
        planner_dir = PROJECT_ROOT / "src" / "agents" / "planner_agent" / "results"
        if not planner_dir.exists():
            return ""
        
        plan_files = sorted(planner_dir.glob("plan_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not plan_files:
            return ""
        
        with open(plan_files[0], 'r', encoding='utf-8') as f:
            plan = json.load(f)
        
        lines = ["ПЛАН ДЕЙСТВИЙ:"]
        if plan.get("summary"):
            lines.append(f"Сводка: {plan['summary']}")
        
        actions = plan.get("actions", [])
        if actions:
            lines.append("\nДействия:")
            for a in actions[:10]:
                priority = a.get("priority", "medium")
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                lines.append(f"{emoji} {a.get('description', '')}")
        
        return "\n".join(lines)
    except Exception as e:
        print(f"[Plan] Ошибка получения плана: {e}")
        return ""


# ============================================================
# API
# ============================================================

@app.get("/api/dashboard")
async def get_dashboard_data():
    """Возвращает данные для дашборда из последнего отчёта"""
    try:
        reports_dir = PROJECT_ROOT / "src" / "agents" / "report_agent" / "reports"
        files = sorted(reports_dir.glob("report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if files:
            with open(files[0], 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            level_analysis = report.get("level_analysis", {})
            
            strategic = level_analysis.get("strategic", {})
            metrics = strategic.get("metrics", [])
            ai_projects = 0
            for m in metrics:
                if "AI проекты" in m.get("name", ""):
                    ai_projects = m.get("current", 0)
                    break
            
            market = level_analysis.get("market", {})
            competitors = market.get("competitors_analyzed", 0)
            
            competency = level_analysis.get("competency", {})
            comp_list = competency.get("competencies", [])
            critical = sum(1 for c in comp_list if c.get("status") == "critical")
            
            plan = report.get("plan", {})
            tasks = plan.get("tasks", [])
            active_tasks = len([t for t in tasks if t.get("priority") in ["critical", "high"]])
            
            rag_chunks = 0
            try:
                rag_dir = PROJECT_ROOT / "src" / "common" / "rag_data"
                if rag_dir.exists():
                    for f in rag_dir.glob("*.json"):
                        try:
                            with open(f, 'r', encoding='utf-8') as rf:
                                rag_chunks += len(json.load(rf))
                        except:
                            pass
            except:
                rag_chunks = 0
            
            return {
                "strategic": {"current": ai_projects if ai_projects > 0 else 750, "target": 1000, "percent": round(ai_projects / 1000 * 100) if ai_projects > 0 else 75},
                "market": {"current": competitors if competitors > 0 else 6, "total": 14},
                "competency": {"critical": critical, "total": len(comp_list) if comp_list else 50},
                "tasks": {"active": active_tasks},
                "rag": {"chunks": rag_chunks}
            }
        else:
            return {
                "strategic": {"current": 750, "target": 1000, "percent": 75},
                "market": {"current": 6, "total": 14},
                "competency": {"critical": 3, "total": 50},
                "tasks": {"active": 0},
                "rag": {"chunks": 0}
            }
    except Exception as e:
        print(f"[API] Ошибка получения данных дашборда: {e}")
        return {
            "strategic": {"current": 750, "target": 1000, "percent": 75},
            "market": {"current": 6, "total": 14},
            "competency": {"critical": 3, "total": 50},
            "tasks": {"active": 0},
            "rag": {"chunks": 0}
        }


@app.get("/api/reports/list")
async def get_reports_list():
    """Возвращает список отчётов в логическом порядке"""
    reports = []
    
    try:
        reports_dir = PROJECT_ROOT / "src" / "agents" / "report_agent" / "reports"
        if reports_dir.exists():
            files = sorted(reports_dir.glob("report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for f in files[:1]:
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    reports.append({
                        "name": f.name, "date": _get_iso_date(f),
                        "title": data.get("header", {}).get("title", "Итоговый управленческий отчёт"),
                        "type": "full_report", "type_label": "📊 Итоговый отчёт",
                        "icon": "fas fa-file-alt", "order": 1
                    })
                except:
                    reports.append({
                        "name": f.name, "date": _get_iso_date(f),
                        "title": "Итоговый управленческий отчёт",
                        "type": "full_report", "type_label": "📊 Итоговый отчёт",
                        "icon": "fas fa-file-alt", "order": 1
                    })
    except Exception as e:
        print(f"[API] Ошибка сбора итоговых отчётов: {e}")
    
    try:
        secretary_dir = PROJECT_ROOT / "src" / "agents" / "secretary_agent" / "transcription_results"
        if secretary_dir.exists():
            summary_files = list(secretary_dir.rglob("summary_*.txt"))
            if summary_files:
                summary_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                sf = summary_files[0]
                analysis_file = sf.parent / sf.name.replace("summary_", "analysis_").replace(".txt", ".json")
                meeting_title = "Сводка совещания"
                if analysis_file.exists():
                    try:
                        with open(analysis_file, 'r', encoding='utf-8') as fp:
                            analysis_data = json.load(fp)
                        if analysis_data.get("summary"):
                            meeting_title = analysis_data["summary"][:80]
                    except:
                        pass
                reports.append({
                    "name": sf.name, "date": _get_iso_date(sf),
                    "title": f"Сводка совещания: {meeting_title}",
                    "type": "meeting", "type_label": "🎙️ Сводка совещания",
                    "icon": "fas fa-microphone-alt", "path": str(sf), "order": 2
                })
    except Exception as e:
        print(f"[API] Ошибка сбора сводок совещаний: {e}")
    
    try:
        narrative_dir = PROJECT_ROOT / "src" / "agents" / "market_narrative_agent" / "results"
        if narrative_dir.exists():
            narrative_files = sorted(narrative_dir.glob("narrative_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
            if narrative_files:
                nf = narrative_files[0]
                reports.append({
                    "name": nf.name, "date": _get_iso_date(nf),
                    "title": "Аналитический обзор рынка",
                    "type": "narrative", "type_label": "📝 Аналитический обзор",
                    "icon": "fas fa-chart-line", "path": str(nf), "order": 3
                })
    except Exception as e:
        print(f"[API] Ошибка сбора нарративов: {e}")
    
    try:
        planner_dir = PROJECT_ROOT / "src" / "agents" / "planner_agent" / "results"
        if planner_dir.exists():
            plan_files = sorted(planner_dir.glob("plan_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if plan_files:
                pf = plan_files[0]
                try:
                    with open(pf, 'r', encoding='utf-8') as fp:
                        plan_data = json.load(fp)
                    summary_short = plan_data.get('summary', '')[:60]
                    reports.append({
                        "name": pf.name, "date": _get_iso_date(pf),
                        "title": f"План действий{f' — {summary_short}' if summary_short else ''}",
                        "type": "plan", "type_label": "📋 План действий",
                        "icon": "fas fa-tasks", "order": 4
                    })
                except:
                    reports.append({
                        "name": pf.name, "date": _get_iso_date(pf),
                        "title": "План действий",
                        "type": "plan", "type_label": "📋 План действий",
                        "icon": "fas fa-tasks", "order": 4
                    })
    except Exception as e:
        print(f"[API] Ошибка сбора планов: {e}")
    
    reports.sort(key=lambda r: r.get("order", 99))
    print(f"[API] Всего отчётов собрано: {len(reports)}")
    return {"reports": reports}


@app.get("/api/reports/content/{report_name}")
async def get_report_content(report_name: str):
    """Возвращает содержимое отчёта по имени файла"""
    try:
        possible_paths = [
            PROJECT_ROOT / "src" / "agents" / "report_agent" / "reports" / report_name,
            PROJECT_ROOT / "src" / "agents" / "planner_agent" / "results" / report_name,
            PROJECT_ROOT / "src" / "agents" / "market_narrative_agent" / "results" / report_name,
        ]
        
        secretary_dir = PROJECT_ROOT / "src" / "agents" / "secretary_agent" / "transcription_results"
        if secretary_dir.exists():
            for sf in secretary_dir.rglob(report_name):
                possible_paths.append(sf)
                break
        
        report_path = None
        for path in possible_paths:
            if path.exists():
                report_path = path
                break
        
        if not report_path:
            return {"error": f"Отчёт не найден: {report_name}"}
        
        if report_path.suffix == '.txt':
            with open(report_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            is_meeting = "secretary_agent" in str(report_path)
            title = "Сводка совещания" if is_meeting else "Аналитический обзор рынка"
            return {
                "header": {"title": title, "date": _get_iso_date(report_path)},
                "executive_summary": "", "narrative": text_content,
                "level_analysis": {}, "recommendations": {}, "plan": {}, "conclusion": ""
            }
        
        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "actions" in data and "summary" in data:
            actions_text = ""
            for action in data.get("actions", [])[:10]:
                priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(action.get("priority", ""), "⚪")
                actions_text += f"{priority_emoji} {action.get('description', '')}\n"
            return {
                "header": {"title": "План действий", "date": _get_iso_date(report_path)},
                "executive_summary": data.get("summary", ""), "narrative": actions_text,
                "level_analysis": {}, "recommendations": {},
                "plan": {"tasks": data.get("actions", [])},
                "conclusion": f"Всего действий: {len(data.get('actions', []))}"
            }
        
        if "main_theses" in data or "decisions" in data or "action_items" in data:
            narrative = ""
            if data.get("main_theses"):
                narrative += "📌 ОСНОВНЫЕ ТЕЗИСЫ\n" + "=" * 40 + "\n"
                for t in data["main_theses"]: narrative += f"• {t}\n"
                narrative += "\n"
            if data.get("decisions"):
                narrative += "📋 ПРИНЯТЫЕ РЕШЕНИЯ\n" + "=" * 40 + "\n"
                for d in data["decisions"]:
                    narrative += f"• {d.get('decision', d) if isinstance(d, dict) else d}\n"
                narrative += "\n"
            if data.get("action_items"):
                narrative += "✅ ПОРУЧЕНИЯ\n" + "=" * 40 + "\n"
                for t in data["action_items"]:
                    if isinstance(t, dict):
                        narrative += f"• {t.get('task', t)}"
                        if t.get('assignee'): narrative += f" → {t['assignee']}"
                        narrative += "\n"
                    else:
                        narrative += f"• {t}\n"
                narrative += "\n"
            if data.get("risks"):
                narrative += "⚠️ РИСКИ\n" + "=" * 40 + "\n"
                for r in data["risks"]:
                    narrative += f"• {r.get('risk', r) if isinstance(r, dict) else r}\n"
            return {
                "header": {"title": "Сводка совещания", "date": _get_iso_date(report_path)},
                "executive_summary": data.get("summary", ""),
                "narrative": narrative if narrative else str(data)[:5000],
                "level_analysis": {}, "recommendations": {}, "plan": {}, "conclusion": ""
            }
        
        return {
            "header": data.get("header", {}),
            "executive_summary": data.get("executive_summary", ""),
            "secretary_input": data.get("secretary_input", {}),
            "narrative": data.get("narrative", {}).get("full_text", ""),
            "level_analysis": data.get("level_analysis", {}),
            "recommendations": data.get("recommendations", {}),
            "plan": data.get("plan", {}),
            "conclusion": data.get("conclusion", ""),
            "research_section": data.get("research_section", {})
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Возвращает сводку по 5 уровням из всех метрик"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        registry = MetricsRegistry()
        all_metrics_dict = registry.get_all_metrics()
        all_metrics = list(all_metrics_dict.values())
        
        levels = {
            "strategic": {"name": "Стратегический", "icon": "🎯", "metrics": []},
            "market": {"name": "Рыночный", "icon": "🌍", "metrics": []},
            "products": {"name": "Продуктовый", "icon": "📦", "metrics": []},
            "competency": {"name": "Компетенции", "icon": "🧠", "metrics": []},
            "technical": {"name": "Технический", "icon": "⚙️", "metrics": []}
        }
        
        for m in all_metrics:
            if m.level in levels:
                levels[m.level]["metrics"].append(m)
        
        summary = []
        for level_key, level_data in levels.items():
            metrics = level_data["metrics"]
            total = len(metrics)
            critical = sum(1 for m in metrics if m.status == "critical")
            warning = sum(1 for m in metrics if m.status == "warning")
            met = sum(1 for m in metrics if m.status in ["met", "exceeded"])
            summary.append({
                "level": level_key, "name": level_data["name"], "icon": level_data["icon"],
                "total": total, "critical": critical, "warning": warning, "met": met
            })
        
        return {"summary": summary}
    except Exception as e:
        print(f"[API] Ошибка получения сводки метрик: {e}")
        return {"summary": [], "error": str(e)}


@app.get("/api/metrics/all")
async def get_all_metrics():
    """Возвращает все метрики с деталями"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        registry = MetricsRegistry()
        metrics_dict = registry.get_all_metrics()
        metrics = list(metrics_dict.values())
        
        result = []
        for m in metrics:
            value = m.value
            if isinstance(value, str):
                try:
                    value = float(value.replace(',', '.'))
                except ValueError:
                    pass
            result.append({
                "id": m.id, "name": m.name, "level": m.level,
                "value": value, "target": m.target, "unit": m.unit,
                "status": m.status, "interpretation": m.interpretation
            })
        
        return {"metrics": result}
    except Exception as e:
        print(f"[API] Ошибка получения всех метрик: {e}")
        return {"metrics": [], "error": str(e)}


@app.get("/api/tasks/list")
async def get_tasks_list():
    """Возвращает список задач из плана действий"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        registry = MetricsRegistry()
        decisions = registry.get_all_decisions()
        tasks = []
        for d in decisions:
            tasks.append({
                "id": d.id, "title": d.description,
                "assignee": d.assignee or "Не назначен",
                "deadline": d.deadline or "Не указан",
                "priority": d.priority
            })
        return {"tasks": tasks}
    except Exception as e:
        print(f"[API] Ошибка получения задач: {e}")
        return {"tasks": [], "error": str(e)}


@app.get("/api/research/list")
async def get_research_list():
    """Возвращает список последних исследований"""
    try:
        research_dir = PROJECT_ROOT / "data" / "reports" / "research"
        if not research_dir.exists():
            return {"research": []}
        files = sorted(research_dir.glob("research_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        research = []
        for f in files[:5]:
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    query = data.get('query', f.name)
                    research.append({
                        "query": query, "path": str(f),
                        "date": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    })
            except:
                pass
        return {"research": research}
    except Exception as e:
        return {"research": [], "error": str(e)}


@app.get("/api/research/content")
async def get_research_content(path: str):
    """Возвращает содержимое исследования по пути к файлу"""
    try:
        from pathlib import Path
        file_path = Path(path)
        if not file_path.exists():
            return {"error": f"Файл не найден: {path}"}
        if not file_path.suffix == '.json':
            return {"error": "Поддерживаются только JSON-файлы"}
        research_dir = PROJECT_ROOT / "data" / "reports" / "research"
        if not str(file_path.resolve()).startswith(str(research_dir.resolve())):
            return {"error": "Доступ запрещён"}
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            "query": data.get("query", ""), "timestamp": data.get("timestamp", ""),
            "sources_count": data.get("sources_count", 0),
            "report": data.get("report", ""), "sources": data.get("sources", [])
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/research/run")
async def run_research(query: str = Form(...), depth: str = Form("standard")):
    """Запускает исследование через ResearchAgent"""
    try:
        from src.agents.research_agent.research_agent import ResearchAgent
        
        depth_config = {
            "standard": {"max_results": 5, "max_crawl_pages": 2},
            "deep": {"max_results": 10, "max_crawl_pages": 3},
            "expert": {"max_results": 20, "max_crawl_pages": 5}
        }
        config = depth_config.get(depth, depth_config["standard"])
        
        print(f"[API] Запуск исследования: {query}")
        print(f"[API] Глубина: {depth}, max_results={config['max_results']}, max_crawl={config['max_crawl_pages']}")
        
        agent = ResearchAgent()
        result = agent.search_and_report(
            query=query, max_results=config["max_results"],
            max_crawl_pages=config["max_crawl_pages"], depth=depth,
            generate_report=True, save_report=True
        )
        
        report_text = result.get("report", "")
        return {
            "status": "completed",
            "task_id": f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "message": f"Исследование по запросу '{query}' завершено (уровень: {depth})",
            "result": {
                "sources_count": result.get("sources_count", 0),
                "chunks_count": result.get("chunks_count", 0),
                "crawled_count": result.get("crawled_count", 0),
                "report_path": str(result.get("report_path", "")),
                "report": report_text, "sources": result.get("sources", []),
                "depth": depth
            }
        }
    except Exception as e:
        print(f"[API] Ошибка запуска исследования: {e}")
        traceback.print_exc()
        return {"status": "error", "message": f"Ошибка: {str(e)}"}


@app.post("/api/chat")
async def chat_message(message: str = Form(...)):
    """
    Обрабатывает сообщение чата с интеллектуальной маршрутизацией.
    Уровень 1: классификация по ключевым словам (быстро)
    Уровень 2: уточнение через LLM (если уверенность низкая)
    """
    try:
        print(f"[Chat] Получено сообщение: {message[:100]}...")
        
        # Двухуровневая классификация намерения
        intent_data = _classify_intent(message)
        intent = intent_data["intent"]
        confidence = intent_data["confidence"]
        method = intent_data.get("method", "keywords")
        
        print(f"[Chat] Интент: {intent} (уверенность: {confidence:.0%}, метод: {method})")
        
        # Маршрутизация по намерению
        if intent == "create_task" and confidence >= 0.6:
            return await _handle_create_task_from_chat(message)
        elif intent == "show_plan" and confidence >= 0.6:
            return await _handle_show_plan_from_chat(message)
        elif intent == "research" and confidence >= 0.6:
            return await _handle_research_from_chat(message)
        else:
            return await _handle_general_question(message)
            
    except Exception as e:
        print(f"[Chat] Ошибка: {e}")
        traceback.print_exc()
        return {"status": "error", "message": f"❌ Ошибка: {str(e)}"}


async def _handle_create_task_from_chat(message: str) -> dict:
    """Создаёт задачу через чат"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        
        # Если Ollama доступен — извлекаем детали задачи
        task_title = message[:100]
        assignee = None
        priority = "medium"
        
        if _check_ollama():
            prompt = f"""Извлеки из сообщения детали задачи в JSON.
Сообщение: {message}
Верни ТОЛЬКО JSON: {{"title":"...", "assignee":null, "priority":"medium", "deadline":null}}"""
            
            llm_response = _query_ollama(prompt, timeout=30)
            try:
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    task_data = json.loads(json_match.group())
                    task_title = task_data.get("title", message[:100])
                    assignee = task_data.get("assignee")
                    priority = task_data.get("priority", "medium")
            except:
                pass
        
        registry = MetricsRegistry()
        registry.add_decision(
            level="operational", description=task_title,
            source="chat", priority=priority,
            assignee=assignee or "Не назначен",
            deadline="Не указан"
        )
        registry.save()
        registry.reload()
        
        answer = f"✅ Задача создана: «{task_title}»\n📌 Приоритет: {priority}"
        if assignee:
            answer += f"\n👤 Исполнитель: {assignee}"
        answer += "\nЗадача добавлена в план действий."
        
        return {"status": "completed", "message": answer, "intent": "create_task"}
    except Exception as e:
        return {"status": "error", "message": f"Не удалось создать задачу: {str(e)}"}


async def _handle_show_plan_from_chat(message: str) -> dict:
    """Показывает план действий"""
    plan_ctx = _get_plan_context()
    tasks_ctx = _get_tasks_context()
    
    combined = f"{plan_ctx}\n\n{tasks_ctx}" if plan_ctx else tasks_ctx
    
    if not combined or combined in ["Задач нет.", ""]:
        return {
            "status": "completed",
            "message": "📋 На данный момент план действий пуст. Запустите полный пайплайн для формирования плана.",
            "intent": "show_plan"
        }
    
    if _check_ollama():
        prompt = f"""На основе плана действий и задач, ответь на вопрос пользователя.

{combined}

Вопрос: {message}
Дай краткий структурированный ответ."""
        answer = _query_ollama(prompt, timeout=60)
    else:
        answer = f"📋 **Текущий план:**\n\n{combined}"
    
    return {"status": "completed", "message": answer, "intent": "show_plan"}


async def _handle_research_from_chat(message: str) -> dict:
    """Запускает исследование через чат"""
    # Извлекаем поисковый запрос
    research_query = message
    prefixes = [r'исследу(й|ем|йте)\s+', r'найди\s+(информаци|данные)\s+(о|про|об)\s+',
                r'поищи\s+', r'расскажи\s+(о|про|об)\s+']
    for prefix in prefixes:
        research_query = re.sub(prefix, '', research_query, flags=re.IGNORECASE).strip()
    
    if not research_query or len(research_query) < 3:
        return {"status": "error", "message": "❌ Уточните, что именно нужно исследовать."}
    
    try:
        from src.agents.research_agent.research_agent import ResearchAgent
        agent = ResearchAgent()
        result = agent.search_and_report(
            query=research_query, max_results=5, max_crawl_pages=2,
            depth="deep", generate_report=True, save_report=False
        )
        
        if result.get("report"):
            answer = f"🔍 Результаты по запросу «{research_query}»:\n\n{result['report'][:2000]}"
            if len(result.get("report", "")) > 2000:
                answer += "\n\n...(отчёт сокращён для чата)"
        else:
            answer = f"По запросу «{research_query}» ничего не найдено."
        
        return {"status": "completed", "message": answer, "intent": "research",
                "sources_count": result.get("sources_count", 0)}
    except Exception as e:
        return {"status": "error", "message": f"Не удалось выполнить исследование: {str(e)}"}


async def _handle_general_question(message: str) -> dict:
    """Обрабатывает общий вопрос через RAG + LLM"""
    ollama_available = _check_ollama()
    context_parts = []
    
    rag_chunks = _search_rag(message, max_chunks=5)
    if rag_chunks:
        rag_text = "ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ:\n"
        for i, chunk in enumerate(rag_chunks[:5], 1):
            text = chunk.get("text", str(chunk))[:500]
            source = chunk.get("source", chunk.get("title", "неизвестно"))
            rag_text += f"\n[{i}] {source}: {text}\n"
        context_parts.append(rag_text)
    
    tasks_ctx = _get_tasks_context()
    if tasks_ctx and tasks_ctx != "Задач нет.":
        context_parts.append(tasks_ctx)
    
    plan_ctx = _get_plan_context()
    if plan_ctx:
        context_parts.append(plan_ctx)
    
    context = "\n\n".join(context_parts) if context_parts else "Контекст отсутствует."
    
    if ollama_available:
        prompt = f"""Ты — AI-ассистент руководителя компании УИИ. Отвечай на русском, кратко и по делу.

КОНТЕКСТ:
{context}

ВОПРОС: {message}

ОТВЕТ:"""
        answer = _query_ollama(prompt, timeout=60)
        if answer:
            return {"status": "completed", "message": answer, "intent": "question",
                    "rag_chunks_used": len(rag_chunks)}
    
    # Fallback
    if rag_chunks:
        answer = "🤖 **Ответ на основе базы знаний:**\n\n"
        for chunk in rag_chunks[:3]:
            text = chunk.get("text", str(chunk))[:400]
            source = chunk.get("source", chunk.get("title", ""))
            answer += f"• {text}...\n"
            if source: answer += f"  _(источник: {source})_\n"
            answer += "\n"
    else:
        answer = ("🤖 **Информация о системе:**\n\n"
                  "Я — AI-ассистент руководителя компании УИИ. Мои возможности:\n\n"
                  "• **Поиск в базе знаний (RAG)** — нахожу релевантную информацию\n"
                  "• **План действий** — могу показать текущий план и задачи\n"
                  "• **Создание задач** — скажите «создай задачу...»\n"
                  "• **Исследования** — скажите «исследуй...»\n\n"
                  "⚠️ Ollama недоступна, работаю в ограниченном режиме.")
    
    return {"status": "completed", "message": answer, "intent": "question",
            "rag_chunks_used": len(rag_chunks)}


@app.post("/api/tasks")
async def create_task(title: str = Form(...), assignee: str = Form(""),
                      priority: str = Form("medium"), deadline: str = Form("")):
    """Создаёт задачу и сохраняет в реестр"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        registry = MetricsRegistry()
        registry.add_decision(
            level="operational", description=title, source="web_interface",
            priority=priority, assignee=assignee or "Не назначен",
            deadline=deadline or "Не указан"
        )
        registry.save()
        registry.reload()
        print(f"[API] Задача создана: {title}")
        return {
            "status": "created",
            "task": {
                "id": f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "title": title, "assignee": assignee or "Не назначен",
                "priority": priority, "deadline": deadline or "Не указан",
                "status": "pending"
            }
        }
    except Exception as e:
        print(f"[API] Ошибка создания задачи: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Удаляет задачу по ID"""
    try:
        from src.agents.metrics_agent.metrics_registry import MetricsRegistry
        registry = MetricsRegistry()
        decisions = registry.get_all_decisions()
        new_decisions = []
        found = False
        for d in decisions:
            if d.id == task_id:
                found = True
                print(f"[API] Удаление задачи: {d.description}")
            else:
                new_decisions.append(d)
        if not found:
            return {"status": "error", "message": f"Задача {task_id} не найдена"}
        registry.decisions_cache = new_decisions
        registry.registry_data["decisions"] = [d.to_dict() for d in new_decisions]
        registry.save()
        registry.reload()
        print(f"[API] Задача удалена: {task_id}")
        return {"status": "deleted", "message": f"Задача {task_id} удалена"}
    except Exception as e:
        print(f"[API] Ошибка удаления задачи: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ============================================================
# СТРАНИЦЫ
# ============================================================

def read_html(filename: str) -> str:
    """Читает HTML-файл из папки templates"""
    try:
        with open(TEMPLATES_DIR / filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>Файл {filename} не найден</h1>"


@app.get("/", response_class=HTMLResponse)
async def index():
    """Главная страница"""
    return HTMLResponse(content=read_html("index.html"))

@app.get("/research", response_class=HTMLResponse)
async def research_page():
    """Страница исследования"""
    return HTMLResponse(content=read_html("research.html"))

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page():
    """Страница задач"""
    return HTMLResponse(content=read_html("tasks.html"))

@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """Страница чата"""
    return HTMLResponse(content=read_html("chat.html"))

@app.get("/presentation", response_class=HTMLResponse)
async def presentation_page():
    """Страница презентации"""
    return HTMLResponse(content=read_html("presentation.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)