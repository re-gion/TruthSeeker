"""Private personal experience library API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.experience_library import confirm_experience_drafts, delete_experience
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class ExperienceDraftRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    drafts: list[dict[str, Any]] = Field(default_factory=list)


def _current_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id == "anonymous":
        raise HTTPException(status_code=401, detail="需要登录")
    return str(user_id)


def _sanitize_entry(row: dict[str, Any]) -> dict[str, Any]:
    collaboration_session_id = row.get("source_collaboration_session_id") or row.get("source_session_id")
    return {
        "id": row.get("id"),
        "source_task_id": row.get("source_task_id"),
        "source_session_id": collaboration_session_id,
        "source_collaboration_session_id": collaboration_session_id,
        "target_agents": row.get("target_agents") or [],
        "title": row.get("title") or "",
        "problem_pattern": row.get("problem_pattern") or "",
        "recommended_method": row.get("recommended_method") or "",
        "evidence_to_check": row.get("evidence_to_check") or [],
        "when_to_escalate": row.get("when_to_escalate") or "",
        "limitations": row.get("limitations") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.get("")
async def list_experiences(request: Request, agent: str = "all", q: str = "", page: int = 1, page_size: int = 12):
    user_id = _current_user_id(request)
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 48)
    try:
        query = (
            supabase.table("experience_library_entries")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
        )
        rows = query.order("created_at", desc=True).execute().data or []
    except Exception as exc:
        logger.error("Failed to list experiences for user %s: %s", user_id, exc)
        raise HTTPException(status_code=503, detail="个人经验库暂时不可用")

    if agent != "all":
        rows = [row for row in rows if agent in (row.get("target_agents") or [])]
    if q.strip():
        needle = q.strip().lower()
        rows = [
            row for row in rows
            if needle in " ".join(str(row.get(key) or "") for key in ("title", "problem_pattern", "recommended_method")).lower()
        ]

    total = len(rows)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": [_sanitize_entry(row) for row in rows[start:end]],
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
    }


@router.get("/{entry_id}")
async def get_experience(entry_id: str, request: Request):
    user_id = _current_user_id(request)
    try:
        resp = (
            supabase.table("experience_library_entries")
            .select("*")
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch experience %s: %s", entry_id, exc)
        raise HTTPException(status_code=503, detail="个人经验暂时不可用")
    if not resp.data:
        raise HTTPException(status_code=404, detail="个人经验不存在")
    return _sanitize_entry(resp.data[0])


@router.post("/confirm")
async def confirm_experiences(request_body: ExperienceDraftRequest, request: Request):
    user_id = _current_user_id(request)
    try:
        return await confirm_experience_drafts(
            user_id=user_id,
            task_id=request_body.task_id,
            session_id=request_body.session_id,
            drafts=request_body.drafts,
        )
    except Exception as exc:
        logger.error("Failed to confirm experience drafts for task %s: %s", request_body.task_id, exc)
        raise HTTPException(status_code=503, detail="个人经验入库失败")


@router.delete("/{entry_id}", status_code=204)
async def remove_experience(entry_id: str, request: Request):
    user_id = _current_user_id(request)
    try:
        delete_experience(entry_id=entry_id, user_id=user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="个人经验不存在")
    except Exception as exc:
        logger.error("Failed to delete experience %s: %s", entry_id, exc)
        raise HTTPException(status_code=503, detail="个人经验删除失败")
