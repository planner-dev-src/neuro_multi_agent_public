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

# Импорт единого реестра направлений компании
from src.common.keywords import COMPANY_DIRECTIONS, get_all_direction_names


class MarketNarrativeAgent:
    """
    Агент для формирования аналитического нарратива о рынке
    (без вводных от руководителя — они идут в итоговый отчёт)
    """
    
    # ============================================================
    # 12 БАЗОВЫХ НАПРАВЛЕНИЙ КОМПАНИИ (из keywords.py)
    # ============================================================
    # Используем COMPANY_DIRECTIONS из единого реестра
    COMPANY_BASE_DIRECTIONS = COMPANY_DIRECTIONS
    
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
        print(f"   Направлений компании: {len(self.COMPANY_BASE_DIRECTIONS)} (из keywords.py)")
    
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
        """Генерирует аналитический нарратив о рынке"""
        print("📝 Генерация рыночного нарратива...")
        
        if metrics_data is None:
            metrics_data = self._get_metrics_data()
        
        market_data = self._build_market_data(market_analysis, metrics_data)
        
        if self._ollama_available:
            print("🧠 Генерация через LLM...")
            print("   Пожалуйста, подождите, это может занять до 2-3 минут...")
            narrative = self._generate_with_llm(market_data)
            narrative = self._clean_narrative(narrative)
        else:
            print("⚠️ Ollama недоступен, используется fallback-генерация")
            narrative = self._generate_fallback_narrative(market_data)
        
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
        
        # 1. О компании УИИ
        lines.append("=== О КОМПАНИИ УИИ ===")
        lines.append("Компания УИИ является безусловным лидером в области AI в России.")
        lines.append("КЛЮЧЕВОЕ ПРЕИМУЩЕСТВО (уникальное, есть ТОЛЬКО у УИИ):")
        lines.append("  - УИИ занимается РАЗРАБОТКОЙ И ОБУЧЕНИЕМ (одновременно)")
        lines.append("  - Конкуренты занимаются ТОЛЬКО ОБУЧЕНИЕМ (без разработки)")
        lines.append("  - Это УНИКАЛЬНОЕ сочетание, которого нет ни у кого из конкурентов")
        lines.append("")
        
        # Используем направления из keywords.py
        lines.append(f"БАЗОВЫЕ НАПРАВЛЕНИЯ КОМПАНИИ УИИ ({len(self.COMPANY_BASE_DIRECTIONS)} направлений):")
        direction_names = get_all_direction_names()
        for name in direction_names:
            lines.append(f"- {name}")
        lines.append("")
        
        # 2. О рынке и конкурентах
        lines.append("=== О РЫНКЕ И КОНКУРЕНТАХ ===")
        
        platforms_analyzed = 0
        total_courses = 0
        competitor_names = []
        competitor_details = []
        
        if "bundle" in market_analysis:
            bundle = market_analysis.get("bundle")
            if bundle is not None:
                if hasattr(bundle, "platforms_total"):
                    platforms_analyzed = getattr(bundle, "platforms_total", 0)
                if hasattr(bundle, "catalog_items_total_kept"):
                    total_courses = getattr(bundle, "catalog_items_total_kept", 0)
                
                if hasattr(bundle, "platform_positioning"):
                    for pos in bundle.platform_positioning:
                        name = getattr(pos, "platform_name", "")
                        if name and name not in competitor_names:
                            competitor_names.append(name)
                            topics = getattr(pos, "dominant_topics", [])
                            competencies = getattr(pos, "dominant_competency_families", [])
                            signals = getattr(pos, "core_signals", [])
                            competitor_details.append({
                                "name": name,
                                "topics": topics[:3] if topics else [],
                                "competencies": competencies[:3] if competencies else [],
                                "signals": signals[:3] if signals else []
                            })
                
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
        
        if platforms_analyzed == 0:
            platforms_analyzed = market_analysis.get("platforms_analyzed", market_analysis.get("platforms_total", 0))
        if total_courses == 0:
            total_courses = market_analysis.get("total_courses", market_analysis.get("courses_total", 0))
        
        if not competitor_details and "competitors" in market_analysis:
            for comp in market_analysis.get("competitors", []):
                if isinstance(comp, dict):
                    name = comp.get("name") or comp.get("platform_name")
                    if name and name not in competitor_names:
                        competitor_names.append(name)
                        competitor_details.append({
                            "name": name, "topics": comp.get("directions", [])[:3],
                            "competencies": [], "signals": []
                        })
                elif isinstance(comp, str) and comp not in competitor_names:
                    competitor_names.append(comp)
                    competitor_details.append({"name": comp, "topics": [], "competencies": [], "signals": []})
        
        if not competitor_details and "platform_reports" in market_analysis:
            for report in market_analysis.get("platform_reports", []):
                if isinstance(report, dict):
                    name = report.get("platform_name")
                    if name and name not in competitor_names:
                        competitor_names.append(name)
                        competitor_details.append({"name": name, "topics": [], "competencies": [], "signals": []})
        
        lines.append(f"Проанализировано платформ: {platforms_analyzed}")
        lines.append(f"ВСЕГО курсов на ВСЕХ платформах (суммарно): {total_courses}")
        lines.append("")
        lines.append("Все перечисленные ниже конкуренты занимаются ТОЛЬКО ОБУЧЕНИЕМ.")
        lines.append("")
        
        if competitor_details:
            competitor_details.sort(key=lambda x: x.get("name", ""))
            for i, comp in enumerate(competitor_details[:10], 1):
                details = []
                if comp.get("topics"): details.append(f"направления: {', '.join(comp['topics'])}")
                if comp.get("competencies"): details.append(f"компетенции: {', '.join(comp['competencies'])}")
                if comp.get("signals"): details.append(f"сигналы: {', '.join(comp['signals'])}")
                if details:
                    lines.append(f"  {i}. {comp['name']} ({'; '.join(details)})")
                else:
                    lines.append(f"  {i}. {comp['name']}")
        else:
            lines.append("  - Данные о конкурентах отсутствуют")
        lines.append("")
        
        # 3. Тренды
        trends = market_analysis.get("trends", market_analysis.get("market_trends", []))
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
        
        # 4. Gap-зоны
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
                    lines.append(f"- {gap.get('direction', gap.get('name', ''))}: {gap.get('opportunity', '')}")
                else:
                    lines.append(f"- {gap}")
            lines.append("")
        
        # 5. Метрики
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
                    "prompt": prompt, "stream": False, "temperature": 0.3,
                    "options": {"num_predict": 8192, "top_k": 40, "top_p": 0.9, "repeat_penalty": 1.1}
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                narrative = result.get("response", "")
                print(f"📄 Длина ответа LLM: {len(narrative)} символов")
                if len(narrative) < 100:
                    print(f"⚠️ Ответ LLM слишком короткий")
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
            return self._generate_fallback_narrative(market_data)
    
    def _clean_narrative(self, narrative: str) -> str:
        narrative = re.sub(r'```.*?```', '', narrative, flags=re.DOTALL)
        narrative = re.sub(r'\n{3,}', '\n\n', narrative)
        narrative = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', narrative)
        narrative = narrative.replace("Компания-заказчик", "УИИ")
        narrative = re.sub(r'\d+\.\s*AI\s*\n', '', narrative)
        narrative = re.sub(r'\d+\.\s*\n', '', narrative)
        narrative = re.sub(r'•\s*\n', '', narrative)
        narrative = re.sub(r'-\s*\n', '', narrative)
        narrative = re.sub(r'[^\u0400-\u04FFa-zA-Z0-9\s.,!?\-;:()"\'"]+', '', narrative)
        narrative = re.sub(r' +', ' ', narrative)
        return narrative.strip()
    
    def _generate_fallback_narrative(self, market_data: str) -> str:
        narrative = []
        narrative.append("# АНАЛИТИЧЕСКИЙ ОБЗОР: РЫНОК AI-ОБРАЗОВАНИЯ\n")
        narrative.append("\n## 1. Введение\n")
        narrative.append("Рынок AI-образования в России активно развивается.\n")
        narrative.append("\n## 2. Конкуренты\n")
        narrative.append("Все конкуренты занимаются ТОЛЬКО ОБУЧЕНИЕМ.\n")
        narrative.append(market_data if market_data else "Данные о конкурентах отсутствуют.\n")
        narrative.append("\n## 3. Позиционирование компании УИИ\n")
        narrative.append("Компания УИИ — ЕДИНСТВЕННЫЙ игрок, сочетающий РАЗРАБОТКУ и ОБУЧЕНИЕ.\n")
        narrative.append("\n## 4. Тренды\n")
        narrative.append("Рост спроса на AI-специалистов, развитие MLOps, внедрение LLM-агентов.\n")
        narrative.append("\n## 5. Стратегические возможности\n")
        narrative.append("- Укрепление позиции лидера\n")
        narrative.append("- Расширение образовательных программ\n")
        narrative.append("- Интеграция обучения с реальными проектами\n")
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
        print(f"💾 Нарратив сохранен: {filepath} ({len(narrative)} символов)")
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
    print("📝 MARKET NARRATIVE AGENT - ТЕСТ (с keywords.py)")
    print("=" * 60)
    
    agent = MarketNarrativeAgent()
    print(f"Направлений компании: {len(agent.COMPANY_BASE_DIRECTIONS)}")
    print(f"Названия: {get_all_direction_names()[:3]}...")
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)


if __name__ == "__main__":
    main()