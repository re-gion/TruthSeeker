"""专家会诊 API — 注入专家意见到 Agent 状态"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.audit_log import record_audit_event
from app.services.consultation_workflow import build_moderator_summary, utc_now_iso
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()

INVITE_TTL_HOURS = 24


class InjectMessageRequest(BaseModel):
    """专家意见注入请求"""
    message: str
    role: str = "expert"  # "expert" | "user" | "commander" | "viewer"
    expert_name: Optional[str] = None
    invite_token: Optional[str] = None
    session_id: Optional[str] = None
    message_type: str = "expert_opinion"
    anchor_agent: Optional[str] = None
    anchor_phase: Optional[str] = None
    confidence: Optional[float] = None
    suggested_action: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class SessionDecisionRequest(BaseModel):
    reason: Optional[str] = None


class SummaryConfirmRequest(BaseModel):
    summary: str


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
    session_id: Optional[str] = None


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


def _fetch_task_or_404(task_id: str, columns: str = "id,status,user_id,metadata,storage_paths") -> dict:
    task_resp = supabase.table("tasks").select(columns).eq("id", task_id).execute()
    if not task_resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task_resp.data[0]


def _fetch_session_or_404(task_id: str, session_id: str) -> dict:
    resp = (
        supabase.table("consultation_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("task_id", task_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="会诊会话不存在")
    return resp.data[0]


def _latest_session(task_id: str) -> dict | None:
    resp = (
        supabase.table("consultation_sessions")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _session_for_invite_or_latest(task_id: str, invite: dict | None = None) -> dict | None:
    session_id = (invite or {}).get("session_id")
    if session_id:
        return _fetch_session_or_404(task_id, session_id)
    return _latest_session(task_id)


def _update_session(session_id: str, payload: dict) -> dict:
    resp = supabase.table("consultation_sessions").update(payload).eq("id", session_id).execute()
    return resp.data[0] if resp.data else {**payload, "id": session_id}


def _session_messages(task_id: str, session_id: str | None) -> list[dict]:
    query = supabase.table("consultation_messages").select("*").eq("task_id", task_id)
    if session_id:
        query = query.eq("session_id", session_id)
    resp = query.order("created_at", desc=False).execute()
    return resp.data or []


def _insert_commander_message(task_id: str, session_id: str, message: str, message_type: str = "moderator_note") -> None:
    try:
        supabase.table("consultation_messages").insert({
            "task_id": task_id,
            "session_id": session_id,
            "role": "commander",
            "message": message,
            "expert_name": "研判指挥Agent",
            "message_type": message_type,
            "created_at": utc_now_iso(),
        }).execute()
    except Exception as exc:
        logger.error("Failed to insert commander consultation message: %s", exc)


@router.post("/{task_id}/inject")
async def inject_expert_message(task_id: str, req: InjectMessageRequest, request: Request):
    """注入专家意见到运行中的 Agent 状态

    消息被写入 Supabase consultation_messages 表，
    Agent 节点在下一轮开始时读取这些消息。
    """
    task = _fetch_task_or_404(task_id, "id,status,user_id")
    task_status = task.get("status", "")
    if task_status not in ("analyzing", "deliberating", "pending", "waiting_consultation", "waiting_consultation_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"任务状态为 {task_status}，不接受新的专家意见"
        )
    request_user_id = getattr(request.state, "user_id", None)
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))

    session_id = req.session_id
    if req.role == "expert":
        invite = _validate_invite_token(task_id, req.invite_token, session_id=session_id)
        if not session_id and invite.get("session_id"):
            session_id = invite.get("session_id")
    elif not is_authenticated:
        raise HTTPException(status_code=401, detail="用户会诊消息需要登录")
    else:
        _assert_task_owner(task, request)
        if session_id:
            _fetch_session_or_404(task_id, session_id)

    # 写入 consultation_messages 表
    message_record = {
        "task_id": task_id,
        "role": req.role,
        "message": req.message,
        "expert_name": req.expert_name,
        "session_id": session_id,
        "message_type": req.message_type,
        "anchor_agent": req.anchor_agent,
        "anchor_phase": req.anchor_phase,
        "confidence": req.confidence,
        "suggested_action": req.suggested_action,
        "metadata": req.metadata,
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
async def create_consultation_invite(task_id: str, request: Request, session_id: Optional[str] = None):
    """创建专家邀请链接。"""
    task = _fetch_task_or_404(task_id, "id,user_id")
    _assert_task_owner(task, request)
    if session_id:
        _fetch_session_or_404(task_id, session_id)
    else:
        current = _latest_session(task_id)
        session_id = current.get("id") if current else None

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)).isoformat()
    invite_record = {
        "task_id": task_id,
        "token": token,
        "session_id": session_id,
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
        session_id=session_id,
    )


@router.get("/{task_id}/session")
async def get_current_consultation_session(task_id: str, request: Request, invite_token: Optional[str] = None):
    """读取当前会诊 session 和上下文。"""
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))
    invite = None
    if invite_token:
        invite = _validate_invite_token(task_id, invite_token)
    else:
        task = _fetch_task_or_404(task_id, "id,user_id")
        _assert_task_owner(task, request)
    session = _session_for_invite_or_latest(task_id, invite)
    return {"session": session}


@router.post("/{task_id}/sessions/{session_id}/approve")
async def approve_consultation_session(task_id: str, session_id: str, request: Request):
    """用户批准第二次及以后的人机协同会诊。"""
    task = _fetch_task_or_404(task_id, "id,user_id")
    _assert_task_owner(task, request)
    session = _fetch_session_or_404(task_id, session_id)
    if session.get("status") != "waiting_user_approval":
        raise HTTPException(status_code=400, detail="当前会诊不处于待用户确认状态")
    updated = _update_session(session_id, {
        "status": "active",
        "approved_by": getattr(request.state, "user_id", None),
        "approved_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    })
    try:
        supabase.table("tasks").update({
            "status": "waiting_consultation",
            "updated_at": utc_now_iso(),
        }).eq("id", task_id).execute()
    except Exception as exc:
        logger.error("Failed to mark task waiting_consultation after approval: %s", exc)
    _insert_commander_message(task_id, session_id, "用户已允许再次进入专家会诊。", "approval")
    record_audit_event(
        action="consultation_approved",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"session_id": session_id},
    )
    return {"status": "ok", "session": updated}


@router.post("/{task_id}/sessions/{session_id}/skip")
async def skip_consultation_session(task_id: str, session_id: str, req: SessionDecisionRequest, request: Request):
    """用户仅跳过本次重复会诊，系统保留风险继续流程。"""
    task = _fetch_task_or_404(task_id, "id,user_id")
    _assert_task_owner(task, request)
    session = _fetch_session_or_404(task_id, session_id)
    if session.get("status") != "waiting_user_approval":
        raise HTTPException(status_code=400, detail="只能跳过等待用户审批的重复会诊")
    summary_payload = {
        "skip_scope": "current_only",
        "reason": req.reason or "用户选择跳过本次专家会诊",
        "skipped_at": utc_now_iso(),
    }
    updated = _update_session(session_id, {
        "status": "skipped",
        "summary_payload": summary_payload,
        "closed_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    })
    try:
        supabase.table("tasks").update({
            "status": "waiting_consultation",
            "updated_at": utc_now_iso(),
        }).eq("id", task_id).execute()
    except Exception as exc:
        logger.error("Failed to mark task waiting_consultation after skip: %s", exc)
    _insert_commander_message(task_id, session_id, summary_payload["reason"], "skip")
    record_audit_event(
        action="consultation_skipped",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"session_id": session_id, "skip_scope": "current_only"},
    )
    return {"status": "ok", "session": updated}


@router.post("/{task_id}/sessions/{session_id}/close")
async def close_consultation_session(task_id: str, session_id: str, request: Request):
    """用户结束会诊，进入 Commander 摘要待确认状态。"""
    task = _fetch_task_or_404(task_id, "id,user_id")
    _assert_task_owner(task, request)
    session = _fetch_session_or_404(task_id, session_id)
    if session.get("status") not in {"active", "requested", "waiting_user_approval"}:
        raise HTTPException(status_code=400, detail="当前会诊状态不能结束")
    messages = _session_messages(task_id, session_id)
    summary_payload = build_moderator_summary(messages=messages)
    updated = _update_session(session_id, {
        "status": "summary_pending",
        "closed_at": utc_now_iso(),
        "summary_payload": summary_payload,
        "updated_at": utc_now_iso(),
    })
    _insert_commander_message(
        task_id,
        session_id,
        summary_payload["generated_summary"],
        "summary",
    )
    record_audit_event(
        action="consultation_closed",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"session_id": session_id, "message_count": len(messages)},
    )
    return {"status": "ok", "session": updated}


@router.post("/{task_id}/sessions/{session_id}/summary")
async def confirm_consultation_summary(
    task_id: str,
    session_id: str,
    req: SummaryConfirmRequest,
    request: Request,
):
    """用户确认或编辑 Commander 会诊摘要。"""
    task = _fetch_task_or_404(task_id, "id,user_id")
    _assert_task_owner(task, request)
    session = _fetch_session_or_404(task_id, session_id)
    if session.get("status") not in {"summary_pending", "summary_confirmed"}:
        raise HTTPException(status_code=400, detail="当前会诊摘要不能确认")
    messages = _session_messages(task_id, session_id)
    summary_payload = build_moderator_summary(
        messages=messages,
        user_confirmed_summary=req.summary,
    )
    updated = _update_session(session_id, {
        "status": "summary_confirmed",
        "summary_payload": summary_payload,
        "updated_at": utc_now_iso(),
    })
    _insert_commander_message(task_id, session_id, req.summary, "summary_confirmed")
    record_audit_event(
        action="consultation_summary_confirmed",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"session_id": session_id, "message_count": len(messages)},
    )
    return {"status": "ok", "session": updated}


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
        "session_id": invite.get("session_id"),
        "status": invite.get("status", "pending"),
        "expires_at": invite.get("expires_at"),
    }


@router.get("/{task_id}/messages")
async def get_consultation_messages(task_id: str, request: Request, invite_token: Optional[str] = None):
    """获取任务的专家会诊消息"""
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))
    invite = None
    if not is_authenticated:
        invite = _validate_invite_token(task_id, invite_token)
    else:
        task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
        if not task_resp.data:
            raise HTTPException(status_code=404, detail="任务不存在")
        _assert_task_owner(task_resp.data[0], request)

    query = supabase.table("consultation_messages").select("*").eq("task_id", task_id)
    if invite and invite.get("session_id"):
        query = query.eq("session_id", invite.get("session_id"))
    resp = query.order("created_at", desc=False).execute()
    return {"messages": resp.data}


@router.get("/{task_id}/agent-history")
async def get_agent_history(task_id: str, request: Request, invite_token: Optional[str] = None):
    """获取已持久化的智能体检测记录，供专家邀请链接和主持人刷新页面后回放。"""
    is_authenticated = bool(getattr(request.state, "is_authenticated", False))
    invite = None
    if not is_authenticated:
        invite = _validate_invite_token(task_id, invite_token)
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
    audit_resp = (
        supabase.table("audit_logs")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=False)
        .execute()
    )

    return {
        "task": task_resp.data[0],
        "agent_logs": logs_resp.data or [],
        "analysis_states": states_resp.data or [],
        "audit_logs": audit_resp.data or [],
        "consultation_session": _session_for_invite_or_latest(task_id, invite),
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
    invite = None
    if not is_authenticated:
        invite = _validate_invite_token(task_id, invite_token)
    else:
        task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
        if not task_resp.data:
            raise HTTPException(status_code=404, detail="任务不存在")
        _assert_task_owner(task_resp.data[0], request)

    query = supabase.table("consultation_messages").select("*").eq("task_id", task_id)
    if invite and invite.get("session_id"):
        query = query.eq("session_id", invite.get("session_id"))
    if after:
        query = query.gt("created_at", after)
    resp = query.order("created_at", desc=False).execute()
    return {"messages": resp.data}


def _validate_invite_token(task_id: str, invite_token: Optional[str], session_id: Optional[str] = None) -> dict:
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
    invite_session_id = invite.get("session_id")
    if session_id and invite_session_id and invite_session_id != session_id:
        raise HTTPException(status_code=403, detail="邀请令牌不属于该会诊会话")
    # 标记为已使用，但允许专家刷新页面或重新进入同一链接读取上下文。
    try:
        supabase.table("consultation_invites").update({"status": "used"}).eq("id", invite["id"]).execute()
    except Exception as exc:
        logger.error("Failed to mark invite as used: %s", exc)
        record_audit_event(
            action="consultation.invite_mark_used_failed",
            task_id=invite.get("task_id"),
            metadata={"invite_id": invite.get("id"), "error": f"{type(exc).__name__}: {exc}"},
        )
    return invite
