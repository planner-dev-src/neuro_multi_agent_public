"""Типы данных для planner_agent."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RAGChunk:
    """Унифицированный контракт RAG-чанка для всех агентов."""

    chunk_id: str
    source: str             # secretary / market_analysis / metrics / planner
    section: str            # overview / trends / gaps / positioning / decisions / products / teams
    title: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class CompetencyGapAnalysis:
    """Результат сопоставления внешней gap-зоны с внутренними компетенциями."""

    topic_key: str
    topic_label: str

    # Внешний рынок
    market_platform_share: float         # 0.0 – 1.0
    market_opportunity_score: float      # 0.0 – 1.0
    market_trend_strength: float         # 0.0 – 1.0

    # Внутренние компетенции
    internal_coverage: float             # 0.0 – 1.0, покрытие командами
    internal_expert_count: int           # кол-во сотрудников с уровнем >= 0.7
    internal_team_count: int             # кол-во команд с этой компетенцией

    # Итоговая оценка
    gap_severity: str                    # critical / significant / moderate / minimal
    recommendation: str                  # hire / upskill / monitor / maintain
    priority: int = 0                    # 1 (критично) – 5 (не срочно)

    narrative: str = ""                  # текстовое обоснование

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RoleRecommendation:
    """Рекомендация по кадровому решению."""

    role: str
    grade: str
    urgency: str                        # immediate / near_term / future

    reason_topic_keys: list[str] = field(default_factory=list)
    market_signal: str = ""
    internal_deficit_score: float = 0.0

    suggested_headcount: int = 0
    narrative: str = ""

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ProductPivotRecommendation:
    """Рекомендация по развитию продукта."""

    product_id: str
    product_name: str
    action: str                         # invest / maintain / divest / pivot

    reason: str = ""
    market_alignment_score: float = 0.0
    internal_capability_score: float = 0.0

    narrative: str = ""

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class PlannerOutput:
    """Финальный результат работы planner_agent."""

    generated_at: str = ""

    # Сводка
    executive_summary: str = ""

    # Gap-анализ по каждой теме
    competency_gaps: list[CompetencyGapAnalysis] = field(default_factory=list)

    # Кадровые рекомендации
    role_recommendations: list[RoleRecommendation] = field(default_factory=list)

    # Продуктовые рекомендации
    product_recommendations: list[ProductPivotRecommendation] = field(default_factory=list)

    # RAG-чанки для сохранения в knowledge base
    rag_chunks: list[RAGChunk] = field(default_factory=dict)

    metadata: dict[str, object] = field(default_factory=dict)