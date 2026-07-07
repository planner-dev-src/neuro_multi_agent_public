"""planner_agent — сопоставление внешних рыночных gap-зон с внутренними метриками компании.

Читает:
- competitive_gaps_*.csv и trend_signals_*.csv из data/reports/market_analysis_agent/
- CompanyMetrics из sample_metrics.json (или переданный объект)

Выдаёт:
- PlannerOutput: CompetencyGapAnalysis, RoleRecommendation, ProductPivotRecommendation
- RAG-чанки для сохранения в knowledge base
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.agents.planner_agent.metrics_schema import (
    CompanyMetrics,
    EmployeeMetrics,
    ProductMetrics,
    StrategyInput,
    TeamMetrics,
)
from src.agents.planner_agent.planner_types import (
    CompetencyGapAnalysis,
    PlannerOutput,
    ProductPivotRecommendation,
    RAGChunk,
    RoleRecommendation,
)
from src.agents.planner_agent.sample_metrics import load_sample_metrics

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------

_MARKET_ANALYSIS_DIR = Path("data/reports/market_analysis_agent")


def _latest_csv(pattern: str) -> Path:
    files = sorted(_MARKET_ANALYSIS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No files matching {pattern} in {_MARKET_ANALYSIS_DIR}")
    return files[-1]


# ---------------------------------------------------------------------------
# Ключи таксономии, для которых наём нерелевантен
# (это характеристики продукта/услуги, а не компетенции сотрудников)
# ---------------------------------------------------------------------------

_NON_HIRE_TOPIC_KEYS: set[str] = {
    "independent_assignments",
    "flexible_schedule",
    "webinars_and_free_content",
    "job_support",
    "job_guarantee",
    "ai_content_base",
    "ai_specialization",
    "real_enterprise_projects",
    "own_ai_hr_agency",
    "course_buyout_employment",
    "hackathon_wins",
    "ai_reality_format",
    "ai_curator_chatgpt",
    "lessons_count",
}


# ---------------------------------------------------------------------------
# Агрегация сотрудников в команды
# ---------------------------------------------------------------------------

def _build_teams_from_employees(employees: list[EmployeeMetrics]) -> list[TeamMetrics]:
    """Агрегирует сотрудников в команды."""
    from collections import defaultdict

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
        bus = sum(1 for e in emps if e.is_key_person)

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
                bus_factor=bus,
                product_ids=list({pid for e in emps for pid in e.product_ids}),
            )
        )

    return teams


# ---------------------------------------------------------------------------
# Загрузка рыночных данных
# ---------------------------------------------------------------------------

def _load_gaps() -> list[dict[str, str]]:
    path = _latest_csv("competitive_gaps_*.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_trends() -> list[dict[str, str]]:
    path = _latest_csv("trend_signals_*.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Сопоставление
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _aggregate_internal_coverage(metrics: CompanyMetrics, topic_key: str) -> tuple[float, int, int]:
    """Возвращает (среднее покрытие, кол-во экспертов, кол-во команд)."""
    levels: list[float] = []
    expert_count = 0
    team_ids: set[str] = set()

    for team in metrics.teams:
        cov = team.competency_coverage.get(topic_key)
        if cov is not None:
            levels.append(cov)
            team_ids.add(team.team_id)

    for emp in metrics.employees:
        lvl = emp.competency_levels.get(topic_key, 0.0)
        if lvl >= 0.7:
            expert_count += 1

    avg = round(sum(levels) / len(levels), 2) if levels else 0.0
    return avg, expert_count, len(team_ids)


def _determine_gap_severity(
    market_opportunity: float,
    internal_coverage: float,
) -> str:
    """Определяет критичность gap на основе внешнего потенциала и внутреннего покрытия."""
    if market_opportunity >= 0.6 and internal_coverage < 0.3:
        return "critical"
    if market_opportunity >= 0.5 and internal_coverage < 0.5:
        return "significant"
    if market_opportunity >= 0.4 or internal_coverage < 0.5:
        return "moderate"
    return "minimal"


def _determine_recommendation(gap_severity: str, internal_coverage: float) -> str:
    if gap_severity == "critical":
        return "hire"
    if gap_severity == "significant":
        return "hire" if internal_coverage < 0.3 else "upskill"
    if gap_severity == "moderate":
        return "upskill"
    return "maintain"


def _build_narrative(gap: CompetencyGapAnalysis) -> str:
    parts: list[str] = []

    if gap.gap_severity == "critical":
        parts.append(
            f"Критический разрыв по направлению «{gap.topic_label}»: "
            f"рыночный потенциал {gap.market_opportunity_score:.2f}, "
            f"внутреннее покрытие всего {gap.internal_coverage:.2f}."
        )
    elif gap.gap_severity == "significant":
        parts.append(
            f"Значимый разрыв: «{gap.topic_label}» — "
            f"рынок требует компетенций (opportunity={gap.market_opportunity_score:.2f}), "
            f"но текущее покрытие {gap.internal_coverage:.2f}."
        )
    else:
        parts.append(
            f"Умеренный разрыв по «{gap.topic_label}»: "
            f"покрытие {gap.internal_coverage:.2f}, "
            f"рыночный потенциал {gap.market_opportunity_score:.2f}."
        )

    if gap.recommendation == "hire":
        parts.append("Рекомендуется нанять специалистов с данной компетенцией.")
    elif gap.recommendation == "upskill":
        parts.append("Рекомендуется повысить квалификацию текущих сотрудников.")
    elif gap.recommendation == "maintain":
        parts.append("Текущий уровень компетенций достаточен — можно поддерживать.")
    else:
        parts.append("Наблюдать за рынком, решение принять позже.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Генерация рекомендаций
# ---------------------------------------------------------------------------

def _generate_role_recommendations(
    gaps: list[CompetencyGapAnalysis],
    metrics: CompanyMetrics,
) -> list[RoleRecommendation]:
    recommendations: list[RoleRecommendation] = []

    for gap in gaps:
        if gap.recommendation not in ("hire",):
            continue

        if gap.topic_key in _NON_HIRE_TOPIC_KEYS:
            continue

        role_mapping = {
            "classical_ml": ("ML Engineer", "middle"),
            "nlp": ("NLP Engineer", "senior"),
            "llm_agents": ("LLM Engineer", "senior"),
            "computer_vision": ("CV Engineer", "senior"),
            "time_series": ("ML Engineer", "middle"),
            "reinforcement_learning": ("RL Engineer", "senior"),
            "speech_audio": ("Speech AI Engineer", "senior"),
            "gan": ("ML Engineer", "middle"),
            "genetic_algorithms": ("Research Engineer", "senior"),
            "automl": ("MLOps Engineer", "middle"),
            "production_integration": ("MLOps Engineer", "senior"),
            "ai_in_production": ("MLOps Engineer", "senior"),
            "data_engineering": ("Data Engineer", "middle"),
            "data_platforms": ("Data Engineer", "middle"),
            "devops_sre": ("DevOps Engineer", "middle"),
            "cloud_devops": ("DevOps Engineer", "middle"),
            "cybersecurity": ("Security Engineer", "senior"),
            "quality_security": ("QA Engineer", "middle"),
            "qa_engineering": ("QA Engineer", "middle"),
            "backend_development": ("Backend Developer", "middle"),
            "frontend_development": ("Frontend Developer", "middle"),
            "fullstack_development": ("Fullstack Developer", "middle"),
            "software_engineering": ("Software Engineer", "middle"),
            "ai_project_management_custom_sales": ("AI Project Manager", "lead"),
            "product_management_it": ("Product Manager", "lead"),
            "product_delivery_management": ("Delivery Manager", "lead"),
            "product_analytics": ("Product Analyst", "middle"),
            "analytics_bi": ("BI Analyst", "middle"),
            "enterprise_enablement": ("Enterprise Solutions Manager", "lead"),
            "generative_ai": ("LLM Engineer", "senior"),
        }

        role_info = role_mapping.get(gap.topic_key, (gap.topic_label.replace("_", " ").title(), "middle"))

        recommendations.append(
            RoleRecommendation(
                role=role_info[0],
                grade=role_info[1],
                urgency="immediate" if gap.gap_severity == "critical" else "near_term",
                reason_topic_keys=[gap.topic_key],
                market_signal=f"opportunity_score={gap.market_opportunity_score:.2f}",
                internal_deficit_score=round(1.0 - gap.internal_coverage, 2),
                suggested_headcount=max(1, int((1.0 - gap.internal_coverage) * 5)),
                narrative=f"Рынок сигнализирует о дефиците компетенций «{gap.topic_label}». "
                          f"Текущее покрытие: {gap.internal_coverage:.2f}. "
                          f"Рекомендуется нанять {role_info[0]} уровня {role_info[1]}.",
            )
        )

    seen_roles: set[str] = set()
    deduped: list[RoleRecommendation] = []
    for rec in recommendations:
        key = f"{rec.role}_{rec.grade}"
        if key not in seen_roles:
            seen_roles.add(key)
            deduped.append(rec)

    return deduped


def _generate_product_recommendations(
    metrics: CompanyMetrics,
    gaps: list[CompetencyGapAnalysis],
) -> list[ProductPivotRecommendation]:
    recommendations: list[ProductPivotRecommendation] = []

    gap_map: dict[str, CompetencyGapAnalysis] = {g.topic_key: g for g in gaps}

    for product in metrics.products:
        alignment_scores: list[float] = []
        capability_scores: list[float] = []

        for comp in product.required_competencies:
            gap = gap_map.get(comp)
            if gap:
                alignment_scores.append(gap.market_opportunity_score)
            cov = product.required_competency_levels.get(comp, 0.0)
            capability_scores.append(cov)

        market_alignment = round(sum(alignment_scores) / len(alignment_scores), 2) if alignment_scores else 0.5
        internal_capability = round(sum(capability_scores) / len(capability_scores), 2) if capability_scores else 0.5

        if product.maturity == "seed" and market_alignment > 0.6:
            action = "invest"
            reason = "Растущий рынок с высоким потенциалом."
        elif product.maturity == "growth" and internal_capability > 0.6:
            action = "invest"
            reason = "Сильные внутренние компетенции, растущий продукт."
        elif product.maturity == "mature" and market_alignment < 0.4:
            action = "maintain"
            reason = "Зрелый рынок, продукт стабилен."
        elif product.maturity == "decline":
            action = "divest"
            reason = "Падающий рынок."
        else:
            action = "maintain"
            reason = "Сбалансированная позиция."

        recommendations.append(
            ProductPivotRecommendation(
                product_id=product.product_id,
                product_name=product.product_name,
                action=action,
                reason=reason,
                market_alignment_score=market_alignment,
                internal_capability_score=internal_capability,
                narrative=f"Продукт «{product.product_name}»: действие «{action}». {reason} "
                          f"Рыночное соответствие: {market_alignment:.2f}, "
                          f"внутренние возможности: {internal_capability:.2f}.",
            )
        )

    return recommendations


# ---------------------------------------------------------------------------
# RAG-чанки
# ---------------------------------------------------------------------------

def _build_rag_chunks(output: PlannerOutput) -> list[RAGChunk]:
    chunks: list[RAGChunk] = []

    chunks.append(
        RAGChunk(
            chunk_id="planner::executive_summary",
            source="planner",
            section="summary",
            title="Сводка рекомендаций",
            text=output.executive_summary,
            metadata={"generated_at": output.generated_at},
        )
    )

    for gap in output.competency_gaps:
        chunks.append(
            RAGChunk(
                chunk_id=f"planner::gap::{gap.topic_key}",
                source="planner",
                section="competency_gap",
                title=f"Gap-анализ: {gap.topic_label}",
                text=gap.narrative,
                metadata={
                    "topic_key": gap.topic_key,
                    "severity": gap.gap_severity,
                    "recommendation": gap.recommendation,
                },
            )
        )

    for rec in output.role_recommendations:
        chunks.append(
            RAGChunk(
                chunk_id=f"planner::role::{rec.role}_{rec.grade}",
                source="planner",
                section="role_recommendation",
                title=f"Рекомендация по роли: {rec.role} ({rec.grade})",
                text=rec.narrative,
                metadata={"role": rec.role, "grade": rec.grade, "urgency": rec.urgency},
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def run_planner(
    *,
    metrics: CompanyMetrics | None = None,
    gaps_csv_path: str | None = None,
    trends_csv_path: str | None = None,
) -> PlannerOutput:
    """Запуск планировщика.

    Если metrics не передан — загружаются модельные данные из sample_metrics.json.
    Если пути к CSV не переданы — подхватываются последние файлы из data/reports/.
    """
    from datetime import datetime, timezone

    if metrics is None:
        metrics = load_sample_metrics()
        metrics.teams = _build_teams_from_employees(metrics.employees)
        metrics.total_teams = len(metrics.teams)

    if gaps_csv_path:
        gaps_raw = []
        with open(gaps_csv_path, "r", encoding="utf-8-sig", newline="") as f:
            gaps_raw = list(csv.DictReader(f))
    else:
        gaps_raw = _load_gaps()

    if trends_csv_path:
        trends_raw = []
        with open(trends_csv_path, "r", encoding="utf-8-sig", newline="") as f:
            trends_raw = list(csv.DictReader(f))
    else:
        trends_raw = _load_trends()

    competency_gaps: list[CompetencyGapAnalysis] = []

    for row in gaps_raw:
        topic_key = row.get("topic", "")
        topic_label = row.get("topic_label", "")
        platform_share = _safe_float(row.get("platform_share"))
        opportunity = _safe_float(row.get("opportunity_score"))
        interpretation = row.get("interpretation", "")

        if not topic_key:
            continue

        internal_cov, experts, teams_count = _aggregate_internal_coverage(metrics, topic_key)

        trend_strength = 0.0
        for t in trends_raw:
            if t.get("topic") == topic_key:
                trend_strength = _safe_float(t.get("signal_strength"))
                break

        severity = _determine_gap_severity(opportunity, internal_cov)
        recommendation = _determine_recommendation(severity, internal_cov)

        gap = CompetencyGapAnalysis(
            topic_key=topic_key,
            topic_label=topic_label,
            market_platform_share=platform_share,
            market_opportunity_score=opportunity,
            market_trend_strength=trend_strength,
            internal_coverage=internal_cov,
            internal_expert_count=experts,
            internal_team_count=teams_count,
            gap_severity=severity,
            recommendation=recommendation,
            priority=1 if severity == "critical" else (2 if severity == "significant" else (3 if severity == "moderate" else 4)),
        )
        gap.narrative = _build_narrative(gap)
        competency_gaps.append(gap)

    competency_gaps.sort(key=lambda g: g.priority)

    role_recs = _generate_role_recommendations(competency_gaps, metrics)
    product_recs = _generate_product_recommendations(metrics, competency_gaps)

    critical_count = sum(1 for g in competency_gaps if g.gap_severity == "critical")
    sig_count = sum(1 for g in competency_gaps if g.gap_severity == "significant")
    hire_count = sum(1 for r in role_recs if r.urgency == "immediate")

    executive_summary = (
        f"Анализ рынка и внутренних метрик компании «{metrics.company_name}».\n"
        f"Выявлено критических gap-зон: {critical_count}, значимых: {sig_count}.\n"
        f"Рекомендуется немедленный наём по {hire_count} ролям.\n"
        f"Продуктов: инвестировать в {sum(1 for p in product_recs if p.action == 'invest')}, "
        f"поддерживать {sum(1 for p in product_recs if p.action == 'maintain')}."
    )

    generated_at = datetime.now(timezone.utc).isoformat()

    output = PlannerOutput(
        generated_at=generated_at,
        executive_summary=executive_summary,
        competency_gaps=competency_gaps,
        role_recommendations=role_recs,
        product_recommendations=product_recs,
    )

    output.rag_chunks = _build_rag_chunks(output)

    return output


# ---------------------------------------------------------------------------
# Точка входа для тестирования
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    metrics = load_sample_metrics()
    metrics.teams = _build_teams_from_employees(metrics.employees)
    metrics.total_teams = len(metrics.teams)

    print("=" * 60)
    print("БАЗА ДЛЯ СРАВНЕНИЯ — ВНУТРЕННИЕ МЕТРИКИ КОМПАНИИ")
    print("=" * 60)
    print(f"Компания: {metrics.company_name}")
    print(f"Сотрудников: {metrics.total_headcount}")
    print(f"Команд: {metrics.total_teams}")
    print(f"Продуктов: {metrics.total_products}")
    print()
    print("--- Сотрудники ---")
    for e in metrics.employees:
        comps = ", ".join(f"{c}={e.competency_levels.get(c, 0):.2f}" for c in e.competencies)
        print(f"  {e.role} ({e.grade}, {e.department}, team {e.team_id}): {comps}")
    print()
    print("--- Команды ---")
    for t in metrics.teams:
        coverage = ", ".join(f"{c}={v:.2f}" for c, v in sorted(t.competency_coverage.items()))
        print(f"  Team {t.team_id} ({t.department}, {t.headcount} чел.): {coverage}")
    print()
    print("--- Продукты ---")
    for p in metrics.products:
        req = ", ".join(f"{c}={p.required_competency_levels.get(c, 0):.2f}" for c in p.required_competencies)
        print(f"  {p.product_name} ({p.maturity}, rev_share={p.revenue_share}): требуется [{req}]")
    print()
    print("--- Стратегия ---")
    print(f"  Приоритетные темы: {', '.join(metrics.strategy.priority_topics)}")
    print(f"  Наём: {', '.join(metrics.strategy.hire_priority_roles)}")
    print(f"  Upskill: {', '.join(metrics.strategy.upskill_priority_topics)}")
    print(f"  Целевой рост выручки: {metrics.strategy.target_revenue_growth*100:.0f}%")
    print()

    result = run_planner(metrics=metrics)

    print("=" * 60)
    print("PLANNER AGENT — РЕЗУЛЬТАТ")
    print("=" * 60)
    print()
    print(result.executive_summary)
    print()

    print("--- GAP-анализ (первые 10) ---")
    for g in result.competency_gaps[:10]:
        print(f"  {g.topic_label:35s} | severity={g.gap_severity:12s} | rec={g.recommendation:8s} | "
              f"market_opp={g.market_opportunity_score:.2f} | internal_cov={g.internal_coverage:.2f}")

    print()
    print("--- Рекомендации по ролям ---")
    for r in result.role_recommendations:
        print(f"  {r.role} ({r.grade}) | urgency={r.urgency:10s} | headcount={r.suggested_headcount}")

    print()
    print("--- Рекомендации по продуктам ---")
    for p in result.product_recommendations:
        print(f"  {p.product_name:30s} | action={p.action:8s} | market={p.market_alignment_score:.2f} | "
              f"internal={p.internal_capability_score:.2f}")

    print()
    print(f"RAG-чанков сгенерировано: {len(result.rag_chunks)}")