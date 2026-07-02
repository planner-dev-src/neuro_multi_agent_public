from src.agents.market_agent.pipeline import MarketAgent
from src.agents.secretary_agent.stub import SecretaryAgent
from src.agents.planner_agent.stub import PlannerAgent


def get_agent(agent_name: str):
    registry = {
        "market_agent": MarketAgent(),
        "secretary_agent": SecretaryAgent(),
        "planner_agent": PlannerAgent(),
    }
    return registry.get(agent_name)