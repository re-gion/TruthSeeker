"""任务管理 API - 已对接 Supabase"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.audit_log import record_audit_event
from app.services.evidence_files import derive_input_type, normalize_uploaded_files, require_evidence_files
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
    effective_user_id = request_user_id

    try:
        raw_files = (
            req.metadata.get("files")
            or req.storage_paths.get("files")
            or []
        )
        evidence_files = normalize_uploaded_files(raw_files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not require_evidence_files(evidence_files):
        raise HTTPException(status_code=400, detail="请至少上传 1 个待检测文件，提示词只作为全局检测目标")

    input_type = derive_input_type(evidence_files)
    case_prompt = req.description or req.metadata.get("case_prompt") or ""
    metadata = {
        **req.metadata,
        "case_prompt": case_prompt,
        "files": evidence_files,
    }
    storage_paths = {
        **req.storage_paths,
        "files": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "mime_type": item.get("mime_type"),
                "size_bytes": item.get("size_bytes"),
                "modality": item.get("modality"),
                "storage_path": item.get("storage_path"),
            }
            for item in evidence_files
        ],
    }
    
    task_data = {
        "id": task_id,
        "title": req.title,
        "status": "pending",
        "input_type": input_type,
        "description": case_prompt,
        "created_at": now,
        "user_id": effective_user_id,
        "updated_at": now,
        "metadata": metadata,
        "priority_focus": req.priority_focus,
        "storage_paths": storage_paths,
    }
    
    try:
        # 插入到 Supabase 'tasks' 表
        response = supabase.table("tasks").insert(task_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create task in database")
        record_audit_event(
            action="task_create",
            task_id=task_id,
            user_id=effective_user_id,
            metadata={"input_type": input_type, "file_count": len(evidence_files)},
        )
        return TaskResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating task: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request):
    """从 Supabase 查询任务详情"""
    try:
        user_id = getattr(request.state, "user_id", None)
        query = supabase.table("tasks").select("*").eq("id", task_id)
        if user_id and user_id != "anonymous":
            query = query.eq("user_id", user_id)
        response = query.execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch task")


@router.get("", response_model=List[TaskResponse])
async def list_tasks(request: Request, limit: int = 20):
    """列出最近的任务"""
    try:
        user_id = getattr(request.state, "user_id", None)
        query = supabase.table("tasks").select("*")
        if user_id and user_id != "anonymous":
            query = query.eq("user_id", user_id)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return [TaskResponse(**t) for t in response.data]
    except Exception as e:
        logger.error("Error listing tasks: %s", e)
        return []
