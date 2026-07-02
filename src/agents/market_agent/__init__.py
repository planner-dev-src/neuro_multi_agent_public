# Market agent package.

from __future__ import annotations

from src.agents.market_agent.analyzer import build_platform_analytics_from_items
from src.agents.market_agent.crawler import MarketCrawler
from src.agents.market_agent.crawler_config import CrawlerConfig
from src.agents.market_agent.normalizer import normalize_documents_to_catalog_items
from src.agents.market_agent.pipeline import INPUT_CSV_PATH, MarketAgent, load_platforms_from_csv

__all__ = [
    "MarketAgent",
    "MarketCrawler",
    "CrawlerConfig",
    "INPUT_CSV_PATH",
    "load_platforms_from_csv",
    "normalize_documents_to_catalog_items",
    "build_platform_analytics_from_items",
]