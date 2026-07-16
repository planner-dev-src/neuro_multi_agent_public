# src/agents/market_analysis_agent/__init__.py
import re
"""
Market Analysis Agent - анализ рыночных данных с учетом метрик
"""

from .market_analysis_agent import (
    MarketAnalysisAgent,
    MarketAnalysisResult,
    CompetitorAnalysis
)
from .pipeline import run_market_analysis
from .types import MarketAnalysisBundle

__all__ = [
    "MarketAnalysisAgent",
    "MarketAnalysisResult",
    "CompetitorAnalysis",
    "run_market_analysis",
    "MarketAnalysisBundle",
]