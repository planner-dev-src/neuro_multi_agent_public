"""Реестр агентов системы.

Предоставляет единую точку доступа ко всем агентам.
"""

from src.agents.market_agent.pipeline import MarketAgent
from src.agents.market_analysis_agent.pipeline import run_market_analysis
from src.agents.market_narrative_agent.market_narrative_agent import MarketNarrativeAgent
from src.agents.metrics_agent.metrics_agent import run_metrics_agent
from src.agents.planner_agent.planner_agent import run_planner
from src.agents.report_agent.report_agent import ReportAgent
from src.agents.research_agent.research_agent import ResearchAgent
from src.agents.secretary_agent.secretary_agent import run_secretary_agent


# ---------------------------------------------------------------------------
# Реестр агентов
# ---------------------------------------------------------------------------

AGENT_REGISTRY = {
    "market_agent": MarketAgent(),
    "market_analysis_agent": run_market_analysis,
    "market_narrative_agent": MarketNarrativeAgent(),
    "metrics_agent": run_metrics_agent,
    "planner_agent": run_planner,
    "report_agent": ReportAgent(use_llm=True),
    "research_agent": ResearchAgent(),
    "secretary_agent": run_secretary_agent,
}


def get_agent(name: str):
    """Возвращает агента по имени.

    Args:
        name: имя агента в реестре

    Returns:
        Экземпляр агента или функция запуска

    Raises:
        ValueError: если агент не найден
    """
    agent = AGENT_REGISTRY.get(name)
    if agent is None:
        raise ValueError(
            f"Неизвестный агент: {name}. Доступные: {', '.join(AGENT_REGISTRY.keys())}"
        )
    return agent


def list_agents() -> list[str]:
    """Возвращает список имён всех зарегистрированных агентов."""
    return list(AGENT_REGISTRY.keys())


def get_agent_info(name: str) -> dict:
    """Возвращает информацию об агенте."""
    agent = get_agent(name)
    return {
        "name": name,
        "type": type(agent).__name__,
        "available": True,
    }


def list_agents_info() -> list[dict]:
    """Возвращает информацию обо всех агентах."""
    return [get_agent_info(name) for name in list_agents()]