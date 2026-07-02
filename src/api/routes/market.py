from fastapi import APIRouter
from src.common.schemas import PlatformRequest
from src.orchestrators.workflow import run_agent

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/analyze")
def analyze_market(platforms: list[PlatformRequest]):
    payload = [item.model_dump() for item in platforms]
    result = run_agent("market_agent", platforms=payload)
    return {
        "agent_name": result.agent_name,
        "status": result.status,
        "message": result.message,
        "payload": result.payload,
    }