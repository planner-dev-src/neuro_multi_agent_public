from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentResult:
    agent_name: str
    status: str
    payload: Dict[str, Any] = field(default_factory=dict)
    message: str = ""