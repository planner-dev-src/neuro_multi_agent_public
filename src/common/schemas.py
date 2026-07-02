from pydantic import BaseModel, Field
from typing import Dict, List


class PlatformRequest(BaseModel):
    name: str
    urls: List[str]


class PlatformAnalysisResult(BaseModel):
    name: str
    directions_found: Dict[str, int] = Field(default_factory=dict)
    criteria_found: Dict[str, str] = Field(default_factory=dict)
    summary: str = ""


class MarketReport(BaseModel):
    platforms: List[PlatformAnalysisResult]