"""任务管理 API - 已对接 Supabase"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateTaskRequest(BaseModel):
    title: str = "Untitled Task"
    input_type: str = "video"
    description: Optional[str] = None
    user_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    priority_focus: str = "balanced"
    storage_paths: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str
    title: str
    status: str
    input_type: str
    created_at: str
    description: Optional[str] = None
    user_id: Optional[str] = None
    priority_focus: str = "balanced"
    metadata: dict[str, Any] = Field(default_factory=dict)
    storage_paths: dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None


@router.post("", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest, request: Request):
    """创建检测任务并持久化到 Supabase"""
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    request_user_id = getattr(request.state, "user_id", None)
    effective_user_id = req.user_id or request_user_id
    
    task_data = {
        "id": task_id,
        "title": req.title,
        "status": "pending",
        "input_type": req.input_type,
        "description": req.description,
        "created_at": now,
        "user_id": effective_user_id,
        "updated_at": now,
        "metadata": req.metadata,
        "priority_focus": req.priority_focus,
        "storage_paths": req.storage_paths,
    }
    
    try:
        # 插入到 Supabase 'tasks' 表
        response = supabase.table("tasks").insert(task_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create task in database")
        return TaskResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating task: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """从 Supabase 查询任务详情"""
    try:
        response = supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch task")


@router.get("", response_model=List[TaskResponse])
async def list_tasks(limit: int = 20):
    """列出最近的任务"""
    try:
        response = supabase.table("tasks").select("*").order("created_at", desc=True).limit(limit).execute()
        return [TaskResponse(**t) for t in response.data]
    except Exception as e:
        logger.error("Error listing tasks: %s", e)
        return []
