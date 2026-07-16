"""
Интеграционные тесты
"""

from .test_market_agent_smoke import *
from .test_full_integration import *

__all__ = [
    "test_full_integration",
    "test_quick"
]