"""Интеграция TaskManager с агентами системы."""

from typing import List, Dict, Any
from loguru import logger

from .service import TaskService
from .models import TaskPriority


class TaskIntegration:
    """Интеграция TaskManager с агентами."""
    
    def __init__(self, task_service: TaskService):
        self.service = task_service
    
    def create_from_secretary(self, decisions: List[Dict[str, Any]]) -> List[str]:
        """Создаёт поручения из решений secretary_agent."""
        task_ids = []
        for decision in decisions:
            task_id = self.service.create_task(
                title=decision.get("decision", "Поручение из встречи"),
                description=decision.get("description", ""),
                assignee=decision.get("who"),
                source="secretary_agent",
                source_id=decision.get("id"),
                priority=self._detect_priority(decision.get("text", ""))
            )
            task_ids.append(task_id)
        return task_ids
    
    def create_from_planner(self, recommendations: List[Dict[str, Any]]) -> List[str]:
        """Создаёт поручения из рекомендаций planner_agent."""
        task_ids = []
        for rec in recommendations:
            task_id = self.service.create_task(
                title=rec.get("title", "Рекомендация"),
                description=rec.get("description", ""),
                assignee=rec.get("assignee"),
                source="planner_agent",
                source_id=rec.get("id"),
                priority=self._detect_priority(rec.get("urgency", "medium"))
            )
            task_ids.append(task_id)
        return task_ids
    
    def _detect_priority(self, text: str) -> TaskPriority:
        text_lower = text.lower()
        if "срочн" in text_lower or "urgent" in text_lower:
            return TaskPriority.URGENT
        if "важн" in text_lower or "important" in text_lower:
            return TaskPriority.HIGH
        return TaskPriority.MEDIUM