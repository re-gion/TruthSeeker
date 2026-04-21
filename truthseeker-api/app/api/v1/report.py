"""报告下载 API — Markdown / PDF 格式"""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.services.audit_log import record_audit_event
from app.services.report_generator import generate_markdown_report, generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter()


def _assert_task_owner(task_id: str, request: Request) -> None:
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id == "anonymous":
        raise HTTPException(status_code=401, detail="未认证用户无法下载报告，请先登录")

    try:
        from app.utils.supabase_client import supabase

        resp = supabase.table("tasks").select("id,user_id").eq("id", task_id).execute()
    except Exception as exc:
        logger.warning("Failed to verify report owner for %s: %s", task_id, exc)
        raise HTTPException(status_code=403, detail="无法验证任务归属")

    if not resp.data:
        raise HTTPException(status_code=404, detail="任务不存在")
    task_user_id = resp.data[0].get("user_id")
    if task_user_id and task_user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该任务报告")


@router.get("/{task_id}/md")
async def download_markdown_report(task_id: str, request: Request):
    """下载 Markdown 格式的鉴伪与溯源分析报告"""
    _assert_task_owner(task_id, request)
    try:
        md_content = await generate_markdown_report(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate markdown report for %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="报告生成失败")

    record_audit_event(
        action="report_downloaded",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"format": "md"},
    )

    return StreamingResponse(
        iter([md_content.encode("utf-8")]),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="truthseeker-report-{task_id}.md"',
        },
    )


@router.get("/{task_id}/pdf")
async def download_pdf_report(task_id: str, request: Request):
    """下载 PDF 格式的鉴伪与溯源分析报告"""
    _assert_task_owner(task_id, request)
    try:
        pdf_bytes = await generate_pdf_report(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate pdf report for %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="报告生成失败")

    record_audit_event(
        action="report_downloaded",
        task_id=task_id,
        user_id=getattr(request.state, "user_id", None),
        metadata={"format": "pdf"},
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="truthseeker-report-{task_id}.pdf"',
        },
    )
