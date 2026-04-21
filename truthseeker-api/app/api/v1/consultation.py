"""专家会诊 API — 注入专家意见到 Agent 状态"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.audit_log import record_audit_event
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()

INVITE_TTL_HOURS = 24


class InjectMessageRequest(BaseModel):
    """专家意见注入请求"""
    message: str
    role: str = "expert"  # "expert" | "admin" | "viewer"
    expert_name: Optional[str] = None
    invite_token: Optional[str] = None


class ConsultationMessage(BaseModel):
    """会诊消息模型"""
    id: Optional[str] = None
    task_id: str
    role: str
    message: str
    expert_name: Optional[str] = None
    created_at: Optional[str] = None


class InviteResponse(BaseModel):
    task_id: str
    token: str
    invite_url: str
    expires_at: str


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _invite_is_expired(invite: dict) -> bool:
    expires_at = _parse_datetime(invite.get("expires_at"))
    return bool(expires_at and expires_at <= datetime.now(timezone.utc))


def _assert_task_owner(task: dict, request: Request) -> None:
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id == "anonymous":
        return
    task_user_id = task.get("user_id")
    if task_user_id and task_user_id != user_id:
        raise HTTPException(status_code=403, detail="无权操作该任务会诊")


@router.post("/{task_id}/inject")
async def inject_expert_message(task_id: str, req: InjectMessageRequest, request: Request):
    """注入专家意见到运行中的 Agent 状态

    消息被写入 Supabase consultation_messages 表，
    Agent 节点在下一轮开始时读取这些消息。
    """
    # 验证任务是否存在
    task_resp = supabase.table("tasks").select("id,status,user_id").eq("id", task_id).execute()
    if not task_resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = task_resp.data[0]
    task_status = task.get("status", "")
    if task_status not in ("analyzing", "deliberating", "pending", "waiting_consultation"):
        raise HTTPException(
            status_code=400,
            detail=f"任务状态为 {task_status}，不接受新的专家意见"
        )
    request_user_id = getattr(request.state, "user_id", None)
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))

    if req.role == "expert":
        _validate_invite_token(task_id, req.invite_token)
    elif not is_authenticated:
        raise HTTPException(status_code=401, detail="主持人会诊消息需要登录")
    else:
        _assert_task_owner(task, request)

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
        record_audit_event(
            action="consultation_message",
            task_id=task_id,
            user_id=request_user_id,
            actor_role=req.role,
            metadata={"message_length": len(req.message), "invite_token": req.invite_token},
        )
        return {"status": "ok", "message_id": resp.data[0].get("id") if resp.data else None}
    except Exception as e:
        logger.error("Failed to insert consultation message: %s", e)
        raise HTTPException(status_code=500, detail="消息注入失败，请稍后重试")


@router.post("/{task_id}/invite", response_model=InviteResponse)
async def create_consultation_invite(task_id: str, request: Request):
    """创建专家邀请链接。"""
    task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
    if not task_resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_task_owner(task_resp.data[0], request)

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)).isoformat()
    invite_record = {
        "task_id": task_id,
        "token": token,
        "status": "pending",
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase.table("consultation_invites").insert(invite_record).execute()
        record_audit_event(
            action="consultation_invite_created",
            task_id=task_id,
            user_id=getattr(request.state, "user_id", None),
            metadata={"invite_token": token},
        )
    except Exception as e:
        logger.error("Failed to create invite: %s", e)
        raise HTTPException(status_code=500, detail="邀请创建失败")

    return InviteResponse(
        task_id=task_id,
        token=token,
        expires_at=expires_at,
        invite_url=f"/detect/{task_id}?role=expert&invite_token={token}",
    )


@router.get("/invite/{token}")
async def validate_consultation_invite(token: str):
    """校验邀请令牌并返回任务上下文。"""
    resp = (
        supabase.table("consultation_invites")
        .select("*")
        .eq("token", token)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="邀请链接无效")

    invite = resp.data[0]
    if invite.get("status") == "expired" or _invite_is_expired(invite):
        raise HTTPException(status_code=410, detail="邀请链接已过期")

    return {
        "task_id": invite.get("task_id"),
        "role": "expert",
        "invite_token": token,
        "status": invite.get("status", "pending"),
        "expires_at": invite.get("expires_at"),
    }


@router.get("/{task_id}/messages")
async def get_consultation_messages(task_id: str, request: Request, invite_token: Optional[str] = None):
    """获取任务的专家会诊消息"""
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))
    if not is_authenticated:
        _validate_invite_token(task_id, invite_token)
    else:
        task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
        if not task_resp.data:
            raise HTTPException(status_code=404, detail="任务不存在")
        _assert_task_owner(task_resp.data[0], request)

    resp = supabase.table("consultation_messages").select("*").eq("task_id", task_id).order(
        "created_at", desc=False
    ).execute()
    return {"messages": resp.data}


@router.get("/{task_id}/agent-history")
async def get_agent_history(task_id: str, request: Request, invite_token: Optional[str] = None):
    """获取已持久化的智能体检测记录，供专家邀请链接和主持人刷新页面后回放。"""
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))
    if not is_authenticated:
        _validate_invite_token(task_id, invite_token)
    else:
        task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
        if not task_resp.data:
            raise HTTPException(status_code=404, detail="任务不存在")
        _assert_task_owner(task_resp.data[0], request)

    task_resp = supabase.table("tasks").select("id,title,status,input_type,result,metadata").eq("id", task_id).execute()
    if not task_resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")

    logs_resp = (
        supabase.table("agent_logs")
        .select("*")
        .eq("task_id", task_id)
        .order("timestamp", desc=False)
        .execute()
    )
    states_resp = (
        supabase.table("analysis_states")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=False)
        .execute()
    )
    reports_resp = (
        supabase.table("reports")
        .select("*")
        .eq("task_id", task_id)
        .order("generated_at", desc=True)
        .execute()
    )

    return {
        "task": task_resp.data[0],
        "agent_logs": logs_resp.data or [],
        "analysis_states": states_resp.data or [],
        "report": reports_resp.data[0] if reports_resp.data else None,
    }


@router.get("/{task_id}/unread")
async def get_unread_messages(
    task_id: str,
    request: Request,
    after: Optional[str] = None,
    invite_token: Optional[str] = None,
):
    """获取未读的专家会诊消息（Agent 节点调用）"""
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))
    if not is_authenticated:
        _validate_invite_token(task_id, invite_token)
    else:
        task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
        if not task_resp.data:
            raise HTTPException(status_code=404, detail="任务不存在")
        _assert_task_owner(task_resp.data[0], request)

    query = supabase.table("consultation_messages").select("*").eq("task_id", task_id)
    if after:
        query = query.gt("created_at", after)
    resp = query.order("created_at", desc=False).execute()
    return {"messages": resp.data}


def _validate_invite_token(task_id: str, invite_token: Optional[str]) -> None:
    if not invite_token:
        raise HTTPException(status_code=401, detail="专家会诊需要有效邀请令牌")
    resp = (
        supabase.table("consultation_invites")
        .select("*")
        .eq("token", invite_token)
        .eq("task_id", task_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=403, detail="邀请令牌无效")
    invite = resp.data[0]
    if invite.get("status") == "expired" or _invite_is_expired(invite):
        raise HTTPException(status_code=410, detail="邀请链接已过期")
    # 标记为已使用，但允许专家刷新页面或重新进入同一链接读取上下文。
    try:
        supabase.table("consultation_invites").update({"status": "used"}).eq("id", invite["id"]).execute()
    except Exception as exc:
        logger.error("Failed to mark invite as used: %s", exc)
