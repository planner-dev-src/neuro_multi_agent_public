from src.agents.base.agent import BaseAgent
from src.agents.base.models import AgentResult


class SecretaryAgent(BaseAgent):
    name = "secretary_agent"

    def run(self, *args, **kwargs) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status="not_implemented",
            payload={},
            message="Secretary agent is not implemented yet.",
        )