from __future__ import annotations

from typing import Any, cast

from src.agents.base.agent import BaseAgent
from src.agents.base.models import AgentResult

from .pipeline import run_market_analysis


class MarketAnalysisAgent(BaseAgent):
    name = "market_analysis_agent"

    def run(
        self,
        source_json_path: str | None = None,
    ) -> AgentResult:
        result = run_market_analysis(source_json_path=source_json_path)
        files = result.get("files", {})

        payload: dict[str, Any] = {
            "summary": result["bundle"].summary,
            "files": files,
        }

        return AgentResult(
            agent_name=self.name,
            status="success",
            payload=cast(dict[str, Any], payload),
            message="Built market analysis bundle",
        )