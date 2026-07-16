# src/api/routes/research.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.agents.research_agent.research_agent import ResearchAgent

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    max_results: int = 10
    generate_report: bool = True


class ResearchResponse(BaseModel):
    query: str
    sources_count: int
    rag_chunks_count: int
    report: Optional[str] = None
    sources: list[dict] = []


@router.post("/search", response_model=ResearchResponse)
async def search_research(request: ResearchRequest):
    """
    Запускает research_agent по запросу руководителя.
    
    Режим поиска — сбор информации по конкретной теме.
    """
    try:
        agent = ResearchAgent()
        result = agent.search_and_report(
            query=request.query,
            max_results=request.max_results,
            generate_report=request.generate_report,
        )
        
        return ResearchResponse(
            query=request.query,
            sources_count=len(result.get("sources", [])),
            rag_chunks_count=len(result.get("rag_chunks", [])),
            report=result.get("report"),
            sources=result.get("sources", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_research_status():
    """Возвращает статус research_agent (последний запуск)."""
    agent = ResearchAgent()
    return agent.get_status()