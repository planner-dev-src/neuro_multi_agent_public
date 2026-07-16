"""
Market Narrative Agent - отвечает за формирование аналитического нарратива
на основе рыночного анализа (конкуренты, тренды, позиционирование)
"""

import sys
import json
import requests
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

# Добавляем путь для импорта
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.agents.metrics_agent.metrics_agent import MetricsAgent


class MarketNarrativeAgent:
    """
    Агент для формирования аналитического нарратива о рынке
    (без вводных от руководителя — они идут в итоговый отчёт)
    """
    
    # ============================================================
    # 12 БАЗОВЫХ НАПРАВЛЕНИЙ КОМПАНИИ
    # ============================================================
    COMPANY_BASE_DIRECTIONS = {
        "cv": {"name": "Компьютерное зрение (CV)"},
        "nlp": {"name": "Обработка естественного языка (NLP)"},
        "ts": {"name": "Временные ряды (TS)"},
        "rl": {"name": "Обучение с подкреплением (RL)"},
        "s2t": {"name": "Аудио и распознавание речи (S2T)"},
        "gan": {"name": "Генеративно-состязательные нейросети (GAN)"},
        "ml": {"name": "Классическое машинное обучение (ML)"},
        "ga": {"name": "Генетические алгоритмы (GA)"},
        "pm": {"name": "Управление AI проектами"},
        "production": {"name": "Интеграция в PRODUCTION / MLOps"},
        "llm_agents": {"name": "AI-агенты на базе LLM"},
        "automl": {"name": "AUTOML"}
    }
    
    # ============================================================
    # УСИЛЕННЫЙ ПРОМПТ С ЖЁСТКИМ ТРЕБОВАНИЕМ РУССКОГО ЯЗЫКА
    # ============================================================
    NARRATIVE_PROMPT = """
Ты — профессиональный аналитик на русском языке.

================================================================================
❗ КРИТИЧЕСКИ ВАЖНО: ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ ❗
================================================================================
- НИ СЛОВА НА КИТАЙСКОМ, АНГЛИЙСКОМ, НЕМЕЦКОМ, ФРАНЦУЗСКОМ ИЛИ ЛЮБОМ ДРУГОМ ЯЗЫКЕ
- ВЕСЬ ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
- ТЕРМИНЫ (AI, ML, NLP, CV, GAN, MLOps, LLM, API, JSON, IT, HR, KPI) — ОСТАВЛЯЙ НА АНГЛИЙСКОМ
- ВСЁ ОСТАЛЬНОЕ — ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
================================================================================

Напиши подробный аналитический нарратив о РЫНКЕ AI-ОБРАЗОВАНИЯ в России.

ДАННЫЕ О РЫНКЕ:
{market_data}

Напиши текст по следующей структуре:

1. Введение — обзор рынка AI-образования в России
2. Анализ конкурентов — кто основные игроки, их специализация, сильные и слабые стороны
3. Позиционирование компании УИИ на рынке — её место среди конкурентов (УИИ — ЕДИНСТВЕННЫЙ игрок, который сочетает РАЗРАБОТКУ и ОБУЧЕНИЕ)
4. Ключевые тренды и направления развития рынка
5. Стратегические возможности для компании УИИ на основе рыночного анализа

Требования:
- ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
- Будь максимально подробным и аналитичным
- Используй все предоставленные данные о рынке и конкурентах
- Подчеркни, что УИИ — единственный игрок, сочетающий разработку и обучение
- НЕ РЕКОМЕНДУЙ стандартные технологии (Docker, Kubernetes, Python, Git, Linux, SQL)
- НЕ ИСПОЛЬЗУЙ вводные от руководителя (решения, поручения, риски)
- Используй профессиональный, но понятный язык
- Объём: 1500-2500 слов

================================================================================
❗ ЕЩЁ РАЗ: ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ ❗
================================================================================

ОТВЕТ:
"""
    
    def __init__(self):
        self.project_root = self._get_project_root()
        self.results_dir = self.project_root / "src" / "agents" / "market_narrative_agent" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._ollama_available = self._check_ollama()
        
        print(f"📝 Market Narrative Agent инициализирован")
        print(f"   Ollama доступен: {self._ollama_available}")
    
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
    
    def _get_metrics_data(self) -> Dict[str, Any]:
        try:
            agent = MetricsAgent()
            return {
                "competency_map": agent.build_competency_map(),
                "criteria_coverage": agent.analyze_criteria_coverage(),
                "impact_map": agent.build_impact_map(),
                "all_metrics": agent.get_all_metrics()
            }
        except Exception as e:
            print(f"⚠️ Ошибка загрузки метрик: {e}")
            return {}
    
    def generate_narrative(
        self,
        market_analysis: Dict[str, Any],
        metrics_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует аналитический нарратив о рынке
        
        Args:
            market_analysis: Данные от Market Analysis Agent
            metrics_data: Данные от Metrics Agent (опционально)
        
        Returns:
            Dict: {narrative, market_data, status}
        """
        print("📝 Генерация рыночного нарратива...")
        
        # Если не переданы метрики, пытаемся загрузить
        if metrics_data is None:
            metrics_data = self._get_metrics_data()
        
        # Формируем данные о рынке
        market_data = self._build_market_data(market_analysis, metrics_data)
        
        if self._ollama_available:
            print("🧠 Генерация через LLM...")
            print("   Пожалуйста, подождите, это может занять до 2-3 минут...")
            narrative = self._generate_with_llm(market_data)
            narrative = self._clean_narrative(narrative)
        else:
            print("⚠️ Ollama недоступен, используется fallback-генерация")
            narrative = self._generate_fallback_narrative(market_data)
        
        # Сохраняем
        filepath = self.save_narrative(narrative)
        
        print("✅ Нарратив сгенерирован")
        
        return {
            "narrative": narrative,
            "market_data": market_data,
            "filepath": filepath,
            "status": "completed",
            "length": len(narrative)
        }
    
    def _build_market_data(
        self, 
        market_analysis: Dict,
        metrics_data: Optional[Dict] = None
    ) -> str:
        """Формирует данные о рынке для промпта"""
        lines = []
        
        # ============================================================
        # 1. О КОМПАНИИ УИИ
        # ============================================================
        lines.append("=== О КОМПАНИИ УИИ ===")
        lines.append("Компания УИИ является безусловным лидером в области AI в России.")
        lines.append("КЛЮЧЕВОЕ ПРЕИМУЩЕСТВО (уникальное, есть ТОЛЬКО у УИИ):")
        lines.append("  - УИИ занимается РАЗРАБОТКОЙ И ОБУЧЕНИЕМ (одновременно)")
        lines.append("  - Конкуренты занимаются ТОЛЬКО ОБУЧЕНИЕМ (без разработки)")
        lines.append("  - Это УНИКАЛЬНОЕ сочетание, которого нет ни у кого из конкурентов")
        lines.append("")
        
        lines.append("БАЗОВЫЕ НАПРАВЛЕНИЯ КОМПАНИИ УИИ (12 направлений):")
        for d in self.COMPANY_BASE_DIRECTIONS.values():
            lines.append(f"- {d['name']}")
        lines.append("")
        
        # ============================================================
        # 2. О РЫНКЕ И КОНКУРЕНТАХ — ИЗВЛЕКАЕМ ИЗ BUNDLE
        # ============================================================
        lines.append("=== О РЫНКЕ И КОНКУРЕНТАХ ===")
        
        platforms_analyzed = 0
        total_courses = 0
        competitor_names = []
        competitor_details = []
        
        # ИЗВЛЕКАЕМ ИЗ BUNDLE
        if "bundle" in market_analysis:
            bundle = market_analysis.get("bundle")
            if bundle is not None:
                # Платформы
                if hasattr(bundle, "platforms_total"):
                    platforms_analyzed = getattr(bundle, "platforms_total", 0)
                if hasattr(bundle, "catalog_items_total_kept"):
                    total_courses = getattr(bundle, "catalog_items_total_kept", 0)
                
                # Конкуренты — из platform_positioning
                if hasattr(bundle, "platform_positioning"):
                    for pos in bundle.platform_positioning:
                        name = getattr(pos, "platform_name", "")
                        if name and name not in competitor_names:
                            competitor_names.append(name)
                            # Извлекаем направления и другую информацию
                            topics = getattr(pos, "dominant_topics", [])
                            competencies = getattr(pos, "dominant_competency_families", [])
                            signals = getattr(pos, "core_signals", [])
                            competitor_details.append({
                                "name": name,
                                "topics": topics[:3] if topics else [],
                                "competencies": competencies[:3] if competencies else [],
                                "signals": signals[:3] if signals else []
                            })
                
                # Конкуренты — из platform_aggregates
                if hasattr(bundle, "platform_aggregates"):
                    for agg in bundle.platform_aggregates:
                        name = getattr(agg, "platform_name", "")
                        if name and name not in competitor_names:
                            competitor_names.append(name)
                            competitor_details.append({
                                "name": name,
                                "topics": getattr(agg, "top_topics", [])[:3],
                                "competencies": getattr(agg, "top_competency_families", [])[:3],
                                "signals": getattr(agg, "top_core_signals", [])[:3]
                            })
        
        # Если bundle не дал данных, пробуем другие источники
        if platforms_analyzed == 0:
            if "platforms_analyzed" in market_analysis:
                platforms_analyzed = market_analysis.get("platforms_analyzed", 0)
            elif "platforms_total" in market_analysis:
                platforms_analyzed = market_analysis.get("platforms_total", 0)
        
        if total_courses == 0:
            if "total_courses" in market_analysis:
                total_courses = market_analysis.get("total_courses", 0)
            elif "courses_total" in market_analysis:
                total_courses = market_analysis.get("courses_total", 0)
        
        # Если competitor_details пуст, пробуем competitors
        if not competitor_details and "competitors" in market_analysis:
            comps = market_analysis.get("competitors", [])
            for comp in comps:
                if isinstance(comp, dict):
                    name = comp.get("name") or comp.get("platform_name")
                    if name and name not in competitor_names:
                        competitor_names.append(name)
                        competitor_details.append({
                            "name": name,
                            "topics": comp.get("directions", [])[:3],
                            "competencies": [],
                            "signals": []
                        })
                elif isinstance(comp, str) and comp not in competitor_names:
                    competitor_names.append(comp)
                    competitor_details.append({
                        "name": comp,
                        "topics": [],
                        "competencies": [],
                        "signals": []
                    })
        
        # Если всё ещё пусто, пробуем platform_reports
        if not competitor_details and "platform_reports" in market_analysis:
            reports = market_analysis.get("platform_reports", [])
            for report in reports:
                if isinstance(report, dict):
                    name = report.get("platform_name")
                    if name and name not in competitor_names:
                        competitor_names.append(name)
                        competitor_details.append({
                            "name": name,
                            "topics": [],
                            "competencies": [],
                            "signals": []
                        })
        
        lines.append(f"Проанализировано платформ: {platforms_analyzed}")
        lines.append(f"ВСЕГО курсов на ВСЕХ платформах (суммарно): {total_courses}")
        lines.append("")
        lines.append("Все перечисленные ниже конкуренты занимаются ТОЛЬКО ОБУЧЕНИЕМ.")
        lines.append("")
        
        if competitor_details:
            # Сортируем по имени
            competitor_details.sort(key=lambda x: x.get("name", ""))
            for i, comp in enumerate(competitor_details[:10], 1):
                name = comp.get("name", "Unknown")
                topics = comp.get("topics", [])
                competencies = comp.get("competencies", [])
                signals = comp.get("signals", [])
                
                details = []
                if topics:
                    details.append(f"направления: {', '.join(topics)}")
                if competencies:
                    details.append(f"компетенции: {', '.join(competencies)}")
                if signals:
                    details.append(f"сигналы: {', '.join(signals)}")
                
                if details:
                    lines.append(f"  {i}. {name} ({'; '.join(details)})")
                else:
                    lines.append(f"  {i}. {name}")
        else:
            lines.append("  - Данные о конкурентах отсутствуют")
        lines.append("")
        
        # ============================================================
        # 3. ТРЕНДЫ
        # ============================================================
        trends = market_analysis.get("trends", [])
        if not trends:
            trends = market_analysis.get("market_trends", [])
        
        # Если trends пуст, пробуем извлечь из bundle
        if not trends and "bundle" in market_analysis:
            bundle = market_analysis.get("bundle")
            if bundle is not None and hasattr(bundle, "trend_signals"):
                for signal in bundle.trend_signals:
                    topic = getattr(signal, "topic", "")
                    if topic:
                        trends.append({"direction": topic})
        
        if trends:
            lines.append("=== РЫНОЧНЫЕ ТРЕНДЫ ===")
            for trend in trends[:5]:
                if isinstance(trend, dict):
                    lines.append(f"- {trend.get('direction', trend.get('name', str(trend)))}")
                else:
                    lines.append(f"- {trend}")
            lines.append("")
        
        # ============================================================
        # 4. GAP-ЗОНЫ (если есть)
        # ============================================================
        gaps = market_analysis.get("gaps", [])
        if not gaps and "bundle" in market_analysis:
            bundle = market_analysis.get("bundle")
            if bundle is not None and hasattr(bundle, "competitive_gaps"):
                for gap in bundle.competitive_gaps:
                    topic = getattr(gap, "topic", "")
                    if topic:
                        gaps.append({"direction": topic, "opportunity": getattr(gap, "interpretation", "")})
        
        if gaps:
            lines.append("=== GAP-ЗОНЫ (потенциальные ниши) ===")
            for gap in gaps[:5]:
                if isinstance(gap, dict):
                    direction = gap.get("direction", gap.get("name", ""))
                    opportunity = gap.get("opportunity", "")
                    lines.append(f"- {direction}: {opportunity}")
                else:
                    lines.append(f"- {gap}")
            lines.append("")
        
        # ============================================================
        # 5. МЕТРИКИ (если есть)
        # ============================================================
        if metrics_data:
            competency_map = metrics_data.get("competency_map", {})
            gaps_comp = competency_map.get("gaps", [])
            if gaps_comp:
                lines.append("=== ПРОБЕЛЫ В КОМПЕТЕНЦИЯХ ===")
                for gap in gaps_comp[:3]:
                    lines.append(f"- {gap}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _generate_with_llm(self, market_data: str) -> str:
        try:
            prompt = self.NARRATIVE_PROMPT.format(market_data=market_data)
            
            print(f"📝 Длина промпта: {len(prompt)} символов")
            print("🧠 Отправка запроса к Ollama...")
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:7b",
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3,
                    "options": {
                        "num_predict": 8192,  # Увеличено для полного ответа
                        "top_k": 40,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1
                    }
                },
                timeout=300  # Увеличено до 300 секунд
            )
            
            print(f"📊 Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                narrative = result.get("response", "")
                print(f"📄 Длина ответа LLM: {len(narrative)} символов")
                
                if len(narrative) < 100:
                    print(f"⚠️ Ответ LLM слишком короткий: {len(narrative)} символов")
                    return self._generate_fallback_narrative(market_data)
                
                return narrative
            else:
                print(f"⚠️ Ошибка LLM: {response.status_code}")
                return self._generate_fallback_narrative(market_data)
                
        except requests.exceptions.Timeout:
            print("⚠️ Таймаут LLM (300 секунд)")
            return self._generate_fallback_narrative(market_data)
        except Exception as e:
            print(f"⚠️ Ошибка LLM: {e}")
            import traceback
            traceback.print_exc()
            return self._generate_fallback_narrative(market_data)
    
    def _clean_narrative(self, narrative: str) -> str:
        """Очищает нарратив от артефактов и лишних символов"""
        # Удаляем маркеры кода
        narrative = re.sub(r'```.*?```', '', narrative, flags=re.DOTALL)
        
        # Удаляем лишние переводы строк
        narrative = re.sub(r'\n{3,}', '\n\n', narrative)
        
        # Удаляем непечатаемые символы
        narrative = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', narrative)
        
        # Заменяем "Компания-заказчик" на "УИИ"
        narrative = narrative.replace("Компания-заказчик", "УИИ")
        
        # Удаляем артефакты типа "1. AI\n2. \n3. \n4. \n\nAI"
        narrative = re.sub(r'\d+\.\s*AI\s*\n', '', narrative)
        narrative = re.sub(r'\d+\.\s*\n', '', narrative)
        narrative = re.sub(r'\n\s*AI\s*\n', '\n', narrative)
        narrative = re.sub(r'AI\s*\n\s*\d+\.\s*\d+', '', narrative)
        narrative = re.sub(r'\d+\.\s*\d+[A-Z]*\s*', '', narrative)
        narrative = re.sub(r'[A-Z]{2,}\s*\n\s*[A-Z]{2,}', '', narrative)
        narrative = re.sub(r'\n\s*\d+\.\s*\n', '\n', narrative)
        narrative = re.sub(r'\d+\.\s*\d+\s*', '', narrative)
        narrative = re.sub(r'\d+\.\s*\d+\s*[A-Z]*', '', narrative)
        narrative = re.sub(r'AI\s*\n\s*AI', '', narrative)
        
        # Удаляем пустые пункты списка
        narrative = re.sub(r'•\s*\n', '', narrative)
        narrative = re.sub(r'-\s*\n', '', narrative)
        
        # Удаляем возможные китайские/другие символы
        narrative = re.sub(r'[^\u0400-\u04FFa-zA-Z0-9\s.,!?\-;:()"\'"]+', '', narrative)
        
        # Удаляем повторяющиеся пробелы
        narrative = re.sub(r' +', ' ', narrative)
        
        return narrative.strip()
    
    def _generate_fallback_narrative(self, market_data: str) -> str:
        narrative = []
        narrative.append("# АНАЛИТИЧЕСКИЙ НАРРАТИВ: РЫНОК AI-ОБРАЗОВАНИЯ\n")
        narrative.append("\n## 1. Введение\n")
        narrative.append("Рынок AI-образования в России активно развивается. Ключевые игроки представлены на платформах, которые предлагают курсы по различным направлениям AI.\n")
        narrative.append("\n## 2. Конкуренты\n")
        narrative.append("Все конкуренты занимаются ТОЛЬКО ОБУЧЕНИЕМ. Они НЕ занимаются разработкой.\n")
        narrative.append(market_data if market_data else "Данные о конкурентах отсутствуют.\n")
        narrative.append("\n## 3. Позиционирование компании УИИ\n")
        narrative.append("Компания УИИ является ЕДИНСТВЕННЫМ игроком, который сочетает РАЗРАБОТКУ и ОБУЧЕНИЕ.\n")
        narrative.append("Это уникальное преимущество, которого нет ни у кого из конкурентов.\n")
        narrative.append("\n## 4. Тренды\n")
        narrative.append("Основные тренды: рост спроса на AI-специалистов, развитие MLOps, внедрение LLM-агентов в бизнес-процессы.\n")
        narrative.append("\n## 5. Стратегические возможности\n")
        narrative.append("Для компании УИИ открываются следующие возможности:\n")
        narrative.append("- Укрепление позиции лидера через развитие уникального сочетания разработки и обучения\n")
        narrative.append("- Расширение портфеля образовательных программ по востребованным направлениям\n")
        narrative.append("- Интеграция обучения с реальными проектами для ускорения подготовки специалистов\n")
        return "\n".join(narrative)
    
    def save_narrative(self, narrative: str, filename: Optional[str] = None) -> str:
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"narrative_{timestamp}.txt"
        
        if not narrative or len(narrative.strip()) < 10:
            print("⚠️ ВНИМАНИЕ: нарратив пустой!")
            narrative = self._generate_fallback_narrative("")
        
        filepath = self.results_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(narrative)
        
        print(f"💾 Нарратив сохранен: {filepath} (длина: {len(narrative)} символов)")
        
        latest_path = self.results_dir / "narrative_latest.txt"
        with open(latest_path, 'w', encoding='utf-8') as f:
            f.write(narrative)
        
        return str(filepath)
    
    def load_latest_narrative(self) -> Optional[str]:
        latest_path = self.results_dir / "narrative_latest.txt"
        if latest_path.exists():
            with open(latest_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None


def main():
    print("=" * 60)
    print("📝 MARKET NARRATIVE AGENT - ТЕСТ")
    print("=" * 60)
    
    agent = MarketNarrativeAgent()
    
    market_analysis_files = list(Path("src/agents/market_analysis_agent/results").glob("market_analysis_*.json"))
    
    if market_analysis_files:
        latest = max(market_analysis_files, key=lambda x: x.stat().st_mtime)
        with open(latest, 'r', encoding='utf-8') as f:
            market_analysis = json.load(f)
        print(f"📁 Загружен рыночный анализ: {latest.name}")
    else:
        market_analysis = {}
        print("⚠️ Рыночный анализ не найден")
    
    result = agent.generate_narrative(market_analysis)
    narrative = result.get("narrative", "")
    
    print("\n" + "=" * 60)
    print("📄 СГЕНЕРИРОВАННЫЙ НАРРАТИВ (первые 1000 символов):")
    print("=" * 60)
    print(narrative[:1000] + "..." if len(narrative) > 1000 else narrative)
    print("\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЕН!")


if __name__ == "__main__":
    main()