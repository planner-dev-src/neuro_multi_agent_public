"""Модели данных для управления поручениями."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    """Статусы поручений."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Приоритеты поручений."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(BaseModel):
    """Модель поручения."""
    
    id: Optional[str] = None
    title: str
    description: Optional[str] = None
    
    # Источник
    source: str = "manual"  # manual, secretary_agent, planner_agent
    source_id: Optional[str] = None
    
    # Статус и приоритет
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Исполнение
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    
    # Временные метки
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Дополнительные данные
    metadata: dict = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }