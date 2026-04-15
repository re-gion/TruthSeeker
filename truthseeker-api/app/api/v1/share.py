"""报告分享 API — 生成/访问公开分享链接"""
import logging
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.analysis_persistence import normalize_final_verdict
from app.services.report_generator import generate_markdown_report
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class ShareResponse(BaseModel):
    share_token: str
    share_url: str


@router.post("/{task_id}", response_model=ShareResponse)
async def create_share_link(task_id: str):
    """为指定任务生成报告分享链接"""
    resp = supabase.table("reports").select("id, share_token").eq("task_id", task_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    report = resp.data[0]

    if report.get("share_token"):
        token = report["share_token"]
    else:
        token = secrets.token_urlsafe(16)
        supabase.table("reports").update({"share_token": token}).eq("id", report["id"]).execute()

    return ShareResponse(
        share_token=token,
        share_url=f"/report/{token}",
    )


@router.get("/{token}")
async def get_shared_report(token: str):
    """通过分享令牌访问报告（无需认证）"""
    resp = supabase.table("reports").select("*, tasks(*)").eq("share_token", token).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")

    report = resp.data[0]
    task = report.get("tasks") or {}

    try:
        md_content = await generate_markdown_report(task.get("id", report["task_id"]))
    except Exception as e:
        logger.error("Failed to generate shared report: %s", e)
        md_content = "# 报告生成失败\n\n报告生成过程中出现错误，请稍后重试。"

    return {
        "report": {
            "verdict": report.get("verdict"),
            "confidence": report.get("confidence_overall"),
            "confidence_overall": report.get("confidence_overall"),
            "summary": report.get("summary"),
            "generated_at": report.get("generated_at"),
        },
        "task": {
            "id": task.get("id"),
            "title": task.get("title"),
            "input_type": task.get("input_type"),
            "status": task.get("status"),
        },
        "markdown": md_content,
        "verdict_payload": normalize_final_verdict(report.get("verdict_payload") or task.get("result") or {}),
    }
