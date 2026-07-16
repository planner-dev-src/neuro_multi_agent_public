"""API эндпоинты для управления поручениями."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.agents.task_manager import TaskService, TaskPriority, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

task_service: Optional[TaskService] = None


def init_task_service(service: TaskService):
    global task_service
    task_service = service


@router.post("/")
async def create_task(
    title: str,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    priority: TaskPriority = TaskPriority.MEDIUM,
    created_by: str = "system"
):
    if not task_service:
        raise HTTPException(status_code=500, detail="TaskService не инициализирован")
    
    task_id = task_service.create_task(
        title=title,
        description=description,
        assignee=assignee,
        priority=priority,
        created_by=created_by
    )
    return {"id": task_id, "status": "created"}


@router.get("/")
async def get_tasks(
    status: Optional[TaskStatus] = Query(None),
    assignee: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    if not task_service:
        raise HTTPException(status_code=500, detail="TaskService не инициализирован")
    
    tasks = task_service.manager.get_tasks(
        status=status,
        assignee=assignee,
        created_by=created_by,
        limit=limit,
        skip=skip
    )
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/stats")
async def get_stats(created_by: Optional[str] = None):
    if not task_service:
        raise HTTPException(status_code=500, detail="TaskService не инициализирован")
    
    stats = task_service.manager.get_stats(created_by=created_by)
    return stats