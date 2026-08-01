"""API роуты для веб-интерфейса."""

from .dashboard import router as dashboard_router
from .research import router as research_router
from .tasks import router as tasks_router
from .chat import router as chat_router