from src.orchestrators.router import get_agent


def run_agent(agent_name: str, **kwargs):
    agent = get_agent(agent_name)
    if agent is None:
        raise ValueError(f"Unknown agent: {agent_name}")
    return agent.run(**kwargs)