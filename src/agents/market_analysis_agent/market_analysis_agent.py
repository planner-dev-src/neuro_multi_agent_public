"""
Market Analysis Agent - анализ рыночных данных с учетом метрик
"""

import re
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field


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
    """

    # Базовые направления компании (12 направлений)
    COMPANY_DIRECTIONS = [
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
        """
        Выполняет анализ рыночных данных

        Args:
            market_data: Данные от market_agent (платформы, курсы) или результат run_market_analysis
            metrics_data: Данные от metrics_agent (опционально)

        Returns:
            MarketAnalysisResult: Результаты анализа
        """
        print("📊 Запуск анализа рыночных данных...")

        # Если передан результат от run_market_analysis, извлекаем данные
        if "summary" in market_data:
            # Это результат от run_market_analysis
            summary = market_data.get("summary", {})
            platforms = summary.get("platforms", [])
            # Также можем извлечь из bundle
            bundle = market_data.get("bundle")
            if bundle and hasattr(bundle, "platforms"):
                platforms = bundle.platforms if hasattr(bundle, "platforms") else platforms
            if bundle and hasattr(bundle, "catalog_items"):
                total_courses = len(bundle.catalog_items) if hasattr(bundle, "catalog_items") else 0
            else:
                total_courses = 0
        else:
            # Обычный формат: {"platforms": [...]}
            platforms = market_data.get("platforms", [])
            total_courses = 0

        result = MarketAnalysisResult(
            generated_at=datetime.now().isoformat()
        )

        # 1. Анализ платформ
        result.platforms_analyzed = len(platforms)

        # 2. Подсчёт курсов
        if total_courses == 0:
            for platform in platforms:
                courses = platform.get("courses", [])
                total_courses += len(courses)
        result.total_courses = total_courses

        # 3. Анализ конкурентов
        result.competitors = self._analyze_competitors(platforms)

        # 4. Анализ трендов
        result.trends = self._analyze_trends(platforms)

        # 5. Анализ gap-зон
        result.gaps = self._analyze_gaps(platforms, metrics_data)

        # 6. Формирование выводов
        result.findings = self._generate_findings(result)

        print(f"✅ Анализ завершён: {result.platforms_analyzed} платформ, "
              f"{result.total_courses} курсов, "
              f"{len(result.competitors)} конкурентов, "
              f"{len(result.gaps)} gap-зон")

        return result

    def _analyze_competitors(self, platforms: List[Dict]) -> List[CompetitorAnalysis]:
        """Анализирует конкурентов на основе данных платформ"""
        competitors = []

        for platform in platforms:
            name = platform.get("name", "Неизвестная платформа")
            # Если courses нет, пробуем catalog_items
            courses = platform.get("courses", [])
            if not courses:
                courses = platform.get("catalog_items", [])

            # Определяем направления
            directions = self._extract_directions(courses)

            # Анализируем сильные и слабые стороны
            strengths, weaknesses = self._analyze_strengths_weaknesses(
                platform, courses
            )

            # Если нет направлений, пропускаем
            if not directions:
                continue

            competitor = CompetitorAnalysis(
                name=name,
                courses_count=len(courses),
                directions=directions[:5],
                strengths=strengths[:3],
                weaknesses=weaknesses[:3],
                positioning=self._determine_positioning(platform, courses)
            )
            competitors.append(competitor)

        # Сортируем по количеству курсов (по убыванию)
        competitors.sort(key=lambda x: x.courses_count, reverse=True)

        return competitors

    def _extract_directions(self, courses: List[Dict]) -> List[str]:
        """Извлекает направления из курсов"""
        directions = []
        direction_keywords = {
            "Компьютерное зрение (CV)": ["computer vision", "opencv", "image", "cv", "зрение"],
            "Обработка естественного языка (NLP)": ["nlp", "natural language", "text", "bert", "язык"],
            "Временные ряды (TS)": ["time series", "forecast", "predict", "ts", "ряды"],
            "Обучение с подкреплением (RL)": ["reinforcement", "rl", "q-learning", "подкрепление"],
            "Аудио и распознавание речи (S2T)": ["speech", "audio", "whisper", "s2t", "аудио", "речь"],
            "Генеративно-состязательные нейросети (GAN)": ["gan", "generative", "diffusion", "генератив"],
            "Классическое машинное обучение (ML)": ["ml", "regression", "classification", "машинное обучение"],
            "Генетические алгоритмы (GA)": ["genetic", "ga", "evolutionary", "генетич"],
            "Управление AI проектами": ["project management", "pm", "agile", "управление проектами"],
            "Интеграция в PRODUCTION / MLOps": ["mlops", "production", "deployment", "интеграция"],
            "AI-агенты на базе LLM": ["llm", "gpt", "agent", "langchain", "агенты"],
            "AUTOML": ["automl", "auto ml", "hyperopt"]
        }

        for course in courses:
            title = course.get("title", "").lower()
            description = course.get("description", "").lower()
            name = course.get("name", "").lower()
            combined = f"{title} {description} {name}"

            for direction, keywords in direction_keywords.items():
                if any(kw in combined for kw in keywords):
                    if direction not in directions:
                        directions.append(direction)

        return directions

    def _analyze_strengths_weaknesses(
        self,
        platform: Dict,
        courses: List[Dict]
    ) -> tuple[List[str], List[str]]:
        """Анализирует сильные и слабые стороны платформы"""
        strengths = []
        weaknesses = []

        courses_count = len(courses)

        # Сильные стороны
        if courses_count > 50:
            strengths.append("Большой выбор курсов")
        elif courses_count > 20:
            strengths.append("Хороший выбор курсов")
        elif courses_count > 10:
            strengths.append("Достаточный выбор курсов")

        # Проверяем наличие AI-специализации
        ai_courses = 0
        for course in courses:
            title = course.get("title", "").lower()
            description = course.get("description", "").lower()
            combined = f"{title} {description}"
            if any(kw in combined for kw in ["ai", "artificial intelligence", "нейросет", "машинное", "machine learning", "deep learning"]):
                ai_courses += 1

        ai_ratio = ai_courses / max(courses_count, 1)
        if ai_ratio > 0.3:
            strengths.append("Специализация на AI")
        if ai_ratio > 0.5:
            strengths.append("Глубокая AI-специализация")

        # Слабые стороны
        if courses_count < 10:
            weaknesses.append("Малый выбор курсов")

        if ai_ratio < 0.1:
            weaknesses.append("Недостаточно AI-специализации")

        if courses_count > 0 and len(self._extract_directions(courses)) < 2:
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
        else:
            return "Нишевый игрок"

    def _analyze_trends(self, platforms: List[Dict]) -> List[Dict[str, Any]]:
        """Анализирует тренды на основе данных платформ"""
        trends = []

        # Собираем все направления
        all_directions = {}
        for platform in platforms:
            courses = platform.get("courses", [])
            if not courses:
                courses = platform.get("catalog_items", [])
            platform_directions = self._extract_directions(courses)

            for direction in platform_directions:
                all_directions[direction] = all_directions.get(direction, 0) + 1

        # Формируем тренды
        for direction, count in sorted(all_directions.items(), key=lambda x: x[1], reverse=True)[:10]:
            if count >= 2:
                trend_level = "high" if count >= 4 else "medium" if count >= 2 else "low"
                trends.append({
                    "direction": direction,
                    "platforms_count": count,
                    "trend_level": trend_level,
                    "description": f"Направление {direction} представлено на {count} платформах"
                })

        return trends

    def _analyze_gaps(
        self,
        platforms: List[Dict],
        metrics_data: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Анализирует gap-зоны"""
        gaps = []

        # 1. Направления, которые не представлены на рынке
        all_directions = set()
        for platform in platforms:
            courses = platform.get("courses", [])
            if not courses:
                courses = platform.get("catalog_items", [])
            directions = self._extract_directions(courses)
            all_directions.update(directions)

        # Находим отсутствующие направления
        missing_directions = [
            d for d in self.COMPANY_DIRECTIONS
            if d not in all_directions
        ]

        # Приоритет для отсутствующих направлений
        high_priority = ["LLM", "MLOps", "AUTOML", "AI-агенты", "GAN"]
        for direction in missing_directions:
            is_high = any(kw in direction for kw in high_priority)
            gaps.append({
                "type": "missing_direction",
                "direction": direction,
                "opportunity": "Не представлено на рынке — потенциальная ниша",
                "priority": "high" if is_high else "medium"
            })

        # 2. Если есть метрики, учитываем их
        if metrics_data:
            competency_map = metrics_data.get("competency_map", {})
            gaps_from_metrics = competency_map.get("gaps", [])
            for gap in gaps_from_metrics:
                if isinstance(gap, str) and gap.strip():
                    # Проверяем, не дублируется ли уже
                    existing = [g for g in gaps if g.get("direction") == gap]
                    if not existing:
                        gaps.append({
                            "type": "competency_gap",
                            "direction": gap,
                            "opportunity": "Пробел в компетенциях — требуется развитие",
                            "priority": "high"
                        })

        return gaps

    def _generate_findings(self, result: MarketAnalysisResult) -> List[str]:
        """Генерирует ключевые выводы на основе анализа"""
        findings = []

        # 1. О рынке
        if result.platforms_analyzed > 0:
            findings.append(f"Проанализировано {result.platforms_analyzed} платформ, "
                          f"всего {result.total_courses} курсов")
        else:
            findings.append("Анализ рынка не выполнен — нет данных о платформах")

        # 2. О конкурентах
        if result.competitors:
            top_competitor = result.competitors[0]
            findings.append(f"Основной конкурент: {top_competitor.name} "
                          f"({top_competitor.courses_count} курсов)")

            if len(result.competitors) > 1:
                second = result.competitors[1]
                findings.append(f"Второй конкурент: {second.name} "
                              f"({second.courses_count} курсов)")

            # Направления конкурентов
            all_directions = set()
            for comp in result.competitors[:3]:
                all_directions.update(comp.directions)
            if all_directions:
                findings.append(f"Ключевые направления конкурентов: {', '.join(list(all_directions)[:5])}")
        else:
            findings.append("Конкуренты не выявлены — возможно, недостаточно данных")

        # 3. О трендах
        if result.trends:
            top_trend = result.trends[0]
            findings.append(f"Ключевой тренд: {top_trend['direction']} "
                          f"(представлен на {top_trend['platforms_count']} платформах)")
            if len(result.trends) > 1:
                findings.append(f"Всего выявлено {len(result.trends)} трендов")

        # 4. О gap-зонах
        high_priority_gaps = [g for g in result.gaps if g.get("priority") == "high"]
        if high_priority_gaps:
            gap_directions = [g.get("direction", "") for g in high_priority_gaps]
            findings.append(f"Выявлено {len(high_priority_gaps)} приоритетных gap-зон: "
                          f"{', '.join(gap_directions[:3])}"
                          f"{'...' if len(gap_directions) > 3 else ''}")

        if result.gaps and not high_priority_gaps:
            findings.append(f"Выявлено {len(result.gaps)} gap-зон для дальнейшего анализа")

        return findings

    def analyze_from_file(self, filepath: str) -> MarketAnalysisResult:
        """
        Выполняет анализ из JSON-файла

        Args:
            filepath: Путь к JSON-файлу с данными от market_agent

        Returns:
            MarketAnalysisResult: Результаты анализа
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return self.analyze(data)

    def save_results(self, result: MarketAnalysisResult, filename: Optional[str] = None) -> str:
        """
        Сохраняет результаты анализа в JSON

        Args:
            result: Результаты анализа
            filename: Имя файла (опционально)

        Returns:
            str: Путь к сохраненному файлу
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"market_analysis_{timestamp}.json"

        filepath = self.results_dir / filename

        # Конвертируем в словарь
        data = {
            "platforms_analyzed": result.platforms_analyzed,
            "total_courses": result.total_courses,
            "competitors": [
                {
                    "name": c.name,
                    "courses_count": c.courses_count,
                    "directions": c.directions,
                    "strengths": c.strengths,
                    "weaknesses": c.weaknesses,
                    "positioning": c.positioning
                }
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

    def load_latest_results(self) -> Optional[MarketAnalysisResult]:
        """Загружает последние результаты анализа"""
        files = sorted(
            self.results_dir.glob("market_analysis_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if not files:
            return None

        with open(files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Конвертируем обратно в MarketAnalysisResult
        competitors = [
            CompetitorAnalysis(
                name=c.get("name", ""),
                courses_count=c.get("courses_count", 0),
                directions=c.get("directions", []),
                strengths=c.get("strengths", []),
                weaknesses=c.get("weaknesses", []),
                positioning=c.get("positioning", "")
            )
            for c in data.get("competitors", [])
        ]

        return MarketAnalysisResult(
            platforms_analyzed=data.get("platforms_analyzed", 0),
            total_courses=data.get("total_courses", 0),
            competitors=competitors,
            trends=data.get("trends", []),
            gaps=data.get("gaps", []),
            findings=data.get("findings", []),
            generated_at=data.get("generated_at", "")
        )


def main():
    """Тестовый запуск"""
    print("=" * 60)
    print("📊 MARKET ANALYSIS AGENT - ТЕСТ")
    print("=" * 60)

    agent = MarketAnalysisAgent()

    # Тестовые данные
    test_data = {
        "platforms": [
            {
                "name": "Coursera",
                "courses": [
                    {"title": "Machine Learning", "description": "ML course"},
                    {"title": "Deep Learning", "description": "DL course"},
                    {"title": "NLP with Transformers", "description": "NLP course"},
                ]
            },
            {
                "name": "OTUS",
                "courses": [
                    {"title": "Computer Vision", "description": "CV course"},
                    {"title": "MLOps", "description": "MLOps course"},
                ]
            }
        ]
    }

    result = agent.analyze(test_data)
    agent.save_results(result)

    print("\n📋 Результаты анализа:")
    print(f"  Платформ: {result.platforms_analyzed}")
    print(f"  Курсов: {result.total_courses}")
    print(f"  Конкурентов: {len(result.competitors)}")
    print(f"  Трендов: {len(result.trends)}")
    print(f"  Gap-зон: {len(result.gaps)}")

    if result.findings:
        print("\n📌 Ключевые выводы:")
        for finding in result.findings:
            print(f"  • {finding}")

    print("\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)


if __name__ == "__main__":
    main()