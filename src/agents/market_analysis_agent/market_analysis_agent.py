"""
Market Analysis Agent - анализ рыночных данных с учетом метрик
"""

import re
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

# Импорт единого реестра направлений и ключевых слов
from src.common.keywords import (
    COMPANY_DIRECTIONS,
    get_direction_by_keyword,
    get_all_direction_names,
    is_relevant_text
)


@dataclass
class CompetitorAnalysis:
    """Анализ конкурента"""
    name: str
    courses_count: int = 0
    directions: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    positioning: str = ""


@dataclass
class MarketAnalysisResult:
    """Результат анализа рынка"""
    platforms_analyzed: int = 0
    total_courses: int = 0
    competitors: List[CompetitorAnalysis] = field(default_factory=list)
    trends: List[Dict[str, Any]] = field(default_factory=list)
    gaps: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    generated_at: str = ""


class MarketAnalysisAgent:
    """
    Агент для анализа рыночных данных.

    Отвечает за:
    - Анализ конкурентной среды
    - Выявление рыночных трендов
    - Определение gap-зон
    - Формирование аналитических выводов

    Использует единый реестр направлений из keywords.py.
    """

    # Базовые направления компании (из keywords.py)
    COMPANY_DIRECTIONS = get_all_direction_names()

    def __init__(self):
        self.project_root = self._get_project_root()
        self.results_dir = self.project_root / "src" / "agents" / "market_analysis_agent" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_root(self) -> Path:
        """Определяет корень проекта"""
        current = Path(__file__).resolve().parent
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
            if (parent / "src" / "agents").exists():
                return parent
        return current.parent.parent.parent

    def analyze(
        self,
        market_data: Dict[str, Any],
        metrics_data: Optional[Dict[str, Any]] = None
    ) -> MarketAnalysisResult:
        """Выполняет анализ рыночных данных"""
        print("📊 Запуск анализа рыночных данных...")

        if "summary" in market_data:
            summary = market_data.get("summary", {})
            platforms = summary.get("platforms", [])
            bundle = market_data.get("bundle")
            if bundle and hasattr(bundle, "platforms"):
                platforms = bundle.platforms if hasattr(bundle, "platforms") else platforms
            if bundle and hasattr(bundle, "catalog_items"):
                total_courses = len(bundle.catalog_items) if hasattr(bundle, "catalog_items") else 0
            else:
                total_courses = 0
        else:
            platforms = market_data.get("platforms", [])
            total_courses = 0

        result = MarketAnalysisResult(generated_at=datetime.now().isoformat())
        result.platforms_analyzed = len(platforms)

        if total_courses == 0:
            for platform in platforms:
                courses = platform.get("courses", [])
                total_courses += len(courses)
        result.total_courses = total_courses

        result.competitors = self._analyze_competitors(platforms)
        result.trends = self._analyze_trends(platforms)
        result.gaps = self._analyze_gaps(platforms, metrics_data)
        result.findings = self._generate_findings(result)

        print(f"✅ Анализ завершён: {result.platforms_analyzed} платформ, "
              f"{result.total_courses} курсов, {len(result.competitors)} конкурентов, "
              f"{len(result.gaps)} gap-зон")

        return result

    def _analyze_competitors(self, platforms: List[Dict]) -> List[CompetitorAnalysis]:
        """Анализирует конкурентов на основе данных платформ"""
        competitors = []

        for platform in platforms:
            name = platform.get("name", "Неизвестная платформа")
            courses = platform.get("courses", platform.get("catalog_items", []))

            # Определяем направления через keywords.py
            directions = []
            for course in courses:
                title = course.get("title", course.get("name", ""))
                description = course.get("description", "")
                combined = f"{title} {description}"
                direction = get_direction_by_keyword(combined)
                if direction and direction not in directions:
                    directions.append(direction)

            if not directions:
                continue

            strengths, weaknesses = self._analyze_strengths_weaknesses(platform, courses)

            competitor = CompetitorAnalysis(
                name=name,
                courses_count=len(courses),
                directions=directions[:5],
                strengths=strengths[:3],
                weaknesses=weaknesses[:3],
                positioning=self._determine_positioning(platform, courses)
            )
            competitors.append(competitor)

        competitors.sort(key=lambda x: x.courses_count, reverse=True)
        return competitors

    def _analyze_strengths_weaknesses(
        self, platform: Dict, courses: List[Dict]
    ) -> tuple[List[str], List[str]]:
        """Анализирует сильные и слабые стороны платформы"""
        strengths, weaknesses = [], []
        courses_count = len(courses)

        if courses_count > 50:
            strengths.append("Большой выбор курсов")
        elif courses_count > 20:
            strengths.append("Хороший выбор курсов")
        elif courses_count > 10:
            strengths.append("Достаточный выбор курсов")

        ai_courses = 0
        for course in courses:
            title = course.get("title", course.get("name", ""))
            description = course.get("description", "")
            combined = f"{title} {description}"
            if is_relevant_text(combined):
                ai_courses += 1

        ai_ratio = ai_courses / max(courses_count, 1)
        if ai_ratio > 0.3:
            strengths.append("Специализация на AI")
        if ai_ratio > 0.5:
            strengths.append("Глубокая AI-специализация")

        if courses_count < 10:
            weaknesses.append("Малый выбор курсов")
        if ai_ratio < 0.1:
            weaknesses.append("Недостаточно AI-специализации")
        if courses_count > 0 and len([c for c in courses if get_direction_by_keyword(
            c.get("title", "") + " " + c.get("description", "")
        )]) < 2:
            weaknesses.append("Узкая специализация")

        return strengths, weaknesses

    def _determine_positioning(self, platform: Dict, courses: List) -> str:
        """Определяет позиционирование платформы"""
        name = platform.get("name", "").lower()
        description = platform.get("description", "").lower()
        combined = f"{name} {description}"

        if any(kw in combined for kw in ["deeplearning", "coursera", "datacamp"]):
            return "Международный лидер"
        elif any(kw in combined for kw in ["otus", "karpov", "практикум", "yandex", "netology", "skillbox"]):
            return "Российский лидер"
        elif any(kw in combined for kw in ["школа", "анализ", "академия"]):
            return "Экспертное образование"
        return "Нишевый игрок"

    def _analyze_trends(self, platforms: List[Dict]) -> List[Dict[str, Any]]:
        """Анализирует тренды на основе данных платформ"""
        all_directions = {}
        for platform in platforms:
            courses = platform.get("courses", platform.get("catalog_items", []))
            for course in courses:
                title = course.get("title", course.get("name", ""))
                description = course.get("description", "")
                direction = get_direction_by_keyword(f"{title} {description}")
                if direction:
                    all_directions[direction] = all_directions.get(direction, 0) + 1

        trends = []
        for direction, count in sorted(all_directions.items(), key=lambda x: x[1], reverse=True)[:10]:
            if count >= 2:
                trend_level = "high" if count >= 4 else "medium" if count >= 2 else "low"
                trends.append({
                    "direction": direction,
                    "platforms_count": count,
                    "trend_level": trend_level,
                    "description": f"Направление представлено на {count} платформах"
                })

        return trends

    def _analyze_gaps(
        self, platforms: List[Dict], metrics_data: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Анализирует gap-зоны"""
        all_directions = set()
        for platform in platforms:
            courses = platform.get("courses", platform.get("catalog_items", []))
            for course in courses:
                title = course.get("title", course.get("name", ""))
                description = course.get("description", "")
                direction = get_direction_by_keyword(f"{title} {description}")
                if direction:
                    all_directions.add(direction)

        gaps = []
        missing = [d for d in self.COMPANY_DIRECTIONS if d not in all_directions]

        high_priority_kw = ["LLM", "MLOps", "AUTOML", "AI-агенты", "GAN"]
        for direction in missing:
            is_high = any(kw in direction for kw in high_priority_kw)
            gaps.append({
                "type": "missing_direction",
                "direction": direction,
                "opportunity": "Не представлено на рынке — потенциальная ниша",
                "priority": "high" if is_high else "medium"
            })

        if metrics_data:
            competency_map = metrics_data.get("competency_map", {})
            for gap in competency_map.get("gaps", []):
                if isinstance(gap, str) and gap.strip():
                    if not any(g.get("direction") == gap for g in gaps):
                        gaps.append({
                            "type": "competency_gap",
                            "direction": gap,
                            "opportunity": "Пробел в компетенциях — требуется развитие",
                            "priority": "high"
                        })

        return gaps

    def _generate_findings(self, result: MarketAnalysisResult) -> List[str]:
        """Генерирует ключевые выводы"""
        findings = []

        if result.platforms_analyzed > 0:
            findings.append(f"Проанализировано {result.platforms_analyzed} платформ, "
                          f"всего {result.total_courses} курсов")
        else:
            findings.append("Анализ рынка не выполнен — нет данных о платформах")

        if result.competitors:
            findings.append(f"Основной конкурент: {result.competitors[0].name} "
                          f"({result.competitors[0].courses_count} курсов)")
            if len(result.competitors) > 1:
                findings.append(f"Второй конкурент: {result.competitors[1].name} "
                              f"({result.competitors[1].courses_count} курсов)")

        if result.trends:
            findings.append(f"Ключевой тренд: {result.trends[0]['direction']} "
                          f"(представлен на {result.trends[0]['platforms_count']} платформах)")

        high_gaps = [g for g in result.gaps if g.get("priority") == "high"]
        if high_gaps:
            gap_names = [g.get("direction", "") for g in high_gaps]
            findings.append(f"Выявлено {len(high_gaps)} приоритетных gap-зон: "
                          f"{', '.join(gap_names[:3])}"
                          f"{'...' if len(gap_names) > 3 else ''}")

        return findings

    def analyze_from_file(self, filepath: str) -> MarketAnalysisResult:
        with open(filepath, 'r', encoding='utf-8') as f:
            return self.analyze(json.load(f))

    def save_results(self, result: MarketAnalysisResult, filename: Optional[str] = None) -> str:
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"market_analysis_{timestamp}.json"

        filepath = self.results_dir / filename
        data = {
            "platforms_analyzed": result.platforms_analyzed,
            "total_courses": result.total_courses,
            "competitors": [
                {"name": c.name, "courses_count": c.courses_count,
                 "directions": c.directions, "strengths": c.strengths,
                 "weaknesses": c.weaknesses, "positioning": c.positioning}
                for c in result.competitors
            ],
            "trends": result.trends,
            "gaps": result.gaps,
            "findings": result.findings,
            "generated_at": result.generated_at
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 Результаты анализа сохранены: {filepath}")
        return str(filepath)


def main():
    print("=" * 60)
    print("📊 MARKET ANALYSIS AGENT - ТЕСТ (с keywords.py)")
    print("=" * 60)

    agent = MarketAnalysisAgent()
    print(f"Направлений компании: {len(agent.COMPANY_DIRECTIONS)}")
    print(f"Пример: {agent.COMPANY_DIRECTIONS[:3]}...")

    # Тест get_direction_by_keyword
    test_kw = ["computer vision", "nlp", "mlops", "кулинария"]
    for kw in test_kw:
        direction = get_direction_by_keyword(kw)
        print(f"  '{kw}' → {direction or 'не найдено'}")

    print("\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)


if __name__ == "__main__":
    main()