"""报告下载 API — Markdown / PDF 格式"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.report_generator import generate_markdown_report, generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{task_id}/md")
async def download_markdown_report(task_id: str):
    """下载 Markdown 格式的鉴伪与溯源分析报告"""
    try:
        md_content = await generate_markdown_report(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate markdown report for %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="报告生成失败")

    return StreamingResponse(
        iter([md_content.encode("utf-8")]),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="truthseeker-report-{task_id}.md"',
        },
    )


@router.get("/{task_id}/pdf")
async def download_pdf_report(task_id: str):
    """下载 PDF 格式的鉴伪与溯源分析报告"""
    try:
        pdf_bytes = await generate_pdf_report(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate pdf report for %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="报告生成失败")

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="truthseeker-report-{task_id}.pdf"',
        },
    )
