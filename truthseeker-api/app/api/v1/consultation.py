"""专家会诊 API — 注入专家意见到 Agent 状态"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class InjectMessageRequest(BaseModel):
    """专家意见注入请求"""
    message: str
    role: str = "expert"  # "expert" | "admin" | "viewer"
    expert_name: Optional[str] = None


class ConsultationMessage(BaseModel):
    """会诊消息模型"""
    id: Optional[str] = None
    task_id: str
    role: str
    message: str
    expert_name: Optional[str] = None
    created_at: Optional[str] = None


@router.post("/{task_id}/inject")
async def inject_expert_message(task_id: str, req: InjectMessageRequest):
    """注入专家意见到运行中的 Agent 状态

    消息被写入 Supabase consultation_messages 表，
    Agent 节点在下一轮开始时读取这些消息。
    """
    # 验证任务是否存在
    task_resp = supabase.table("tasks").select("id, status").eq("id", task_id).execute()
    if not task_resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_status = task_resp.data[0].get("status", "")
    if task_status not in ("analyzing", "deliberating", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"任务状态为 {task_status}，不接受新的专家意见"
        )

    # 写入 consultation_messages 表
    message_record = {
        "task_id": task_id,
        "role": req.role,
        "message": req.message,
        "expert_name": req.expert_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        resp = supabase.table("consultation_messages").insert(message_record).execute()
        return {"status": "ok", "message_id": resp.data[0].get("id") if resp.data else None}
    except Exception as e:
        logger.error("Failed to insert consultation message: %s", e)
        raise HTTPException(status_code=500, detail="消息注入失败，请稍后重试")


@router.get("/{task_id}/messages")
async def get_consultation_messages(task_id: str):
    """获取任务的专家会诊消息"""
    resp = supabase.table("consultation_messages").select("*").eq("task_id", task_id).order(
        "created_at", desc=False
    ).execute()
    return {"messages": resp.data}


@router.get("/{task_id}/unread")
async def get_unread_messages(task_id: str, after: Optional[str] = None):
    """获取未读的专家会诊消息（Agent 节点调用）"""
    query = supabase.table("consultation_messages").select("*").eq("task_id", task_id)
    if after:
        query = query.gt("created_at", after)
    resp = query.order("created_at", desc=False).execute()
    return {"messages": resp.data}
