"""报告分享 API — 生成/访问公开分享链接"""
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.analysis_persistence import normalize_final_verdict
from app.services.audit_log import record_audit_event
from app.services.report_generator import generate_markdown_report
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class ShareResponse(BaseModel):
    share_token: str
    share_url: str
    report_hash: str | None = None


def _assert_task_owner(task_id: str, request: Request) -> None:
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id == "anonymous":
        return

    try:
        task_resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
    except Exception as exc:
        logger.warning("Failed to verify share owner for %s: %s", task_id, exc)
        raise HTTPException(status_code=403, detail="无法验证任务归属")

    if not task_resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")
    task_user_id = task_resp.data[0].get("user_id")
    if task_user_id and task_user_id != user_id:
        raise HTTPException(status_code=403, detail="无权分享该任务报告")


@router.post("/{task_id}", response_model=ShareResponse)
async def create_share_link(task_id: str, request: Request):
    """为指定任务生成报告分享链接"""
    _assert_task_owner(task_id, request)
    resp = supabase.table("reports").select("id, share_token, report_hash").eq("task_id", task_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    report = resp.data[0]

    if report.get("share_token"):
        token = report["share_token"]
    else:
        token = secrets.token_urlsafe(16)
        supabase.table("reports").update({"share_token": token}).eq("id", report["id"]).execute()

    record_audit_event(
        action="share_created",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"share_token": token, "report_hash": report.get("report_hash")},
    )

    return ShareResponse(
        share_token=token,
        share_url=f"/report/{token}",
        report_hash=report.get("report_hash"),
    )


@router.get("/{token}")
async def get_shared_report(token: str, request: Request):
    """通过分享令牌访问报告（无需认证）"""
    resp = supabase.table("reports").select("*, tasks(*)").eq("share_token", token).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")

    report = resp.data[0]
    task = report.get("tasks") or {}
    record_audit_event(
        action="share_viewed",
        task_id=task.get("id") or report.get("task_id"),
        user_id=getattr(request.state, "user_id", None),
        actor_role="viewer",
        metadata={"share_token": token, "report_hash": report.get("report_hash")},
    )

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
            "report_hash": report.get("report_hash"),
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
