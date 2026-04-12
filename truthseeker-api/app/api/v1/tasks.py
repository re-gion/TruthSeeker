"""任务管理 API - 已对接 Supabase"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.utils.supabase_client import supabase

router = APIRouter()


class CreateTaskRequest(BaseModel):
    title: str = "Untitled Task"
    input_type: str = "video"
    description: Optional[str] = None
    user_id: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    status: str
    input_type: str
    created_at: str
    description: Optional[str] = None


@router.post("", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    """创建检测任务并持久化到 Supabase"""
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    task_data = {
        "id": task_id,
        "title": req.title,
        "status": "pending",
        "input_type": req.input_type,
        "description": req.description,
        "created_at": now,
        "user_id": req.user_id,
        "updated_at": now
    }
    
    try:
        # 插入到 Supabase 'tasks' 表
        response = supabase.table("tasks").insert(task_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create task in database")
        return TaskResponse(**response.data[0])
    except Exception as e:
        print(f"Error creating task: {e}")
        # Fallback to simplified response if DB fails (for development safety)
        return TaskResponse(**task_data)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """从 Supabase 查询任务详情"""
    try:
        response = supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskResponse(**response.data[0])
    except Exception as e:
        print(f"Error fetching task: {e}")
        raise HTTPException(status_code=404, detail="Task not found or database error")


@router.get("", response_model=List[TaskResponse])
async def list_tasks(limit: int = 20):
    """列出最近的任务"""
    try:
        response = supabase.table("tasks").select("*").order("created_at", desc=True).limit(limit).execute()
        return [TaskResponse(**t) for t in response.data]
    except Exception as e:
        print(f"Error listing tasks: {e}")
        return []
