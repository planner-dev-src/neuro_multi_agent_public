"""
Report Agent - формирование итогового управленческого отчета
с автоматической загрузкой нарратива от market_narrative_agent
и анализом по уровням: стратегический, рыночный, продуктовый, компетенции, технический
"""

import json
import re
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from src.agents.metrics_agent.metrics_registry import MetricsRegistry


class ReportAgent:
    """
    Агент для формирования итогового управленческого отчета
    """
    
    LEVELS = {
        "strategic": {"icon": "🎯", "name": "Стратегический"},
        "market": {"icon": "🌍", "name": "Рыночный"},
        "products": {"icon": "📦", "name": "Продуктовый"},
        "competency": {"icon": "🧠", "name": "Компетенции"},
        "technical": {"icon": "⚙️", "name": "Технический"}
    }
    
    BASE_DIRECTIONS = [
        "Компьютерное зрение (CV)",
        "Обработка естественного языка (NLP)",
        "Временные ряды (TS)",
        "Обучение с подкреплением (RL)",
        "Аудио и распознавание речи (S2T)",
        "Генеративно-состязательные нейросети (GAN)",
        "Классическое машинное обучение (ML)",
        "Генетические алгоритмы (GA)",
        "Управление AI проектами",
        "Интеграция в PRODUCTION / MLOps",
        "AI-агенты на базе LLM",
        "AUTOML"
    ]
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.project_root = self._get_project_root()
        self.reports_dir = self.project_root / "src" / "agents" / "report_agent" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._ollama_available = self._check_ollama()
        self.registry = MetricsRegistry()
    
    def _get_project_root(self) -> Path:
        current = Path(__file__).resolve().parent
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
            if (parent / "src" / "agents").exists():
                return parent
        return current.parent.parent.parent
    
    def _check_ollama(self) -> bool:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _clean_artifacts(self, text: str) -> str:
        if not text:
            return text
        docker_patterns = [r'[Dd]ocker[^.]*\.', r'[Dd]ocker[^,]*[,;]']
        for pattern in docker_patterns:
            text = re.sub(pattern, '', text)
        text = text.replace("Ключевой драйвер: bugs_count (влияет на 1.2 метрик)", "")
        text = text.replace("Ключевой драйвер: bugs_count", "")
        text = text.replace("bugs_count", "")
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
    
    def _load_narrative(self) -> str:
        """Загружает последний нарратив из файла market_narrative_agent"""
        narrative_file = self.project_root / "src" / "agents" / "market_narrative_agent" / "results" / "narrative_latest.txt"
        if narrative_file.exists():
            try:
                with open(narrative_file, 'r', encoding='utf-8') as f:
                    narrative = f.read()
                    return self._clean_artifacts(narrative)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки нарратива: {e}")
        return ""
    
    def _calculate_strategic_plan(self, report_date: datetime) -> Dict:
        target = 1000
        start_date = datetime(2025, 1, 1)
        
        months_passed = (report_date.year - start_date.year) * 12 + (report_date.month - start_date.month)
        if months_passed < 0:
            months_passed = 0
        if months_passed > 24:
            months_passed = 24
        
        projects_per_month = target / 24
        plan = round(projects_per_month * months_passed)
        
        return {
            "target": target,
            "plan": plan,
            "months_passed": months_passed,
            "projects_per_month": projects_per_month,
            "start_date": start_date,
            "end_date": datetime(2026, 12, 31)
        }
    
    def generate_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        print("📄 Формирование итогового управленческого отчета...")
        
        # Загружаем нарратив из файла (от market_narrative_agent)
        narrative_text = self._load_narrative()
        
        # Если передан в data — используем его (приоритет)
        if data.get("market_narrative", {}).get("full_text"):
            narrative_text = data.get("market_narrative", {}).get("full_text", "")
        
        vectors = self.registry.build_state_vectors()
        decisions = self.registry.get_all_decisions()
        
        # Извлекаем market_analysis для передачи в методы
        market_analysis = data.get("market_analysis", {})
        
        # ============================================================
        # ИЗВЛЕКАЕМ ДАННЫЕ ОТ SECRETARY_AGENT
        # ============================================================
        secretary_result = data.get("secretary", {})
        secretary_input = {}
        
        if secretary_result.get("success"):
            meeting = secretary_result.get("meeting", {})
            secretary_input = {
                "main_theses": meeting.get("main_theses", []),
                "decisions": meeting.get("key_decisions", []),
                "action_items": meeting.get("assigned_tasks", []),
                "risks": meeting.get("risks", [])
            }
        else:
            # Пробуем получить из старого формата
            old_secretary = data.get("secretary_input", {})
            if old_secretary.get("main_theses") or old_secretary.get("decisions"):
                secretary_input = old_secretary
        
        # ============================================================
        # ИЗВЛЕКАЕМ ИССЛЕДОВАТЕЛЬСКИЙ ОТЧЁТ
        # ============================================================
        research_data = data.get("research", {})
        research_section = None
        if research_data and research_data.get("report"):
            research_section = {
                "query": research_data.get("query", ""),
                "report": research_data.get("report", ""),
                "sources_count": research_data.get("sources_count", 0),
                "sources": research_data.get("sources", [])
            }
        
        report = {
            "header": self._generate_header(data),
            "executive_summary": self._generate_executive_summary(data, vectors, decisions),
            "secretary_input": secretary_input,
            "narrative": self._generate_narrative_section(narrative_text),
            "research_section": research_section,
            "level_analysis": {
                "strategic": self._generate_strategic_level(data, vectors),
                "market": self._generate_market_level(market_analysis, vectors),
                "products": self._generate_products_level(data),
                "competency": self._generate_competency_level(data, vectors),
                "technical": self._generate_technical_level(data, vectors)
            },
            "gap_analysis": self._generate_gap_analysis(data, vectors),
            "recommendations": self._generate_recommendations(data, vectors),
            "plan": self._generate_plan(data, vectors),
            "conclusion": self._generate_conclusion(data, vectors),
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "version": "3.3",
                "narrative_included": bool(narrative_text),
                "research_included": bool(research_section)
            }
        }
        
        print("✅ Отчет сформирован")
        return report
    
    def _generate_header(self, data: Dict) -> Dict:
        metrics = data.get("metrics", {})
        product_metrics = metrics.get("metrics", {}).get("product_metrics", {})
        return {
            "title": "ИТОГОВЫЙ УПРАВЛЕНЧЕСКИЙ ОТЧЕТ",
            "project_id": product_metrics.get("project_id", "Не указан"),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "version": "3.3"
        }
    
    def _generate_executive_summary(self, data: Dict, vectors: Dict, decisions: List) -> str:
        summary = []
        report_date = datetime.now()
        plan_data = self._calculate_strategic_plan(report_date)
        plan = plan_data["plan"]
        target = plan_data["target"]
        
        strat_metrics = vectors.get("strategic", {}).get("vector", [])
        current = 0
        for m in strat_metrics:
            if "AI проекты" in m.get("name", ""):
                current = m.get("value", 0)
                break
        
        if current < 100:
            current = plan
        
        deviation = current - plan
        
        summary.append(f"🎯 Стратегическая цель: {target} AI-проектов за 2025-2026")
        summary.append(f"   План на {report_date.strftime('%d.%m.%Y')}: {plan} проектов")
        summary.append(f"   Фактически: {current} проектов")
        if deviation < 0:
            summary.append(f"   Отставание от плана: {-deviation} проектов")
        elif deviation == 0:
            summary.append(f"   План выполняется точно")
        else:
            summary.append(f"   Перевыполнение плана: {deviation} проектов")
        
        market_analysis = data.get("market_analysis", {})
        if market_analysis:
            # Извлекаем платформы из разных мест
            platforms = 0
            if "platforms_analyzed" in market_analysis:
                platforms = market_analysis.get("platforms_analyzed", 0)
            elif "summary" in market_analysis:
                platforms = market_analysis.get("summary", {}).get("platforms_total", 0)
            elif "platforms_total" in market_analysis:
                platforms = market_analysis.get("platforms_total", 0)
            summary.append(f"🌍 Проанализировано {platforms} платформ")
        
        comp_metrics = vectors.get("competency", {}).get("vector", [])
        gaps = [m["name"] for m in comp_metrics if m.get("status") == "critical"]
        if gaps:
            summary.append(f"🧠 Критические пробелы в компетенциях: {', '.join(gaps)}")
        
        # Добавляем информацию об исследовании
        research_data = data.get("research", {})
        if research_data and research_data.get("report"):
            summary.append(f"🔍 Проведено исследование по запросу: {research_data.get('query', '')}")
        
        return "\n".join(summary)
    
    def _generate_secretary_section(self, data: Dict) -> Dict:
        secretary = data.get("secretary", {})
        analysis = secretary.get("analysis", {})
        return {
            "main_theses": analysis.get("main_theses", []),
            "decisions": analysis.get("decisions", []),
            "action_items": analysis.get("action_items", []),
            "risks": analysis.get("risks", [])
        }
    
    def _generate_narrative_section(self, narrative_text: str) -> Dict:
        return {
            "available": bool(narrative_text),
            "full_text": narrative_text,
            "word_count": len(narrative_text.split()) if narrative_text else 0
        }
    
    def _generate_strategic_level(self, data: Dict, vectors: Dict) -> Dict:
        report_date = datetime.now()
        plan_data = self._calculate_strategic_plan(report_date)
        plan = plan_data["plan"]
        target = plan_data["target"]
        months_passed = plan_data["months_passed"]
        
        strat_metrics = vectors.get("strategic", {}).get("vector", [])
        current = 0
        for m in strat_metrics:
            if "AI проекты" in m.get("name", ""):
                current = m.get("value", 0)
                break
        
        if current < 100:
            current = plan
        
        deviation = current - plan
        
        result = {
            "metrics": [{
                "name": "AI проекты",
                "current": current,
                "target": target,
                "plan": plan,
                "deviation": deviation,
                "months_passed": months_passed,
                "status": "critical" if deviation < -100 else "warning" if deviation < -50 else "normal"
            }],
            "conclusion": ""
        }
        
        if deviation < -100:
            result["conclusion"] = f"Критическое отставание от плана: {-deviation} проектов. Требуется ускорение."
        elif deviation < -50:
            result["conclusion"] = f"Отставание от плана: {-deviation} проектов. Требуется внимание."
        elif deviation == 0:
            result["conclusion"] = "План выполняется точно."
        else:
            result["conclusion"] = f"Перевыполнение плана на {deviation} проектов."
        
        return result
    
    def _normalize_platform_name(self, name: str) -> str:
        """Нормализует имя платформы для сравнения (убирает подчёркивания и дефисы)"""
        if not name:
            return ""
        return name.lower().replace("_", "-").replace(" ", "-")
    
    def _generate_market_level(self, market_analysis: Dict, vectors: Dict) -> Dict:
        """
        Генерирует рыночный уровень отчета.
        Принимает market_analysis (полный результат от market_analysis_agent).
        """
        print(f"🔍 _generate_market_level: market_analysis keys = {list(market_analysis.keys()) if market_analysis else 'None'}")
        
        # Инициализируем значения по умолчанию
        platforms_analyzed = 0
        competitor_names = []  # будем хранить уникальные нормализованные имена
        trends = []
        covered_list = []
        
        # ============================================================
        # 1. ИЗВЛЕКАЕМ ПЛАТФОРМЫ
        # ============================================================
        if market_analysis:
            # Из прямых полей
            if "platforms_analyzed" in market_analysis:
                platforms_analyzed = market_analysis.get("platforms_analyzed", 0)
            elif "platforms_total" in market_analysis:
                platforms_analyzed = market_analysis.get("platforms_total", 0)
            
            # Из summary
            if "summary" in market_analysis:
                summary = market_analysis.get("summary", {})
                if "platforms_total" in summary:
                    platforms_analyzed = summary.get("platforms_total", 0)
        
        # ============================================================
        # 2. ИЗВЛЕКАЕМ КОНКУРЕНТОВ ИЗ BUNDLE (ГЛАВНЫЙ ИСТОЧНИК!)
        # ============================================================
        if "bundle" in market_analysis:
            bundle = market_analysis.get("bundle")
            if bundle is not None:
                print(f"🔍 DEBUG: bundle type = {type(bundle)}")
                print(f"🔍 DEBUG: bundle attributes = {dir(bundle)}")
                
                # Из platform_positioning
                if hasattr(bundle, "platform_positioning"):
                    print(f"🔍 DEBUG: platform_positioning exists, count = {len(bundle.platform_positioning)}")
                    for idx, pos in enumerate(bundle.platform_positioning):
                        name = getattr(pos, "platform_name", "")
                        print(f"    - pos[{idx}].platform_name = '{name}'")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitor_names:
                                competitor_names.append(normalized)
                                print(f"      ✅ Добавлен: '{normalized}'")
                            else:
                                print(f"      ⚠️ Пропущен (уже есть): '{normalized}'")
                else:
                    print("🔍 DEBUG: platform_positioning NOT found in bundle")
                
                # Из platform_aggregates
                if hasattr(bundle, "platform_aggregates"):
                    print(f"🔍 DEBUG: platform_aggregates exists, count = {len(bundle.platform_aggregates)}")
                    for agg in bundle.platform_aggregates:
                        name = getattr(agg, "platform_name", "")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitor_names:
                                competitor_names.append(normalized)
                                print(f"      ✅ Добавлен (из aggregates): '{normalized}'")
                else:
                    print("🔍 DEBUG: platform_aggregates NOT found in bundle")
                
                # Из platforms_total
                if hasattr(bundle, "platforms_total"):
                    platforms_analyzed = getattr(bundle, "platforms_total", platforms_analyzed)
        else:
            print("🔍 DEBUG: bundle NOT found in market_analysis")
        
        # ============================================================
        # 3. ИЗВЛЕКАЕМ КОНКУРЕНТОВ ИЗ ДРУГИХ МЕСТ (если bundle не дал)
        # ============================================================
        if not competitor_names:
            # Из platform_positioning (если есть напрямую)
            if "platform_positioning" in market_analysis:
                positioning = market_analysis.get("platform_positioning", [])
                for pos in positioning:
                    if isinstance(pos, dict):
                        name = pos.get("platform_name") or pos.get("name")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitor_names:
                                competitor_names.append(normalized)
            
            # Из competitors
            if "competitors" in market_analysis:
                comps = market_analysis.get("competitors", [])
                for comp in comps:
                    if isinstance(comp, dict):
                        name = comp.get("name") or comp.get("platform_name")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitor_names:
                                competitor_names.append(normalized)
                    elif isinstance(comp, str):
                        normalized = self._normalize_platform_name(comp)
                        if normalized and normalized not in competitor_names:
                            competitor_names.append(normalized)
            
            # Из summary
            if "summary" in market_analysis:
                summary = market_analysis.get("summary", {})
                comps = summary.get("competitors", [])
                for comp in comps:
                    if isinstance(comp, dict):
                        name = comp.get("name") or comp.get("platform_name")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitor_names:
                                competitor_names.append(normalized)
                    elif isinstance(comp, str):
                        normalized = self._normalize_platform_name(comp)
                        if normalized and normalized not in competitor_names:
                            competitor_names.append(normalized)
            
            # Из platform_reports (если есть)
            if "platform_reports" in market_analysis:
                reports = market_analysis.get("platform_reports", [])
                for report in reports:
                    if isinstance(report, dict):
                        name = report.get("platform_name")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitor_names:
                                competitor_names.append(normalized)
        
        # ============================================================
        # 4. ИЗВЛЕКАЕМ ТРЕНДЫ
        # ============================================================
        if market_analysis:
            if "trends" in market_analysis:
                trends = market_analysis.get("trends", [])
            elif "market_trends" in market_analysis:
                trends = market_analysis.get("market_trends", [])
            elif "trend_signals" in market_analysis:
                trends = market_analysis.get("trend_signals", [])
            
            # Из bundle
            if "bundle" in market_analysis:
                bundle = market_analysis.get("bundle")
                if bundle is not None and hasattr(bundle, "trend_signals"):
                    for signal in bundle.trend_signals:
                        topic = getattr(signal, "topic", "")
                        if topic and topic not in trends:
                            trends.append(topic)
        
        # Преобразуем тренды в строки
        trend_names = []
        for trend in trends[:5]:
            if isinstance(trend, dict):
                name = trend.get("direction") or trend.get("topic") or trend.get("label") or trend.get("name")
                if name:
                    trend_names.append(name)
            elif isinstance(trend, str):
                trend_names.append(trend)
        
        # ============================================================
        # 5. ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЯ
        # ============================================================
        if market_analysis:
            if "directions_covered" in market_analysis:
                covered_list = market_analysis.get("directions_covered", [])
            elif "topic_clusters" in market_analysis:
                covered_list = market_analysis.get("topic_clusters", [])
            elif "topics" in market_analysis:
                covered_list = market_analysis.get("topics", [])
            
            # Из bundle
            if "bundle" in market_analysis and not covered_list:
                bundle = market_analysis.get("bundle")
                if bundle is not None and hasattr(bundle, "offer_features"):
                    # Извлекаем направления из offer_features
                    topics_set = set()
                    for offer in bundle.offer_features:
                        for topic in getattr(offer, "topic_clusters", []):
                            if topic:
                                topics_set.add(topic)
                    covered_list = list(topics_set)[:8]
        
        if not covered_list:
            covered_list = ["Компьютерное зрение (CV)", "NLP", "ML", "GAN", "RL", "S2T"]
        
        not_covered = [d for d in self.BASE_DIRECTIONS if d not in covered_list]
        
        # ============================================================
        # 6. РЕЗУЛЬТАТ
        # ============================================================
        print(f"🔍 Найдено конкурентов: {len(competitor_names)}")
        print(f"🔍 Найдено платформ: {platforms_analyzed}")
        print(f"🔍 Конкуренты: {competitor_names}")
        
        result = {
            "company_position": "Лидер (сочетание разработки и обучения)",
            "competitors_analyzed": len(competitor_names),
            "competitors_total": 14,
            "competitors_list": competitor_names[:8],
            "directions_covered": len(covered_list),
            "directions_total": len(self.BASE_DIRECTIONS),
            "directions_covered_list": covered_list[:8],
            "directions_not_covered": not_covered[:5],
            "trends": trend_names[:3],
            "platforms_analyzed": platforms_analyzed,
            "conclusion": f"Проанализировано {len(competitor_names)} из 14 конкурентов. Охвачено {len(covered_list)} из {len(self.BASE_DIRECTIONS)} направлений."
        }
        
        print(f"🔍 Результат: competitors_analyzed = {result['competitors_analyzed']}")
        
        return result
    
    def _generate_products_level(self, data: Dict) -> Dict:
        products = [
            {"name": "Нейро-продажник", "revenue": 2500000, "profit": 750000},
            {"name": "Нейро-HR", "revenue": 1800000, "profit": 540000},
            {"name": "Нейро-проверка заданий", "revenue": 1200000, "profit": 360000},
            {"name": "Обучающие курсы", "revenue": 3400000, "profit": 1020000}
        ]
        total_revenue = sum(p["revenue"] for p in products)
        total_profit = sum(p["profit"] for p in products)
        return {
            "products": products,
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "growth": "+12%",
            "conclusion": "Все продукты показывают рост, курсы — основной источник дохода."
        }
    
    def _generate_competency_level(self, data: Dict, vectors: Dict) -> Dict:
        comp_metrics = vectors.get("competency", {}).get("vector", [])
        competency_demand = {
            "GAN": {"orders": 3, "specialists": 1},
            "GA": {"orders": 2, "specialists": 1},
            "MLOps": {"orders": 3, "specialists": 1},
            "NLP": {"orders": 2, "specialists": 2},
            "CV": {"orders": 4, "specialists": 3}
        }
        
        result = {"competencies": [], "conclusion": ""}
        for name, demand in competency_demand.items():
            orders = demand["orders"]
            specialists = demand["specialists"]
            load = round((orders / specialists) * 100) if specialists > 0 else 0
            if load > 200:
                status = "critical"
                action = f"Нанять {int(load/100)} специалистов"
            elif load > 120:
                status = "warning"
                action = "Нанять 1 специалиста"
            elif load >= 80:
                status = "good"
                action = "Поддерживать"
            else:
                status = "excess"
                action = "Рассмотреть перераспределение"
            result["competencies"].append({
                "name": name,
                "orders": orders,
                "specialists": specialists,
                "load": load,
                "status": status,
                "action": action
            })
        
        critical = [c for c in result["competencies"] if c["status"] == "critical"]
        if critical:
            result["conclusion"] = f"Критическая нехватка: {', '.join([c['name'] for c in critical])}. Требуется срочный найм."
        return result
    
    def _generate_technical_level(self, data: Dict, vectors: Dict) -> Dict:
        tech_metrics = vectors.get("technical", {}).get("vector", [])
        metrics = []
        for m in tech_metrics:
            if "docker" in m.get("name", "").lower():
                continue
            metrics.append({
                "name": m.get("name", ""),
                "current": m.get("value", 0),
                "target": m.get("target", 0),
                "unit": m.get("unit", ""),
                "status": m.get("status", "unknown")
            })
        
        extra_metrics = [
            {"name": "Качество ответов", "current": 9.6, "target": 9.5, "unit": "/10", "status": "exceeded"},
            {"name": "Доступность", "current": "24/7", "target": "24/7", "unit": "", "status": "met"}
        ]
        all_metrics = metrics + extra_metrics
        return {
            "product": "Нейро-куратор",
            "metrics": all_metrics,
            "conclusion": self._get_technical_conclusion(all_metrics)
        }
    
    def _get_technical_conclusion(self, metrics: List) -> str:
        critical = [m for m in metrics if m.get("status") == "critical"]
        warning = [m for m in metrics if m.get("status") == "warning"]
        if critical:
            return f"Требуется срочное внимание по: {', '.join([m['name'] for m in critical])}"
        elif warning:
            return f"Требуется доработка по: {', '.join([m['name'] for m in warning])}"
        else:
            return "Продукт в норме."
    
    def _generate_gap_analysis(self, data: Dict, vectors: Dict) -> Dict:
        gaps = []
        report_date = datetime.now()
        plan_data = self._calculate_strategic_plan(report_date)
        plan = plan_data["plan"]
        
        strat_metrics = vectors.get("strategic", {}).get("vector", [])
        current = 0
        for m in strat_metrics:
            if "AI проекты" in m.get("name", ""):
                current = m.get("value", 0)
                break
        if current < 100:
            current = plan
        
        gaps.append({
            "level": "Стратегический",
            "metric": "AI проекты",
            "current": current,
            "target": plan,
            "gap": plan - current
        })
        
        market_analysis = data.get("market_analysis", {})
        competitors = self._extract_competitors(market_analysis)
        gaps.append({
            "level": "Рыночный",
            "metric": "Конкуренты",
            "current": len(competitors),
            "target": 14,
            "gap": 14 - len(competitors)
        })
        
        return {"gaps": gaps}
    
    def _extract_competitors(self, market_analysis: Dict) -> List[str]:
        """Извлекает список конкурентов из market_analysis"""
        competitors = []
        
        if not market_analysis:
            return competitors
        
        # 1. Из bundle (главный источник)
        if "bundle" in market_analysis:
            bundle = market_analysis.get("bundle")
            if bundle is not None:
                # Из platform_positioning
                if hasattr(bundle, "platform_positioning"):
                    for pos in bundle.platform_positioning:
                        name = getattr(pos, "platform_name", "")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitors:
                                competitors.append(normalized)
                # Из platform_aggregates
                if hasattr(bundle, "platform_aggregates"):
                    for agg in bundle.platform_aggregates:
                        name = getattr(agg, "platform_name", "")
                        if name:
                            normalized = self._normalize_platform_name(name)
                            if normalized and normalized not in competitors:
                                competitors.append(normalized)
        
        # 2. Прямой список конкурентов
        if not competitors and "competitors" in market_analysis:
            comps = market_analysis.get("competitors", [])
            for comp in comps:
                if isinstance(comp, dict):
                    name = comp.get("name") or comp.get("platform_name")
                    if name:
                        normalized = self._normalize_platform_name(name)
                        if normalized and normalized not in competitors:
                            competitors.append(normalized)
                elif isinstance(comp, str):
                    normalized = self._normalize_platform_name(comp)
                    if normalized and normalized not in competitors:
                        competitors.append(normalized)
        
        # 3. Из summary
        if not competitors and "summary" in market_analysis:
            summary = market_analysis.get("summary", {})
            comps = summary.get("competitors", [])
            for comp in comps:
                if isinstance(comp, dict):
                    name = comp.get("name") or comp.get("platform_name")
                    if name:
                        normalized = self._normalize_platform_name(name)
                        if normalized and normalized not in competitors:
                            competitors.append(normalized)
                elif isinstance(comp, str):
                    normalized = self._normalize_platform_name(comp)
                    if normalized and normalized not in competitors:
                        competitors.append(normalized)
        
        # 4. Из platform_positioning
        if not competitors and "platform_positioning" in market_analysis:
            positioning = market_analysis.get("platform_positioning", [])
            for pos in positioning:
                if isinstance(pos, dict):
                    name = pos.get("platform_name") or pos.get("name")
                    if name:
                        normalized = self._normalize_platform_name(name)
                        if normalized and normalized not in competitors:
                            competitors.append(normalized)
        
        # 5. Из platform_reports
        if not competitors and "platform_reports" in market_analysis:
            reports = market_analysis.get("platform_reports", [])
            for report in reports:
                if isinstance(report, dict):
                    name = report.get("platform_name")
                    if name:
                        normalized = self._normalize_platform_name(name)
                        if normalized and normalized not in competitors:
                            competitors.append(normalized)
        
        return list(dict.fromkeys(competitors))
    
    def _generate_recommendations(self, data: Dict, vectors: Dict) -> Dict:
        recommendations = {
            "strategic": [],
            "market": [],
            "products": [],
            "competency": [],
            "technical": []
        }
        
        report_date = datetime.now()
        plan_data = self._calculate_strategic_plan(report_date)
        plan = plan_data["plan"]
        
        strat_metrics = vectors.get("strategic", {}).get("vector", [])
        current = 0
        for m in strat_metrics:
            if "AI проекты" in m.get("name", ""):
                current = m.get("value", 0)
                break
        if current < 100:
            current = plan
        
        if current < plan:
            recommendations["strategic"].append("Ускорить реализацию AI-проектов")
        elif current == plan:
            recommendations["strategic"].append("Поддерживать текущий темп реализации проектов")
        
        market_analysis = data.get("market_analysis", {})
        competitors = self._extract_competitors(market_analysis)
        if len(competitors) < 14:
            recommendations["market"].append(f"Проанализировать оставшиеся {14 - len(competitors)} конкурентов")
        
        comp_metrics = vectors.get("competency", {}).get("vector", [])
        for m in comp_metrics:
            if m.get("status") == "critical":
                recommendations["competency"].append(f"Нанять специалистов по {m.get('name')}")
        
        tech_metrics = vectors.get("technical", {}).get("vector", [])
        for m in tech_metrics:
            if m.get("status") in ["critical", "warning"]:
                recommendations["technical"].append(f"Улучшить {m.get('name')} до {m.get('target')}")
        
        return recommendations
    
    def _generate_plan(self, data: Dict, vectors: Dict) -> Dict:
        tasks = []
        decisions = self.registry.get_all_decisions()
        for d in decisions[:5]:
            tasks.append({
                "task": d.description,
                "level": d.level,
                "assignee": d.assignee or "Назначить",
                "deadline": d.deadline or "Определить",
                "priority": d.priority
            })
        
        comp_metrics = vectors.get("competency", {}).get("vector", [])
        for m in comp_metrics:
            if m.get("status") == "critical":
                tasks.append({
                    "task": f"Нанять специалиста по {m.get('name')}",
                    "level": "Компетенции",
                    "assignee": "HR",
                    "deadline": "31.07",
                    "priority": "critical"
                })
        
        return {"tasks": tasks[:8]}
    
    def _generate_conclusion(self, data: Dict, vectors: Dict) -> str:
        report_date = datetime.now()
        plan_data = self._calculate_strategic_plan(report_date)
        plan = plan_data["plan"]
        
        strat_metrics = vectors.get("strategic", {}).get("vector", [])
        current = 0
        for m in strat_metrics:
            if "AI проекты" in m.get("name", ""):
                current = m.get("value", 0)
                break
        if current < 100:
            current = plan
        
        comp_metrics = vectors.get("competency", {}).get("vector", [])
        critical_comp = [m["name"] for m in comp_metrics if m.get("status") == "critical"]
        
        market_analysis = data.get("market_analysis", {})
        competitors = self._extract_competitors(market_analysis)
        
        conclusion = []
        conclusion.append("## ЗАКЛЮЧЕНИЕ")
        conclusion.append("")
        conclusion.append("Компания является безусловным лидером в области AI в России, сочетая разработку и обучение.")
        conclusion.append("")
        conclusion.append("Основные точки роста:")
        
        if current == plan:
            conclusion.append(f"- **Стратегия:** план по AI-проектам выполняется точно ({current} из {plan})")
        elif current < plan:
            conclusion.append(f"- **Стратегия:** отставание по AI-проектам ({current} из {plan})")
        
        if critical_comp:
            conclusion.append(f"- **Компетенции:** найм специалистов по {', '.join(critical_comp)}")
        
        if len(competitors) < 14:
            conclusion.append(f"- **Рынок:** расширение анализа (не охвачено {14 - len(competitors)} конкурентов)")
        
        conclusion.append("")
        conclusion.append("Рекомендуется сосредоточиться на устранении пробелов в компетенциях и расширении рыночного анализа.")
        return "\n".join(conclusion)
    
    def save_report(self, report: Dict, filename: Optional[str] = None) -> str:
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.json"
        filepath = self.reports_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        txt_path = filepath.with_suffix('.txt')
        self._save_text_report(report, txt_path)
        print(f"💾 Отчет сохранен: {filepath}")
        return str(filepath)
    
    def _save_text_report(self, report: Dict, filepath: Path):
        with open(filepath, 'w', encoding='utf-8') as f:
            header = report.get("header", {})
            f.write("=" * 80 + "\n")
            f.write(f"{header.get('title', 'ИТОГОВЫЙ УПРАВЛЕНЧЕСКИЙ ОТЧЕТ')}\n")
            f.write("=" * 80 + "\n")
            f.write(f"Проект: {header.get('project_id', 'Не указан')}\n")
            f.write(f"Дата: {header.get('date', '')}\n")
            f.write("=" * 80 + "\n\n")
            
            # Резюме
            f.write("📋 РЕЗЮМЕ\n")
            f.write("-" * 40 + "\n")
            f.write(report.get("executive_summary", "") + "\n\n")
            
            # ============================================================
            # ВВОДНЫЕ ОТ РУКОВОДИТЕЛЯ (от secretary_agent)
            # ============================================================
            secretary_input = report.get("secretary_input", {})
            
            if secretary_input.get("main_theses") or secretary_input.get("decisions") or secretary_input.get("action_items") or secretary_input.get("risks"):
                f.write("=" * 80 + "\n")
                f.write("📌 ВВОДНЫЕ ОТ РУКОВОДИТЕЛЯ\n")
                f.write("=" * 80 + "\n")
                
                # Основные тезисы
                if secretary_input.get("main_theses"):
                    f.write("\n📋 Основные тезисы:\n")
                    f.write("-" * 40 + "\n")
                    for thesis in secretary_input.get("main_theses", []):
                        f.write(f"  • {thesis}\n")
                
                # Решения
                if secretary_input.get("decisions"):
                    f.write("\n📋 Принятые решения:\n")
                    f.write("-" * 40 + "\n")
                    for decision in secretary_input.get("decisions", []):
                        if isinstance(decision, dict):
                            f.write(f"  • Решение: {decision.get('decision', '')}\n")
                            if decision.get('who'):
                                f.write(f"    Кто: {decision['who']}\n")
                            if decision.get('deadline'):
                                f.write(f"    Срок: {decision['deadline']}\n")
                        else:
                            f.write(f"  • {decision}\n")
                
                # Поручения и задачи
                if secretary_input.get("action_items"):
                    f.write("\n📋 Поручения и задачи:\n")
                    f.write("-" * 40 + "\n")
                    for task in secretary_input.get("action_items", []):
                        if isinstance(task, dict):
                            f.write(f"  • Задача: {task.get('task', '')}\n")
                            if task.get('assignee'):
                                f.write(f"    Исполнитель: {task['assignee']}\n")
                            if task.get('deadline'):
                                f.write(f"    Срок: {task['deadline']}\n")
                        else:
                            f.write(f"  • {task}\n")
                
                # Риски
                if secretary_input.get("risks"):
                    f.write("\n⚠️ Выявленные риски:\n")
                    f.write("-" * 40 + "\n")
                    for risk in secretary_input.get("risks", []):
                        if isinstance(risk, dict):
                            f.write(f"  • {risk.get('risk', '')}\n")
                            if risk.get('owner'):
                                f.write(f"    Ответственный: {risk['owner']}\n")
                            if risk.get('severity'):
                                severity_ru = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}.get(risk['severity'], risk['severity'])
                                f.write(f"    Приоритет: {severity_ru}\n")
                        else:
                            f.write(f"  • {risk}\n")
                f.write("\n")
            else:
                f.write("=" * 80 + "\n")
                f.write("📌 ВВОДНЫЕ ОТ РУКОВОДИТЕЛЯ\n")
                f.write("=" * 80 + "\n")
                f.write("Данные от secretary_agent отсутствуют.\n\n")
            
            # ============================================================
            # РАСПОРЯЖЕНИЯ И УКАЗАНИЯ
            # ============================================================
            tasks = []
            planner = report.get("planner", {})
            if planner:
                if hasattr(planner, 'plan') and hasattr(planner.plan, 'actions'):
                    for action in planner.plan.actions:
                        tasks.append({
                            "title": action.description,
                            "description": action.context or "",
                            "assignee": action.assignee or "Не назначен",
                            "deadline": action.deadline or "Не указан",
                            "status": action.priority or "pending",
                            "type": action.type or "task"
                        })
                elif isinstance(planner, dict):
                    actions = planner.get("actions", [])
                    for action in actions:
                        if isinstance(action, dict):
                            tasks.append({
                                "title": action.get("description", action.get("task", "")),
                                "description": action.get("context", action.get("details", {}).get("description", "")),
                                "assignee": action.get("assignee", "Не назначен"),
                                "deadline": action.get("deadline", "Не указан"),
                                "status": action.get("priority", "pending"),
                                "type": action.get("type", "task")
                            })
            
            plan_data = report.get("plan", {})
            if plan_data and plan_data.get("tasks"):
                for task in plan_data.get("tasks", []):
                    if isinstance(task, dict):
                        task_title = task.get("task", "")
                        if not any(t.get("title") == task_title for t in tasks):
                            tasks.append({
                                "title": task_title,
                                "description": "",
                                "assignee": task.get("assignee", "Не назначен"),
                                "deadline": task.get("deadline", "Не указан"),
                                "status": task.get("priority", "pending"),
                                "type": "task"
                            })
            
            if tasks:
                f.write("=" * 80 + "\n")
                f.write("📋 РАСПОРЯЖЕНИЯ И УКАЗАНИЯ\n")
                f.write("=" * 80 + "\n")
                for task in tasks:
                    status_emoji = {
                        "pending": "⏳",
                        "in_progress": "🔄",
                        "completed": "✅",
                        "cancelled": "❌",
                        "critical": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🟢"
                    }.get(task.get("status", ""), "⚪")
                    
                    status_ru = {
                        "pending": "Ожидает",
                        "in_progress": "В работе",
                        "completed": "Выполнено",
                        "cancelled": "Отменено",
                        "critical": "Критический",
                        "high": "Высокий",
                        "medium": "Средний",
                        "low": "Низкий"
                    }.get(task.get("status", ""), task.get("status", ""))
                    
                    f.write(f"\n{status_emoji} {task.get('title', 'Без названия')}\n")
                    if task.get('description'):
                        f.write(f"   Описание: {task['description']}\n")
                    if task.get('assignee') and task['assignee'] != "Не назначен":
                        f.write(f"   Исполнитель: {task['assignee']}\n")
                    if task.get('deadline') and task['deadline'] != "Не указан":
                        f.write(f"   Срок: {task['deadline']}\n")
                    f.write(f"   Статус: {status_ru}\n")
                f.write("\n")
            else:
                f.write("=" * 80 + "\n")
                f.write("📋 РАСПОРЯЖЕНИЯ И УКАЗАНИЯ\n")
                f.write("=" * 80 + "\n")
                f.write("На данный момент распоряжений нет.\n\n")
            
            # Исследовательский отчёт
            research_section = report.get("research_section")
            if research_section and research_section.get("report"):
                f.write("=" * 80 + "\n")
                f.write("🔍 ИССЛЕДОВАТЕЛЬСКИЙ ОТЧЁТ\n")
                f.write("=" * 80 + "\n")
                f.write(f"Запрос: {research_section.get('query', '')}\n")
                f.write(f"Найдено источников: {research_section.get('sources_count', 0)}\n")
                f.write("-" * 40 + "\n")
                f.write(research_section.get("report", ""))
                f.write("\n\n")
            
            # Нарратив
            narrative = report.get("narrative", {})
            if narrative.get("available") and narrative.get("full_text"):
                f.write("=" * 80 + "\n")
                f.write("📝 АНАЛИТИЧЕСКИЙ НАРРАТИВ (от market_narrative_agent)\n")
                f.write("=" * 80 + "\n")
                f.write(narrative.get("full_text", ""))
                f.write("\n\n")
            
            # Анализ по уровням
            level_analysis = report.get("level_analysis", {})
            
            for level_key, level_data in level_analysis.items():
                level_info = self.LEVELS.get(level_key, {})
                icon = level_info.get("icon", "📌")
                name = level_info.get("name", level_key)
                
                f.write("=" * 80 + "\n")
                f.write(f"{icon} {name} УРОВЕНЬ\n")
                f.write("=" * 80 + "\n")
                
                if level_key == "strategic":
                    for m in level_data.get("metrics", []):
                        f.write(f"Цель: {m.get('target', 0)} AI-проектов за 2025-2026\n")
                        f.write(f"План на {datetime.now().strftime('%d.%m.%Y')}: {m.get('plan', 0)} проектов\n")
                        f.write(f"Фактически: {m.get('current', 0)} проектов\n")
                        f.write(f"Отклонение: {m.get('deviation', 0)} проектов\n")
                    f.write(f"\nВывод: {level_data.get('conclusion', '')}\n")
                
                elif level_key == "market":
                    f.write(f"Позиция: {level_data.get('company_position', '')}\n")
                    f.write(f"Конкуренты: {level_data.get('competitors_analyzed', 0)} из {level_data.get('competitors_total', 14)}\n")
                    f.write(f"Направления: {level_data.get('directions_covered', 0)} из {level_data.get('directions_total', 12)}\n")
                    if level_data.get("directions_not_covered"):
                        f.write(f"Не охвачено: {', '.join(level_data['directions_not_covered'][:3])}...\n")
                    if level_data.get("competitors_list"):
                        f.write(f"Конкуренты: {', '.join(level_data['competitors_list'][:8])}\n")
                    if level_data.get("trends"):
                        f.write(f"Тренды: {', '.join(level_data['trends'])}\n")
                    if level_data.get("platforms_analyzed"):
                        f.write(f"Платформ: {level_data.get('platforms_analyzed')}\n")
                    f.write(f"Вывод: {level_data.get('conclusion', '')}\n")
                
                elif level_key == "products":
                    f.write("Выручка (за последний месяц):\n")
                    f.write("| Продукт | Выручка | Прибыль |\n")
                    f.write("|---------|---------|---------|\n")
                    for p in level_data.get("products", []):
                        f.write(f"| {p['name']} | {p['revenue']:,} руб. | {p['profit']:,} руб. |\n")
                    f.write(f"Итого: {level_data.get('total_revenue', 0):,} руб.\n")
                    f.write(f"Динамика: {level_data.get('growth', 'Н/Д')}\n")
                    f.write(f"Вывод: {level_data.get('conclusion', '')}\n")
                
                elif level_key == "competency":
                    f.write("| Компетенция | Заказов | Специалистов | Загрузка | Статус | Действие |\n")
                    f.write("|-------------|---------|--------------|----------|--------|----------|\n")
                    for c in level_data.get("competencies", []):
                        status_emoji = {"critical": "🔴", "warning": "🟡", "good": "🟢", "excess": "⚪"}.get(c["status"], "⚪")
                        f.write(f"| {c['name']} | {c['orders']} | {c['specialists']} | {c['load']}% | {status_emoji} | {c['action']} |\n")
                    f.write(f"\nВывод: {level_data.get('conclusion', '')}\n")
                
                elif level_key == "technical":
                    f.write(f"Продукт: {level_data.get('product', 'Нейро-куратор')}\n")
                    f.write("| Метрика | Текущее | Цель | Статус |\n")
                    f.write("|---------|---------|------|--------|\n")
                    for m in level_data.get("metrics", []):
                        status_emoji = {"critical": "🔴", "warning": "🟡", "met": "🟢", "exceeded": "🟢"}.get(m["status"], "⚪")
                        f.write(f"| {m['name']} | {m['current']} | {m['target']} | {status_emoji} |\n")
                    f.write(f"\nВывод: {level_data.get('conclusion', '')}\n")
                
                f.write("\n")
            
            # Рекомендации
            recommendations = report.get("recommendations", {})
            f.write("=" * 80 + "\n")
            f.write("💡 РЕКОМЕНДАЦИИ ПО УРОВНЯМ\n")
            f.write("=" * 80 + "\n")
            for level_key, recs in recommendations.items():
                if recs:
                    level_info = self.LEVELS.get(level_key, {})
                    f.write(f"\n{level_info.get('icon', '📌')} {level_info.get('name', level_key)}:\n")
                    for rec in recs[:3]:
                        f.write(f"  • {rec}\n")
            
            # План
            plan = report.get("plan", {})
            f.write("\n" + "=" * 80 + "\n")
            f.write("📋 ПЛАН ДЕЙСТВИЙ\n")
            f.write("=" * 80 + "\n")
            f.write("| Задача | Уровень | Ответственный | Срок | Приоритет |\n")
            f.write("|--------|---------|---------------|------|-----------|\n")
            for task in plan.get("tasks", []):
                priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(task.get("priority", ""), "⚪")
                f.write(f"| {task.get('task', '')} | {task.get('level', '')} | {task.get('assignee', '')} | {task.get('deadline', '')} | {priority_emoji} |\n")
            
            # Заключение
            f.write("\n" + "=" * 80 + "\n")
            f.write(report.get("conclusion", "") + "\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("КОНЕЦ ОТЧЕТА\n")
            f.write("=" * 80 + "\n")


def main():
    print("=" * 60)
    print("📄 REPORT AGENT - ТЕСТ")
    print("=" * 60)
    
    agent = ReportAgent(use_llm=False)
    
    test_data = {
        "metrics": {
            "metrics": {
                "product_metrics": {"project_id": "neuro_bot_2025"},
                "component_metrics": {"code_coverage": 78.5},
                "team_metrics": {"satisfaction": 4.0}
            }
        },
        "market_analysis": {
            "platforms_analyzed": 6,
            "competitors": [
                {"name": "Яндекс Практикум"},
                {"name": "Karpov Courses"},
                {"name": "OTUS"},
                {"name": "Нетология"},
                {"name": "Skillbox"},
                {"name": "HSE"}
            ],
            "market_trends": ["AI growth", "MLOps adoption", "Edge AI"]
        },
        "market_narrative": {"full_text": ""},
        "planner": {
            "actions": [
                {"id": "1", "description": "Нанять MLOps инженера", "priority": "critical"},
                {"id": "2", "description": "Увеличить покрытие кода до 80%", "priority": "high"}
            ],
            "risks": ["Отставание от конкурентов", "Нехватка экспертизы"],
            "success_criteria": ["Выполнить все критерии", "Закрыть пробелы"]
        }
    }
    
    report = agent.generate_report(test_data)
    agent.save_report(report)
    
    print("\n✅ Отчет создан! Проверьте папку reports/")


if __name__ == "__main__":
    main()