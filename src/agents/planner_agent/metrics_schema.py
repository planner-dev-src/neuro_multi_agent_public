"""Структура внутренних метрик компании для planner_agent.

Иерархия:
    CompanyMetrics
    ├── products (продуктовые метрики)
    ├── teams (командные метрики)
    ├── employees (индивидуальные метрики)
    └── strategy (стратегические ориентиры от руководителя)
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Индивидуальный уровень
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EmployeeMetrics:
    """Метрики одного сотрудника."""

    employee_id: str
    role: str
    grade: str                      # junior / middle / senior / lead
    department: str
    team_id: str

    # Hard skills — ключи из таксономии (TOPIC_KEYS)
    competencies: list[str] = field(default_factory=list)

    # Уровень владения компетенцией: 0.0 – 1.0
    competency_levels: dict[str, float] = field(default_factory=dict)

    # Производительность
    velocity_score: float = 0.0     # 0.0 – 1.0, относительно внутреннего бенчмарка
    utilisation: float = 0.0        # 0.0 – 1.0, доля времени на продуктивные задачи

    # Дефицитность
    is_key_person: bool = False
    replacement_risk: float = 0.0   # 0.0 – 1.0, сложность замены

    # Участие в продуктах
    product_ids: list[str] = field(default_factory=list)

    metadata: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Командный уровень
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TeamMetrics:
    """Агрегированные метрики команды."""

    team_id: str
    team_name: str
    department: str
    headcount: int = 0

    # Распределение по грейдам
    junior_count: int = 0
    middle_count: int = 0
    senior_count: int = 0
    lead_count: int = 0

    # Агрегированное покрытие компетенций
    # Ключ — TOPIC_KEYS, значение — средний уровень по команде (0.0 – 1.0)
    competency_coverage: dict[str, float] = field(default_factory=dict)

    # Ключевые компетенции команды (пороговое значение >= 0.6)
    core_competencies: list[str] = field(default_factory=list)

    # Дефицитные компетенции (< 0.3)
    deficit_competencies: list[str] = field(default_factory=list)

    # Командная производительность
    avg_velocity: float = 0.0
    avg_utilisation: float = 0.0

    # Текучесть и риски
    turnover_risk: float = 0.0
    key_person_count: int = 0
    bus_factor: int = 0               # минимальное число людей, уход которых остановит команду

    product_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Продуктовый уровень
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProductMetrics:
    """Метрики программного продукта / направления."""

    product_id: str
    product_name: str
    product_type: str                   # platform / service / consulting / course

    # Бизнес-метрики
    revenue_share: float = 0.0          # доля в выручке компании (0.0 – 1.0)
    growth_rate: float = 0.0            # годовой рост (%)
    margin: float = 0.0                 # маржинальность

    # Жизненный цикл
    maturity: str = "seed"              # seed / growth / mature / decline

    # Компетенции, необходимые для развития продукта
    required_competencies: list[str] = field(default_factory=list)
    required_competency_levels: dict[str, float] = field(default_factory=dict)

    # Покрытие компетенций командами (рассчитывается)
    coverage_score: float = 0.0         # 0.0 – 1.0, насколько команды покрывают required

    # Конкурентная позиция
    market_differentiation: float = 0.0 # 0.0 – 1.0, насколько продукт уникален vs рынок
    competitor_count: int = 0
    moat_strength: str = "weak"         # weak / moderate / strong

    assigned_team_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Стратегический уровень (вводные от руководителя)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StrategyInput:
    """Стратегические ориентиры, заданные руководителем."""

    # Приоритетные направления развития (ключи TOPIC_KEYS)
    priority_topics: list[str] = field(default_factory=list)

    # KPI, заданные руководителем
    target_revenue_growth: float = 0.0
    target_headcount_growth: float = 0.0
    target_margin: float = 0.0

    # Кадровые ориентиры
    hire_priority_roles: list[str] = field(default_factory=list)
    upskill_priority_topics: list[str] = field(default_factory=list)

    # Ограничения
    budget_constraint: float | None = None
    timeline_months: int = 12

    # Свободный текст установок
    narrative: str = ""

    metadata: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Корневая модель
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CompanyMetrics:
    """Агрегированная модель внутренних метрик компании."""

    company_name: str = ""
    generated_at: str = ""

    products: list[ProductMetrics] = field(default_factory=list)
    teams: list[TeamMetrics] = field(default_factory=list)
    employees: list[EmployeeMetrics] = field(default_factory=list)
    strategy: StrategyInput = field(default_factory=StrategyInput)

    # Сводная статистика
    total_headcount: int = 0
    total_products: int = 0
    total_teams: int = 0

    metadata: dict[str, object] = field(default_factory=dict)