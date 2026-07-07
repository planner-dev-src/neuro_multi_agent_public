"""Загрузчик модельных метрик компании из JSON-файла.

Использование:
    from src.agents.planner_agent.sample_metrics import load_sample_metrics
    metrics = load_sample_metrics()
    metrics = load_sample_metrics("path/to/custom_metrics.json")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agents.planner_agent.metrics_schema import (
    CompanyMetrics,
    EmployeeMetrics,
    ProductMetrics,
    StrategyInput,
)


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


def load_sample_metrics(path: str | Path | None = None) -> CompanyMetrics:
    """Загружает модельные метрики компании из JSON.

    Если путь не указан, используется sample_metrics.json из той же папки.
    """
    if path is None:
        path = Path(__file__).resolve().parent / "sample_metrics.json"
    else:
        path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    employees = [_parse_employee(e) for e in data.get("employees", [])]
    products = [_parse_product(p) for p in data.get("products", [])]
    strategy = _parse_strategy(data.get("strategy", {}))

    return CompanyMetrics(
        company_name=str(data.get("company_name", "")),
        generated_at=str(data.get("generated_at", "")),
        products=products,
        teams=[],  # будут построены из employees в planner_agent
        employees=employees,
        strategy=strategy,
        total_headcount=len(employees),
        total_products=len(products),
        total_teams=0,  # будет вычислено в planner_agent
    )