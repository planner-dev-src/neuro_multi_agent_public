"""metrics_agent — загрузка, нормализация и агрегация внутренних метрик компании.

Читает:
- sample_metrics.json (или другой источник: API, БД, CSV)

Выдаёт:
- CompanyMetrics (employees, teams, products, strategy)
- Оценку соответствия продукта компании 14 критериям сравнения с платформами
- RAG-чанки
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agents.planner_agent.metrics_schema import (
    CompanyMetrics,
    EmployeeMetrics,
    ProductMetrics,
    StrategyInput,
    TeamMetrics,
)
from src.agents.planner_agent.planner_types import RAGChunk


# ---------------------------------------------------------------------------
# 14 критериев сравнения с платформами (из таксономии)
# ---------------------------------------------------------------------------

PLATFORM_CRITERIA: dict[str, str] = {
    "independent_assignments": "Самостоятельные задания",
    "flexible_schedule": "Гибкий график курса",
    "webinars_and_free_content": "Вебинары и бесплатный контент",
    "job_support": "Помощь в трудоустройстве",
    "job_guarantee": "Гарантированное трудоустройство",
    "ai_content_base": "База контента по AI",
    "ai_specialization": "Чёткая специализация на AI",
    "real_enterprise_projects": "Реальные проекты для компаний",
    "own_ai_hr_agency": "Собственное AI HR агентство",
    "course_buyout_employment": "Выкуп стоимости курса (работа у нас)",
    "hackathon_wins": "Подтверждённые победы на хакатонах",
    "ai_reality_format": "AI Реалити",
    "ai_curator_chatgpt": "Нейро-куратор по AI на chatGPT",
    "lessons_count": "Количество занятий / объём контента",
}


# ---------------------------------------------------------------------------
# Критерии компании (модельные — позже из БД)
# ---------------------------------------------------------------------------

SAMPLE_COMPANY_CRITERIA: dict[str, bool | str | None] = {
    "independent_assignments": True,
    "flexible_schedule": True,
    "webinars_and_free_content": False,
    "job_support": True,
    "job_guarantee": False,
    "ai_content_base": True,
    "ai_specialization": True,
    "real_enterprise_projects": True,
    "own_ai_hr_agency": False,
    "course_buyout_employment": False,
    "hackathon_wins": True,
    "ai_reality_format": False,
    "ai_curator_chatgpt": True,
    "lessons_count": "50+ занятий в среднем",
}


# ---------------------------------------------------------------------------
# Результат оценки критериев
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CriteriaAssessment:
    """Оценка компании по одному критерию сравнения с платформами."""

    criteria_key: str
    criteria_label: str
    company_has: bool
    company_value: str | None = None
    market_coverage: float = 0.0       # доля платформ с этим критерием
    market_opportunity: float = 0.0    # потенциал gap
    assessment: str = ""               # "Сильная сторона", "Зона роста", "Соответствие рынку", "Не применимо"


# ---------------------------------------------------------------------------
# Загрузка данных
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_employee(data: dict[str, Any]) -> EmployeeMetrics:
    return EmployeeMetrics(
        employee_id=str(data.get("employee_id", "")),
        role=str(data.get("role", "")),
        grade=str(data.get("grade", "")),
        department=str(data.get("department", "")),
        team_id=str(data.get("team_id", "")),
        competencies=[str(c) for c in data.get("competencies", []) or []],
        competency_levels={str(k): float(v) for k, v in (data.get("competency_levels") or {}).items()},
        velocity_score=float(data.get("velocity_score", 0.0)),
        utilisation=float(data.get("utilisation", 0.0)),
        is_key_person=bool(data.get("is_key_person", False)),
        replacement_risk=float(data.get("replacement_risk", 0.0)),
        product_ids=[str(p) for p in data.get("product_ids", []) or []],
    )


def _parse_product(data: dict[str, Any]) -> ProductMetrics:
    return ProductMetrics(
        product_id=str(data.get("product_id", "")),
        product_name=str(data.get("product_name", "")),
        product_type=str(data.get("product_type", "")),
        revenue_share=float(data.get("revenue_share", 0.0)),
        growth_rate=float(data.get("growth_rate", 0.0)),
        margin=float(data.get("margin", 0.0)),
        maturity=str(data.get("maturity", "seed")),
        required_competencies=[str(c) for c in data.get("required_competencies", []) or []],
        required_competency_levels={str(k): float(v) for k, v in (data.get("required_competency_levels") or {}).items()},
        assigned_team_ids=[str(t) for t in data.get("assigned_team_ids", []) or []],
    )


def _parse_strategy(data: dict[str, Any]) -> StrategyInput:
    return StrategyInput(
        priority_topics=[str(t) for t in data.get("priority_topics", []) or []],
        target_revenue_growth=float(data.get("target_revenue_growth", 0.0)),
        target_headcount_growth=float(data.get("target_headcount_growth", 0.0)),
        hire_priority_roles=[str(r) for r in data.get("hire_priority_roles", []) or []],
        upskill_priority_topics=[str(t) for t in data.get("upskill_priority_topics", []) or []],
        budget_constraint=float(data["budget_constraint"]) if data.get("budget_constraint") is not None else None,
        timeline_months=int(data.get("timeline_months", 12)),
        narrative=str(data.get("narrative", "")),
    )


# ---------------------------------------------------------------------------
# Агрегация
# ---------------------------------------------------------------------------

def _build_teams_from_employees(employees: list[EmployeeMetrics]) -> list[TeamMetrics]:
    team_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "employees": [],
            "competencies": defaultdict(list),
        }
    )

    for emp in employees:
        tm = team_map[emp.team_id]
        tm["employees"].append(emp)
        for comp, level in emp.competency_levels.items():
            tm["competencies"][comp].append(level)

    teams: list[TeamMetrics] = []
    for team_id, data in team_map.items():
        emps = data["employees"]
        comp_coverage: dict[str, float] = {}
        core: list[str] = []
        deficit: list[str] = []

        for comp, levels in data["competencies"].items():
            avg = sum(levels) / len(levels)
            comp_coverage[comp] = round(avg, 2)
            if avg >= 0.6:
                core.append(comp)
            elif avg < 0.3:
                deficit.append(comp)

        jun = sum(1 for e in emps if e.grade == "junior")
        mid = sum(1 for e in emps if e.grade == "middle")
        sen = sum(1 for e in emps if e.grade == "senior")
        lead = sum(1 for e in emps if e.grade == "lead")
        key_count = sum(1 for e in emps if e.is_key_person)

        dept = emps[0].department if emps else ""

        teams.append(
            TeamMetrics(
                team_id=team_id,
                team_name=f"Team {team_id}",
                department=dept,
                headcount=len(emps),
                junior_count=jun,
                middle_count=mid,
                senior_count=sen,
                lead_count=lead,
                competency_coverage=comp_coverage,
                core_competencies=core,
                deficit_competencies=deficit,
                avg_velocity=round(sum(e.velocity_score for e in emps) / len(emps), 2),
                avg_utilisation=round(sum(e.utilisation for e in emps) / len(emps), 2),
                key_person_count=key_count,
                bus_factor=key_count,
                product_ids=list({pid for e in emps for pid in e.product_ids}),
            )
        )

    return teams


# ---------------------------------------------------------------------------
# Оценка критериев сравнения с платформами
# ---------------------------------------------------------------------------

def _assess_criteria(
    company_criteria: dict[str, bool | str | None],
    gaps: list[dict[str, str]],
) -> list[CriteriaAssessment]:
    """Сопоставляет критерии компании с рыночными gap-зонами."""
    gap_map: dict[str, dict[str, str]] = {g.get("topic", ""): g for g in gaps}

    assessments: list[CriteriaAssessment] = []

    for key, label in PLATFORM_CRITERIA.items():
        company_value = company_criteria.get(key)
        company_has = bool(company_value) if company_value is not None else False

        gap = gap_map.get(key, {})
        market_coverage = float(gap.get("platform_share", 0.0))
        market_opportunity = float(gap.get("opportunity_score", 0.0))

        # Логика оценки
        if company_has and market_coverage < 0.3:
            assessment = "Сильная сторона (редкий критерий на рынке)"
        elif company_has and market_coverage >= 0.5:
            assessment = "Соответствие рынку (критерий широко распространён)"
        elif company_has:
            assessment = "Умеренное преимущество"
        elif not company_has and market_opportunity >= 0.5:
            assessment = "Зона роста (рынок требует, у компании нет)"
        elif not company_has:
            assessment = "Потенциальная возможность"
        else:
            assessment = "Не применимо"

        assessments.append(
            CriteriaAssessment(
                criteria_key=key,
                criteria_label=label,
                company_has=company_has,
                company_value=str(company_value) if company_value is not None else None,
                market_coverage=market_coverage,
                market_opportunity=market_opportunity,
                assessment=assessment,
            )
        )

    return assessments


# ---------------------------------------------------------------------------
# RAG-чанки
# ---------------------------------------------------------------------------

def _build_criteria_rag_chunks(assessments: list[CriteriaAssessment]) -> list[RAGChunk]:
    chunks: list[RAGChunk] = []

    for a in assessments:
        chunks.append(
            RAGChunk(
                chunk_id=f"metrics::criteria::{a.criteria_key}",
                source="metrics",
                section="platform_criteria",
                title=f"Критерий: {a.criteria_label}",
                text=f"Компания: {'есть' if a.company_has else 'нет'}. "
                     f"Значение: {a.company_value or '—'}. "
                     f"Охват рынка: {a.market_coverage:.2f}. "
                     f"Потенциал gap: {a.market_opportunity:.2f}. "
                     f"Оценка: {a.assessment}.",
                metadata={
                    "criteria_key": a.criteria_key,
                    "company_has": a.company_has,
                    "market_coverage": a.market_coverage,
                    "assessment": a.assessment,
                },
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def run_metrics_agent(
    *,
    metrics_path: str | Path | None = None,
    gaps: list[dict[str, str]] | None = None,
    company_criteria: dict[str, bool | str | None] | None = None,
) -> dict[str, Any]:
    """Запуск metrics_agent.

    Args:
        metrics_path: путь к JSON с метриками компании
        gaps: сырые данные gap-зон из market_analysis (для оценки критериев)
        company_criteria: словарь соответствия компании 14 критериям

    Returns:
        {
            "metrics": CompanyMetrics,
            "criteria_assessment": list[CriteriaAssessment],
            "rag_chunks": list[RAGChunk],
        }
    """
    from datetime import datetime, timezone

    if metrics_path is None:
        metrics_path = Path(__file__).resolve().parent / "sample_metrics.json"

    data = _load_json(Path(metrics_path))

    employees = [_parse_employee(e) for e in data.get("employees", [])]
    products = [_parse_product(p) for p in data.get("products", [])]
    strategy = _parse_strategy(data.get("strategy", {}))
    teams = _build_teams_from_employees(employees)

    metrics = CompanyMetrics(
        company_name=str(data.get("company_name", "")),
        generated_at=datetime.now(timezone.utc).isoformat(),
        products=products,
        teams=teams,
        employees=employees,
        strategy=strategy,
        total_headcount=len(employees),
        total_products=len(products),
        total_teams=len(teams),
    )

    if company_criteria is None:
        company_criteria = SAMPLE_COMPANY_CRITERIA

    criteria_assessment: list[CriteriaAssessment] = []
    rag_chunks: list[RAGChunk] = []

    if gaps:
        criteria_assessment = _assess_criteria(company_criteria, gaps)
        rag_chunks = _build_criteria_rag_chunks(criteria_assessment)

    # Добавляем обзорный чанк
    rag_chunks.insert(
        0,
        RAGChunk(
            chunk_id="metrics::overview",
            source="metrics",
            section="overview",
            title="Обзор внутренних метрик компании",
            text=f"Компания: {metrics.company_name}. "
                 f"Сотрудников: {metrics.total_headcount}. "
                 f"Команд: {metrics.total_teams}. "
                 f"Продуктов: {metrics.total_products}. "
                 f"Приоритетные темы: {', '.join(metrics.strategy.priority_topics)}. "
                 f"Целевой рост выручки: {metrics.strategy.target_revenue_growth*100:.0f}%.",
            metadata={
                "headcount": metrics.total_headcount,
                "teams": metrics.total_teams,
                "products": metrics.total_products,
            },
        ),
    )

    return {
        "metrics": metrics,
        "criteria_assessment": criteria_assessment,
        "rag_chunks": rag_chunks,
    }


# ---------------------------------------------------------------------------
# Точка входа для тестирования
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import csv

    # Загружаем gap-зоны для оценки критериев
    _MARKET_ANALYSIS_DIR = Path("data/reports/market_analysis_agent")
    gaps_files = sorted(_MARKET_ANALYSIS_DIR.glob("competitive_gaps_*.csv"), key=lambda p: p.stat().st_mtime)
    gaps_data: list[dict[str, str]] = []
    if gaps_files:
        with open(gaps_files[-1], "r", encoding="utf-8-sig", newline="") as f:
            gaps_data = list(csv.DictReader(f))

    result = run_metrics_agent(gaps=gaps_data)

    metrics = result["metrics"]
    criteria = result["criteria_assessment"]

    print("=" * 60)
    print("METRICS AGENT — РЕЗУЛЬТАТ")
    print("=" * 60)
    print()
    print(f"Компания: {metrics.company_name}")
    print(f"Сотрудников: {metrics.total_headcount}")
    print(f"Команд: {metrics.total_teams}")
    print(f"Продуктов: {metrics.total_products}")
    print()

    print("--- Команды и покрытие компетенций ---")
    for t in metrics.teams:
        coverage = ", ".join(f"{c}={v:.2f}" for c, v in sorted(t.competency_coverage.items()))
        print(f"  Team {t.team_id} ({t.department}, {t.headcount} чел.): {coverage}")
    print()

    print("--- Оценка по 14 критериям сравнения с платформами ---")
    for c in criteria:
        icon = "✅" if c.company_has else "❌"
        print(f"  {icon} {c.criteria_label:40s} | market_cov={c.market_coverage:.2f} | gap={c.market_opportunity:.2f} | {c.assessment}")
    print()

    print(f"RAG-чанков сгенерировано: {len(result['rag_chunks'])}")