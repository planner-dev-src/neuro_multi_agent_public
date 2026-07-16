"""Бизнес-логика управления поручениями."""

from typing import List, Optional
from .models import Task, TaskStatus, TaskPriority
from .manager import TaskManager


class TaskService:
    """Сервисный слой для управления поручениями."""
    
    def __init__(self, task_manager: TaskManager):
        self.manager = task_manager
    
    def create_task(self, title: str, description: Optional[str] = None,
                   assignee: Optional[str] = None, priority: TaskPriority = TaskPriority.MEDIUM,
                   source: str = "manual", source_id: Optional[str] = None,
                   created_by: str = "system") -> str:
        """Создаёт поручение."""
        task = Task(
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            source=source,
            source_id=source_id,
            created_by=created_by
        )
        return self.manager.create_task(task)
    
    def get_pending_tasks(self, created_by: Optional[str] = None) -> List[Task]:
        return self.manager.get_tasks(status=TaskStatus.PENDING, created_by=created_by)
    
    def assign_task(self, task_id: str, assignee: str) -> bool:
        return self.manager.assign_task(task_id, assignee)
    
    def complete_task(self, task_id: str) -> bool:
        return self.manager.update_status(task_id, TaskStatus.COMPLETED)