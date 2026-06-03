"""Public case library API."""
from __future__ import annotations

import logging
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.services.builtin_cases import get_builtin_case
from app.services.case_library import find_public_file, sanitize_case_for_response
from app.services.text_validation import decode_text_bytes
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()

Category = Literal["all", "text_generation", "image_forgery", "image_text_mixed", "audio_forgery", "video_forgery"]


class CaseListResponse(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int


class PreviewUrlRequest(BaseModel):
    file_id: str = Field(..., min_length=1)


def _fetch_public_case(case_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("case_library_entries")
        .select("*")
        .eq("status", "published")
        .eq("id", case_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _find_private_storage_path(row: dict[str, Any], file_id: str) -> str | None:
    task_id = row.get("task_id")
    if not task_id:
        return None
    try:
        resp = supabase.table("tasks").select("metadata,storage_paths").eq("id", task_id).limit(1).execute()
    except Exception as exc:
        logger.warning("Failed to fetch task files for public case preview %s: %s", row.get("id"), exc)
        return None
    task = resp.data[0] if resp.data else {}
    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    storage_paths = task.get("storage_paths") if isinstance(task.get("storage_paths"), dict) else {}
    files = metadata.get("files") or storage_paths.get("files") or []
    for item in files:
        if isinstance(item, dict) and str(item.get("id")) == str(file_id):
            storage_path = item.get("storage_path")
            return str(storage_path) if storage_path else None
    return None


def _download_storage_bytes(storage_path: str) -> bytes:
    raw = supabase.storage.from_("media").download(storage_path)
    if isinstance(raw, dict):
        raw = raw.get("data") or raw.get("body") or b""
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return bytes(raw)


def _public_case_file_or_404(case_id: str, file_id: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    try:
        row = _fetch_public_case(case_id)
    except Exception as exc:
        logger.error("Failed to fetch public case %s for preview: %s", case_id, exc)
        raise HTTPException(status_code=503, detail="公开案例暂时不可用")
    if not row:
        raise HTTPException(status_code=404, detail="公开案例不存在")

    file_info = find_public_file(row, file_id)
    storage_path = _find_private_storage_path(row, file_id)
    if not file_info or not storage_path:
        raise HTTPException(status_code=404, detail="公开案例检材不存在")
    return row, file_info, storage_path


@router.get("", response_model=CaseListResponse)
async def list_cases(category: Category = "all", page: int = 1, page_size: int = 6):
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 24)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size - 1

    try:
        query = (
            supabase.table("case_library_entries")
            .select("*", count="exact")
            .eq("status", "published")
        )
        if category != "all":
            query = query.eq("media_category", category)
        resp = query.order("published_at", desc=True).range(start, end).execute()
        return CaseListResponse(
            items=[sanitize_case_for_response(row) for row in (resp.data or [])],
            page=safe_page,
            page_size=safe_page_size,
            total=resp.count if resp.count is not None else len(resp.data or []),
        )
    except Exception as exc:
        logger.error("Failed to list public cases: %s", exc)
        raise HTTPException(status_code=503, detail="公开案例库暂时不可用")


@router.get("/{case_id}")
async def get_case(case_id: str):
    builtin = get_builtin_case(case_id)
    if builtin:
        return sanitize_case_for_response(builtin, include_report=True)
    try:
        row = _fetch_public_case(case_id)
    except Exception as exc:
        logger.error("Failed to fetch public case %s: %s", case_id, exc)
        raise HTTPException(status_code=503, detail="公开案例暂时不可用")
    if not row:
        raise HTTPException(status_code=404, detail="公开案例不存在")
    return sanitize_case_for_response(row, include_report=True)


@router.post("/{case_id}/preview-url")
async def create_preview_url(case_id: str, request: PreviewUrlRequest):
    _, file_info, storage_path = _public_case_file_or_404(case_id, request.file_id)
    try:
        signed = supabase.storage.from_("media").create_signed_url(storage_path, 600)
        signed_url = signed.get("signedURL") or signed.get("signedUrl")
        if not signed_url:
            raise ValueError("Empty signed URL response")
        if str(file_info.get("mime_type") or "").startswith("text/"):
            decoded = decode_text_bytes(_download_storage_bytes(storage_path), max_chars=20000)
            return {
                "signed_url": signed_url,
                "expires_in": 600,
                "preview_kind": "text",
                "text": decoded["text"],
                "charset": "utf-8",
                "detected_encoding": decoded["encoding"],
                "text_url": f"/api/v1/cases/{case_id}/files/{request.file_id}/text",
            }
        return {"signed_url": signed_url, "expires_in": 600, "preview_kind": "file"}
    except Exception as exc:
        logger.error("Failed to sign public case file %s/%s: %s", case_id, request.file_id, exc)
        raise HTTPException(status_code=500, detail="检材预览链接生成失败")


@router.get("/{case_id}/files/{file_id}/text")
async def preview_text_file(case_id: str, file_id: str):
    _, file_info, storage_path = _public_case_file_or_404(case_id, file_id)
    if not str(file_info.get("mime_type") or "").startswith("text/"):
        raise HTTPException(status_code=415, detail="该检材不是文本文件")
    try:
        decoded = decode_text_bytes(_download_storage_bytes(storage_path))
    except Exception as exc:
        logger.error("Failed to decode public case text file %s/%s: %s", case_id, file_id, exc)
        raise HTTPException(status_code=500, detail="文本检材解码失败")
    filename = quote(str(file_info.get("name") or f"{file_id}.txt"))
    return PlainTextResponse(
        decoded["text"],
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}"},
    )


@router.delete("/{case_id}", status_code=204)
async def delete_case(case_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id == "anonymous":
        raise HTTPException(status_code=401, detail="需要登录")
    try:
        resp = (
            supabase.table("case_library_entries")
            .select("id, user_id")
            .eq("id", case_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch case %s for deletion: %s", case_id, exc)
        raise HTTPException(status_code=503, detail="服务暂时不可用")
    if not resp.data:
        raise HTTPException(status_code=404, detail="案例不存在")
    if resp.data[0].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权删除此案例")
    try:
        supabase.table("case_library_rag_chunks").delete().eq("source_kind", "public").eq("case_id", case_id).execute()
        supabase.table("case_library_entries").delete().eq("id", case_id).execute()
    except Exception as exc:
        logger.error("Failed to delete case %s: %s", case_id, exc)
        raise HTTPException(status_code=503, detail="删除失败，请稍后重试")
