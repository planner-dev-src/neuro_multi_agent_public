"""Основная логика управления поручениями."""

import uuid
from typing import List, Optional
from datetime import datetime
from loguru import logger

from .models import Task, TaskStatus, TaskPriority


class TaskManager:
    """Менеджер задач для управления поручениями."""
    
    def __init__(self, db_collection):
        self.collection = db_collection
        logger.info("TaskManager инициализирован")
    
    def create_task(self, task: Task) -> str:
        """Создаёт новое поручение."""
        if not task.id:
            task.id = str(uuid.uuid4())
        
        task.created_at = datetime.now()
        task.updated_at = datetime.now()
        
        task_dict = task.dict()
        self.collection.insert_one(task_dict)
        
        logger.info(f"Создано поручение: {task.id} - {task.title}")
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Получает поручение по ID."""
        data = self.collection.find_one({"id": task_id})
        if data:
            return Task(**data)
        return None
    
    def get_tasks(
        self,
        status: Optional[TaskStatus] = None,
        assignee: Optional[str] = None,
        created_by: Optional[str] = None,
        priority: Optional[TaskPriority] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Task]:
        """Получает список поручений с фильтрацией."""
        query = {}
        if status:
            query["status"] = status
        if assignee:
            query["assignee"] = assignee
        if created_by:
            query["created_by"] = created_by
        if priority:
            query["priority"] = priority
        
        cursor = self.collection.find(query).skip(skip).limit(limit)
        return [Task(**doc) for doc in cursor]
    
    def assign_task(self, task_id: str, assignee: str) -> bool:
        """Назначает исполнителя."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task.assignee = assignee
        task.status = TaskStatus.ASSIGNED
        task.updated_at = datetime.now()
        
        self.collection.update_one(
            {"id": task_id},
            {"$set": task.dict()}
        )
        
        logger.info(f"Поручение {task_id} назначено {assignee}")
        return True
    
    def update_status(self, task_id: str, status: TaskStatus) -> bool:
        """Обновляет статус поручения."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        old_status = task.status
        task.status = status
        task.updated_at = datetime.now()
        
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        
        self.collection.update_one(
            {"id": task_id},
            {"$set": task.dict()}
        )
        
        logger.info(f"Статус поручения {task_id}: {old_status} → {status}")
        return True
    
    def delete_task(self, task_id: str) -> bool:
        """Удаляет поручение."""
        result = self.collection.delete_one({"id": task_id})
        return result.deleted_count > 0
    
    def get_stats(self, created_by: Optional[str] = None) -> dict:
        """Получает статистику по поручениям."""
        query = {}
        if created_by:
            query["created_by"] = created_by
        
        total = self.collection.count_documents(query)
        pending = self.collection.count_documents({**query, "status": TaskStatus.PENDING})
        assigned = self.collection.count_documents({**query, "status": TaskStatus.ASSIGNED})
        completed = self.collection.count_documents({**query, "status": TaskStatus.COMPLETED})
        
        return {
            "total": total,
            "pending": pending,
            "assigned": assigned,
            "completed": completed,
            "completion_rate": (completed / total * 100) if total > 0 else 0
        }