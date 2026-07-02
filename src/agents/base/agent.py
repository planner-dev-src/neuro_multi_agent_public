from abc import ABC, abstractmethod
from src.agents.base.models import AgentResult


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def run(self, *args, **kwargs) -> AgentResult:
        raise NotImplementedError