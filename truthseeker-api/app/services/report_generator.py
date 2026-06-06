"""报告生成服务 — Markdown + PDF 报告"""
import asyncio
import io
import inspect
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.services.analysis_persistence import normalize_final_verdict
from app.services.consultation_workflow import filter_human_consultation_messages
from app.services.input_types import display_input_type
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

MAX_REPORT_FIELD_CHARS = 1200
MAX_SEARCH_SUMMARY_CHARS = 280
REPORT_AUDIT_LOG_LIMIT = 50
SKIP_REPORT_KEYS = {"signed_url", "raw_response", "case_rag", "experience_rag"}
MARKDOWN_REPORT_FIELDS = {
    "llm_analysis": "LLM 分析",
    "llm_cross_validation": "LLM 逻辑质询",
    "llm_ruling": "LLM 最终研判",
}

AGENT_DISPLAY_NAMES = {
    "forensics": "电子取证 Agent",
    "osint": "情报溯源 Agent",
    "challenger": "逻辑质询 Agent",
    "commander": "综合研判 Agent",
}


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

async def _fetch_task_data(task_id: str) -> dict:
    """从 Supabase 获取任务的完整数据。"""
    return await asyncio.to_thread(_sync_fetch_task_data, task_id)


def _is_transient_read_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in ("readerror", "read error", "timeout", "connection reset", "server disconnected"))


def _execute_supabase_query(factory, *, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return factory()
        except Exception as exc:
            last_error = exc
            if attempt >= attempts or not _is_transient_read_error(exc):
                raise
            time.sleep(0.2 * attempt)
    raise last_error or RuntimeError("Supabase query failed")


def _sync_fetch_task_data(task_id: str) -> dict:
    """同步获取任务数据（在线程池中执行）"""
    # 1. 任务基本信息
    task_resp = _execute_supabase_query(lambda: supabase.table("tasks").select("*").eq("id", task_id).execute())
    if not task_resp.data:
        raise ValueError(f"Task not found: {task_id}")
    task = task_resp.data[0]

    # 2. 分析状态
    analysis_resp = _execute_supabase_query(
        lambda: (
            supabase.table("analysis_states")
            .select("*")
            .eq("task_id", task_id)
            .execute()
        )
    )
    analysis_states = analysis_resp.data or []

    # 3. Agent 日志
    logs_resp = _execute_supabase_query(
        lambda: (
            supabase.table("agent_logs")
            .select("*")
            .eq("task_id", task_id)
            .order("timestamp", desc=False)
            .execute()
        )
    )
    agent_logs = logs_resp.data or []

    audit_resp = _execute_supabase_query(
        lambda: (
            supabase.table("audit_logs")
            .select("*")
            .eq("task_id", task_id)
            .order("created_at", desc=False)
            .execute()
        )
    )
    audit_logs = audit_resp.data or []

    def _select_collaboration_rows(primary_table: str, legacy_table: str) -> list[dict]:
        for table_name in (primary_table, legacy_table):
            try:
                resp = _execute_supabase_query(
                    lambda table_name=table_name: (
                        supabase.table(table_name)
                        .select("*")
                        .eq("task_id", task_id)
                        .order("created_at", desc=False)
                        .execute()
                    )
                )
                if resp.data:
                    return resp.data or []
            except Exception as exc:
                logger.warning("Failed to fetch %s for report %s: %s", table_name, task_id, exc)
        return []

    consultation_sessions = _select_collaboration_rows("collaboration_sessions", "consultation_sessions")
    consultation_messages = _select_collaboration_rows("collaboration_messages", "consultation_messages")

    report_resp = _execute_supabase_query(
        lambda: (
            supabase.table("reports")
            .select("*")
            .eq("task_id", task_id)
            .order("generated_at", desc=True)
            .execute()
        )
    )
    report = report_resp.data[0] if report_resp.data else None

    return {
        "task": task,
        "report": report,
        "analysis_states": analysis_states,
        "agent_logs": agent_logs,
        "audit_logs": audit_logs,
        "consultation_sessions": consultation_sessions,
        "consultation_messages": consultation_messages,
    }


# ---------------------------------------------------------------------------
# Markdown 报告
# ---------------------------------------------------------------------------

async def generate_markdown_report(task_id: str) -> str:
    """生成 Markdown 格式的鉴伪与溯源分析报告"""
    data = await _fetch_task_data(task_id)
    task = data["task"]
    report = data["report"]
    analysis_states = data["analysis_states"]
    agent_logs = data["agent_logs"]
    audit_logs = data.get("audit_logs") or []
    consultation_sessions = data.get("consultation_sessions") or []
    consultation_messages = data.get("consultation_messages") or []
    detection_run_id = _resolve_final_detection_run_id(task, report, analysis_states, agent_logs, audit_logs)
    if detection_run_id:
        analysis_states = _filter_rows_by_detection_run_id(analysis_states, detection_run_id)
        agent_logs = _filter_rows_by_detection_run_id(agent_logs, detection_run_id)
        audit_logs = _filter_audit_logs_for_detection_run(audit_logs, detection_run_id)

    lines: list[str] = []

    # ---- 标题 ----
    lines.append("# TruthSeeker 跨模态鉴伪与溯源分析最终裁决报告")
    lines.append("")

    # ---- 任务信息 ----
    lines.append("## 一、任务信息")
    lines.append("")
    lines.append(f"| 项目 | 内容 |")
    lines.append(f"|------|------|")
    lines.append(f"| 任务 ID | `{task.get('id', 'N/A')}` |")
    lines.append(f"| 标题 | {task.get('title', 'N/A')} |")
    lines.append(f"| 输入类型 | {display_input_type(task.get('input_type'))} |")
    lines.append(f"| 状态 | {task.get('status', 'N/A')} |")
    lines.append(f"| 创建时间 | {_fmt_time(task.get('created_at'))} |")
    lines.append(f"| 完成时间 | {_fmt_time(task.get('completed_at'))} |")
    if report and report.get("report_hash"):
        lines.append(f"| 报告 Hash | `{report.get('report_hash')}` |")
    lines.append("")

    # ---- 最终裁决 ----
    result = _resolve_final_result(task, report)
    if result:
        lines.append("## 二、最终裁决")
        lines.append("")
        verdict = result.get("verdict", "N/A")
        confidence = result.get("confidence", "N/A")
        ruling_time = report.get("generated_at") if report else task.get("completed_at")
        lines.append(f"- **裁决结论**: {verdict}")
        lines.append(f"- **置信度**: {_fmt_confidence(confidence)}")
        lines.append(f"- **裁决时间**: {_fmt_time(ruling_time)}")
        key_evidence = result.get("key_evidence", [])
        if key_evidence:
            lines.append("- **关键证据**:")
            for ev in key_evidence:
                if isinstance(ev, dict):
                    description = ev.get("description") or ev.get("source") or str(ev)
                    lines.append(f"  - [{ev.get('type', '?')}] {description}")
                else:
                    lines.append(f"  - {ev}")
        lines.append("")

    # ---- 降级状态汇总 ----
    forensics = _extract_agent_result(analysis_states, "forensics")
    osint = _extract_agent_result(analysis_states, "osint") or _derive_osint_result_from_final_verdict(result)
    degraded_items: list[str] = []
    tool_limitations: list[str] = []

    def _format_tool_summary(tool_summary: dict) -> str:
        total = int(tool_summary.get("total", 0) or 0)
        success = int(tool_summary.get("success", 0) or 0)
        partial = int(tool_summary.get("partial", 0) or 0)
        available = int(tool_summary.get("available", success + partial) or 0)
        degraded = int(tool_summary.get("degraded", 0) or 0)
        failed = int(tool_summary.get("failed", 0) or 0)
        other = int(tool_summary.get("other", max(0, total - available - degraded - failed)) or 0)
        parts = [
            f"可用 {available}/{total or '?'}",
            f"完整成功 {success}",
        ]
        if partial:
            parts.append(f"部分可用 {partial}")
        if other:
            parts.append(f"其他 {other}")
        parts.extend([f"降级 {degraded}", f"失败 {failed}"])
        return "，".join(parts)

    def _collect_tool_limitations(agent_result: dict | None) -> None:
        if not agent_result:
            return
        tool_results = agent_result.get("tool_results") or agent_result.get("tool_matrix") or []
        for item in tool_results:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if status in ("partial", "degraded", "failed"):
                tool_name = item.get("tool", "unknown")
                target = item.get("target", "")
                error = item.get("error", "")
                summary = item.get("summary", "")
                status_label = {"partial": "部分可用", "degraded": "降级", "failed": "失败"}.get(status, str(status))
                detail = f"{tool_name} [{status_label}] ({target})"
                if error:
                    detail += f" — 错误: {error}"
                elif summary:
                    detail += f" — {summary}"
                tool_limitations.append(detail)

    if forensics and forensics.get("degraded"):
        tool_summary = forensics.get("tool_summary") or {}
        degraded_items.append(f"{_agent_display_name('forensics')} 降级（{_format_tool_summary(tool_summary)}）")
        _collect_tool_limitations(forensics)
    if osint and osint.get("degraded"):
        tool_summary = osint.get("tool_summary") or {}
        degraded_items.append(f"{_agent_display_name('osint')} 降级（{_format_tool_summary(tool_summary)}）")
        _collect_tool_limitations(osint)
    if result:
        forensics_degraded = (result.get("forensics_summary") or {}).get("degraded")
        osint_degraded = (result.get("osint_summary") or {}).get("degraded")
        if forensics_degraded and not forensics:
            degraded_items.append(f"{_agent_display_name('forensics')} 降级（详情见分析状态）")
        if osint_degraded and not osint:
            degraded_items.append(f"{_agent_display_name('osint')} 降级（详情见分析状态）")
    if degraded_items:
        lines.append("## ⚠️ 降级状态汇总")
        lines.append("")
        for item in degraded_items:
            lines.append(f"- {item}")
        if tool_limitations:
            lines.append("")
            lines.append("**具体工具受限/失败详情**:")
            for detail in tool_limitations[:10]:
                lines.append(f"  - {detail}")
            if len(tool_limitations) > 10:
                lines.append(f"  - ... 及其他 {len(tool_limitations) - 10} 个工具受限或失败")
        lines.append("")
        lines.append("> **注意**: 降级或部分可用表示外部工具权限、额度、网络或接口返回不完整；"
                    "已取得的数据仍会保留，但缺失部分需要在服务恢复或权限补齐后复核。")
        lines.append("")

    # ---- Forensics 分析 ----
    if forensics:
        lines.append(f"## 三、{_agent_display_name('forensics')} 分析")
        lines.append("")
        lines.extend(_dict_to_markdown(forensics).splitlines())
        lines.append("")

    # ---- OSINT 情报 ----
    lines.append(f"## 四、{_agent_display_name('osint')} 分析")
    lines.append("")
    if osint:
        lines.extend(_dict_to_markdown(osint).splitlines())
    else:
        lines.append(f"- 暂无 {_agent_display_name('osint')} 数据（Agent 未运行或结果未入库）。")
    lines.append("")

    # ---- 公开案例与个人经验 RAG ----
    challenger = _extract_agent_result(analysis_states, "challenger")
    case_rag_sections = _build_case_rag_sections(
        (forensics or {}).get("case_rag") if forensics else None,
        (forensics or {}).get("experience_rag") if forensics else None,
        (osint or {}).get("case_rag") if osint else None,
        (osint or {}).get("experience_rag") if osint else None,
        (challenger or {}).get("challenger_experience_rag") if challenger else None,
    )
    lines.append("## 五、公开案例与个人经验 RAG 检索情况")
    lines.append("")
    lines.extend(case_rag_sections)
    lines.append("")

    # ---- 逻辑质询时间线 ----
    timeline_sections = _build_challenger_timeline_sections(analysis_states, agent_logs)
    lines.append("## 六、逻辑质询时间线")
    lines.append("")
    if timeline_sections:
        lines.extend(timeline_sections)
    else:
        lines.append("- 暂无逻辑质询 Agent 局部质询轮次记录。")
        lines.append("")

    # ---- 全程审计日志 ----
    audit_sections = _build_full_audit_log_sections(agent_logs, analysis_states, audit_logs, limit=REPORT_AUDIT_LOG_LIMIT)
    lines.append("## 七、全程审计日志")
    lines.append("")
    if audit_sections:
        lines.append(f"> 为省篇幅，这里只展示前 {REPORT_AUDIT_LOG_LIMIT} 条日志，完整日志请见审计日志文件。")
        lines.append("")
        lines.extend(audit_sections)
    else:
        lines.append("- 暂无可展示的审计日志。")
    lines.append("")

    # ---- 人机协同 ----
    consultation_sections = _build_consultation_sections(consultation_sessions, consultation_messages, result or {})
    lines.append("## 八、人机协同")
    lines.append("")
    if consultation_sections:
        lines.extend(consultation_sections)
    else:
        lines.append("- 本任务未触发人机协同。")
        lines.append("")

    # ---- 建议 ----
    lines.append("## 九、建议与说明")
    lines.append("")
    if result:
        recommendations = result.get("recommendations", [])
        if recommendations:
            for rec in recommendations:
                lines.append(f"- {rec}")
        else:
            lines.append("- 建议结合多源信息进行人工复核。")
    else:
        lines.append("- 任务尚未完成，暂无建议。")
    lines.append("")

    # ---- 页脚 ----
    lines.append("---")
    lines.append("")
    now_cn = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Shanghai"))
    lines.append(f"*报告生成时间: {now_cn.strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append(f"*TruthSeeker - 跨模态恶意 AIGC 鉴伪与溯源系统*")

    return _normalize_report_agent_terms("\n".join(lines))


async def generate_audit_log_markdown(task_id: str) -> str:
    """Generate a complete audit-log Markdown file for a task."""
    data_or_coro = _fetch_task_data(task_id)
    data = await data_or_coro if inspect.isawaitable(data_or_coro) else data_or_coro
    task = data["task"]
    audit_logs = data.get("audit_logs") or []
    detection_run_id = _resolve_final_detection_run_id(
        task,
        data.get("report"),
        data.get("analysis_states") or [],
        data.get("agent_logs") or [],
        audit_logs,
    )
    analysis_states = data.get("analysis_states") or []
    agent_logs = data.get("agent_logs") or []
    if detection_run_id:
        analysis_states = _filter_rows_by_detection_run_id(analysis_states, detection_run_id)
        agent_logs = _filter_rows_by_detection_run_id(agent_logs, detection_run_id)
        audit_logs = _filter_audit_logs_for_detection_run(audit_logs, detection_run_id)
    entries = _collect_audit_entries(
        agent_logs,
        analysis_states,
        audit_logs,
    )
    lines = [
        "# TruthSeeker 全程审计日志",
        "",
        f"- 任务 ID：`{task.get('id', task_id)}`",
        f"- 标题：{task.get('title', 'N/A')}",
        f"- 日志总数：{len(entries)}",
        "",
        "## 完整日志",
        "",
    ]
    if not entries:
        lines.append("- 暂无可展示的审计日志。")
    else:
        lines.extend(_render_audit_entries(entries, limit=None))
    return "\n".join(lines)


async def generate_audit_log_pdf(task_id: str) -> bytes:
    """Generate the complete audit log as a PDF file."""
    md_content = await generate_audit_log_markdown(task_id)
    return _render_markdown_pdf_with_fpdf_or_pillow(md_content)


# ---------------------------------------------------------------------------
# PDF 报告
# ---------------------------------------------------------------------------

async def generate_pdf_report(task_id: str) -> bytes:
    """生成 PDF 格式的鉴伪与溯源分析报告"""
    md_content = await generate_markdown_report(task_id)
    return _render_markdown_pdf_with_fpdf_or_pillow(md_content)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _fmt_time(value: Optional[str]) -> str:
    """格式化时间戳为北京时间"""
    if not value:
        return "N/A"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        dt_cn = dt.astimezone(ZoneInfo("Asia/Shanghai"))
        return dt_cn.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return str(value)


def _fmt_confidence(value) -> str:
    """格式化置信度"""
    if isinstance(value, (int, float)):
        return f"{value:.1%}"
    return str(value)


def _metadata_detection_run_id(value) -> str | None:
    metadata = _as_dict(value)
    run_id = metadata.get("detection_run_id")
    return str(run_id) if run_id else None


def _row_detection_run_id(row: dict) -> str | None:
    if not isinstance(row, dict):
        return None
    direct = row.get("detection_run_id")
    if direct:
        return str(direct)
    metadata_id = _metadata_detection_run_id(row.get("metadata"))
    if metadata_id:
        return metadata_id
    snapshot = _as_dict(row.get("result_snapshot"))
    snapshot_id = snapshot.get("detection_run_id")
    if snapshot_id:
        return str(snapshot_id)
    final_verdict = _as_dict(snapshot.get("final_verdict"))
    verdict_run_id = final_verdict.get("detection_run_id")
    if verdict_run_id:
        return str(verdict_run_id)
    board = _as_dict(row.get("evidence_board"))
    board_run_id = board.get("detection_run_id")
    if board_run_id:
        return str(board_run_id)
    payload = _as_dict(row.get("verdict_payload"))
    payload_run_id = payload.get("detection_run_id")
    if payload_run_id:
        return str(payload_run_id)
    result = _as_dict(row.get("result"))
    result_run_id = result.get("detection_run_id")
    return str(result_run_id) if result_run_id else None


def _resolve_final_detection_run_id(
    task: dict,
    report: dict | None,
    analysis_states: list,
    agent_logs: list,
    audit_logs: list,
) -> str | None:
    report_run_id = _row_detection_run_id(report or {})
    if report_run_id:
        return report_run_id

    task_result = _as_dict(task.get("result"))
    task_result_id = task_result.get("detection_run_id")
    if task_result_id:
        return str(task_result_id)

    metadata = _as_dict(task.get("metadata"))
    metadata_run_id = metadata.get("last_detection_run_id") or metadata.get("active_detection_run_id")
    if metadata_run_id:
        return str(metadata_run_id)

    for row in reversed(analysis_states):
        run_id = _row_detection_run_id(row)
        snapshot = _as_dict(row.get("result_snapshot") if isinstance(row, dict) else None)
        if run_id and _as_dict(snapshot.get("final_verdict")).get("verdict"):
            return run_id

    for row in reversed(audit_logs):
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "")
        if action in {"detect_completed", "report_generated"}:
            run_id = _row_detection_run_id(row)
            if run_id:
                return run_id

    for row in reversed(agent_logs):
        run_id = _row_detection_run_id(row)
        if run_id:
            return run_id
    return None


def _filter_rows_by_detection_run_id(rows: list, detection_run_id: str) -> list:
    if not detection_run_id:
        return rows
    row_run_ids = [_row_detection_run_id(row) for row in rows if isinstance(row, dict)]
    if not any(row_run_ids):
        return rows
    return [
        row for row in rows
        if isinstance(row, dict) and _row_detection_run_id(row) == detection_run_id
    ]


def _row_time(row: dict) -> datetime:
    if not isinstance(row, dict):
        return datetime.min.replace(tzinfo=timezone.utc)
    return _parse_timeline_time(
        row.get("created_at")
        or row.get("timestamp")
        or row.get("updated_at")
        or row.get("generated_at")
    )


def _filter_audit_logs_for_detection_run(audit_logs: list, detection_run_id: str) -> list:
    if not detection_run_id:
        return audit_logs
    explicit_ids = [_row_detection_run_id(row) for row in audit_logs if isinstance(row, dict)]
    if not any(explicit_ids):
        return audit_logs

    matching = [
        row for row in audit_logs
        if isinstance(row, dict) and _row_detection_run_id(row) == detection_run_id
    ]
    starts = [
        row for row in matching
        if str(row.get("action") or "") == "detect_start"
    ]
    terminals = [
        row for row in matching
        if str(row.get("action") or "") in {
            "detect_completed",
            "detect_failed",
            "detect_cancelled",
            "report_generated",
        }
    ]
    if not starts:
        return matching

    start_time = min(_row_time(row) for row in starts)
    end_time = max((_row_time(row) for row in terminals), default=datetime.max.replace(tzinfo=timezone.utc))
    filtered: list = []
    for row in audit_logs:
        if not isinstance(row, dict):
            continue
        row_run_id = _row_detection_run_id(row)
        if row_run_id:
            if row_run_id == detection_run_id:
                filtered.append(row)
            continue
        row_time = _row_time(row)
        if start_time <= row_time <= end_time:
            filtered.append(row)
    return filtered


def _agent_display_name(agent_name: str) -> str:
    return AGENT_DISPLAY_NAMES.get(agent_name, agent_name)


def _normalize_report_agent_terms(markdown: str) -> str:
    replacements = [
        (r"Forensics\s*电子取证", _agent_display_name("forensics")),
        (r"Forensics\s*取证", _agent_display_name("forensics")),
        (r"Forensics\s*Agent", _agent_display_name("forensics")),
        (r"\bForensics\b", _agent_display_name("forensics")),
        (r"OSINT\s*开源情报溯源", _agent_display_name("osint")),
        (r"OSINT\s*情报", _agent_display_name("osint")),
        (r"OSINT\s*Agent", _agent_display_name("osint")),
        (r"\bOSINT\b", _agent_display_name("osint")),
        (r"法医分析", f"{_agent_display_name('forensics')} 分析"),
        (r"法医", "电子取证"),
    ]
    normalized = markdown
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def _extract_agent_result(analysis_states: list, agent_name: str) -> Optional[dict]:
    """从 analysis_states 中提取指定 agent 的结果"""
    for state in reversed(analysis_states):
        result_snapshot = state.get("result_snapshot") or {}
        if result_snapshot.get(agent_name):
            return result_snapshot[agent_name]
        if state.get("agent_name") == agent_name or state.get("agent") == agent_name:
            return state.get("result") or state.get("data")
    return None


def _derive_osint_result_from_final_verdict(result: dict | None) -> Optional[dict]:
    """Use final verdict OSINT context when the dedicated agent snapshot is missing."""
    if not isinstance(result, dict):
        return None

    osint_summary = result.get("osint_summary")
    provenance_graph = result.get("provenance_graph")
    provenance_summary = result.get("provenance_summary")
    has_fallback_data = any(
        isinstance(value, dict) and bool(value)
        for value in (osint_summary, provenance_graph, provenance_summary)
    )
    if not has_fallback_data:
        return None

    fallback: dict = {
        "analysis_source": "final_verdict_summary",
        "note": "未找到独立 OSINT Agent 持久化明细，本节由最终裁决中的 OSINT 摘要与溯源图谱回填。",
    }
    if isinstance(osint_summary, dict):
        fallback.update(osint_summary)
    if isinstance(provenance_summary, dict):
        fallback["provenance_summary"] = provenance_summary
    if isinstance(provenance_graph, dict):
        fallback["provenance_graph"] = provenance_graph
    return fallback


def _maybe_fmt_time(value) -> str:
    """如果值像 ISO 8601 时间戳，则转为北京时间；否则原样返回。"""
    if not isinstance(value, str):
        return str(value)
    # 匹配常见 ISO 8601 格式，如 2026-04-22T10:29:49.349138+00:00
    import re
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", value):
        return _fmt_time(value)
    return value


def _truncate_text(value: str, limit: int = MAX_REPORT_FIELD_CHARS) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _render_tool_results(items: list, indent: int = 0) -> str:
    prefix = "  " * indent
    lines: list[str] = []
    for item in items[:12]:
        if not isinstance(item, dict):
            lines.append(f"{prefix}- {_truncate_text(str(item), 240)}")
            continue
        tool = item.get("tool", "unknown")
        target = item.get("target", "")
        status = item.get("status", "unknown")
        degraded = item.get("degraded", False)
        summary = item.get("summary") or item.get("error") or ""
        line = f"{prefix}- {tool} [{status}]"
        if degraded:
            line += "（降级）"
        if target:
            line += f" — {target}"
        if summary:
            line += f": {_truncate_text(str(summary), 260)}"
        lines.append(line)
    if len(items) > 12:
        lines.append(f"{prefix}- ... 及其他 {len(items) - 12} 条工具记录")
    return "\n".join(lines)


def _render_search_results(items: list, indent: int = 0) -> str:
    prefix = "  " * indent
    lines: list[str] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        title = _truncate_text(str(item.get("title") or item.get("url") or "搜索结果"), 120)
        url = item.get("url")
        query = item.get("query")
        summary = _truncate_text(str(item.get("summary") or ""), MAX_SEARCH_SUMMARY_CHARS)
        lines.append(f"{prefix}- **{title}**")
        if url:
            lines.append(f"{prefix}  - URL: {url}")
        if query:
            lines.append(f"{prefix}  - 查询: {_truncate_text(str(query), 160)}")
        if summary:
            lines.append(f"{prefix}  - 摘要: {summary}")
    if len(items) > 5:
        lines.append(f"{prefix}- ... 及其他 {len(items) - 5} 条搜索结果")
    return "\n".join(lines)


def _render_provenance_graph_summary(graph: dict, indent: int = 0) -> str:
    prefix = "  " * indent
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    citations = graph.get("citations") or []
    quality = graph.get("quality") or {}
    lines = [
        f"{prefix}- 节点数: {len(nodes)}",
        f"{prefix}- 边数: {len(edges)}",
        f"{prefix}- 引用数: {len(citations)}",
    ]
    if quality:
        lines.append(
            f"{prefix}- 图谱质量: completeness={quality.get('completeness', 'N/A')}, "
            f"citation_coverage={quality.get('citation_coverage', 'N/A')}, "
            f"model_inferred_ratio={quality.get('model_inferred_ratio', 'N/A')}"
        )
    return "\n".join(lines)


def _build_consultation_sections(sessions: list, messages: list, result: dict) -> list[str]:
    if not sessions and not result.get("consultation_summary"):
        return []
    lines: list[str] = []
    for index, session in enumerate(sessions, start=1):
        if not isinstance(session, dict):
            continue
        lines.append(f"### 协同轮次 {index}")
        lines.append("")
        lines.append(f"- **状态**: {session.get('status', 'unknown')}")
        if session.get("triggered_by_agent"):
            lines.append(f"- **触发对象**: {session.get('triggered_by_agent')}")
        if session.get("reason"):
            lines.append(f"- **触发原因**: {session.get('reason')}")
        summary = session.get("summary_payload") if isinstance(session.get("summary_payload"), dict) else {}
        confirmed = summary.get("confirmed_summary")
        if confirmed:
            lines.append(f"- **用户确认摘要**: {confirmed}")
        quotes = summary.get("key_quotes") if isinstance(summary.get("key_quotes"), list) else []
        if quotes:
            lines.append("- **关键意见摘录**:")
            for quote in quotes[:5]:
                if not isinstance(quote, dict):
                    continue
                role = quote.get("role", "participant")
                message = _truncate_text(str(quote.get("message") or ""), 240)
                lines.append(f"  - {role}: {message}")
        related_messages = [
            item for item in messages
            if isinstance(item, dict) and item.get("session_id") == session.get("id")
        ]
        related_messages = filter_human_consultation_messages(related_messages)
        if related_messages and not quotes:
            lines.append("- **关键意见摘录**:")
            for item in related_messages[:5]:
                role = item.get("role", "participant")
                lines.append(f"  - {role}: {_truncate_text(str(item.get('message') or ''), 240)}")
        lines.append("")
    consultation_summary = result.get("consultation_summary")
    if isinstance(consultation_summary, dict) and consultation_summary.get("confirmed_summary"):
        lines.append("### 对最终研判的影响")
        lines.append("")
        lines.append(f"- {consultation_summary.get('confirmed_summary')}")
        lines.append("")
    return lines


def _render_markdown_field(key: str, value: str, indent: int = 0) -> str:
    """Render LLM Markdown fields without collapsing paragraphs into one bullet."""
    label = MARKDOWN_REPORT_FIELDS.get(key, key)
    text = (value or "").strip()
    if len(text) > 5000:
        text = text[:4999].rstrip() + "\n\n..."
    prefix = "  " * indent
    if indent == 0:
        return "\n".join([f"### {label}", "", text])

    lines = [f"{prefix}- **{label}**:"]
    for raw_line in text.splitlines():
        lines.append(f"{prefix}  {raw_line}" if raw_line else "")
    return "\n".join(lines)


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _parse_timeline_time(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _safe_metadata_summary(metadata) -> str:
    record = _as_dict(metadata)
    if not record:
        return ""
    parts: list[str] = []
    for key, value in record.items():
        key_text = str(key)
        lowered = key_text.lower()
        if any(secret in lowered for secret in ("token", "secret", "password", "authorization", "signed_url")):
            continue
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, default=str)
        else:
            rendered = str(value)
        parts.append(f"{key_text}={_truncate_text(rendered, 90)}")
        if len(parts) >= 4:
            break
    return "，".join(parts)


def _collect_audit_entries(agent_logs: list, analysis_states: list, audit_logs: list) -> list[dict]:
    """Merge agent logs, persisted timeline events, and audit_logs into one chronological audit trail."""
    entries: list[dict] = []
    for log in agent_logs:
        if not isinstance(log, dict):
            continue
        timestamp = log.get("timestamp") or log.get("created_at")
        entries.append({
            "timestamp": timestamp,
            "source": "Agent 日志",
            "agent": log.get("agent", log.get("agent_name", "unknown")),
            "kind": log.get("type", log.get("log_type", "info")),
            "content": str(log.get("content") or ""),
        })

    for state in analysis_states:
        if not isinstance(state, dict):
            continue
        board = _as_dict(state.get("evidence_board"))
        for event in _as_list(board.get("timeline_events")):
            if not isinstance(event, dict):
                continue
            timestamp = event.get("timestamp") or state.get("created_at")
            entries.append({
                "timestamp": timestamp,
                "source": "阶段事件",
                "agent": event.get("agent", state.get("agent_name", "system")),
                "kind": event.get("event_type", "timeline"),
                "content": event.get("summary") or event.get("content") or "",
            })

    for row in audit_logs:
        if not isinstance(row, dict):
            continue
        metadata_summary = _safe_metadata_summary(row.get("metadata"))
        action = str(row.get("action") or "audit")
        content = action if not metadata_summary else f"{action}（{metadata_summary}）"
        entries.append({
            "timestamp": row.get("created_at") or row.get("timestamp"),
            "source": "系统审计",
            "agent": row.get("agent") or row.get("actor_role") or "system",
            "kind": action,
            "content": content,
        })

    entries = [
        entry for entry in entries
        if str(entry.get("content") or "").strip()
    ]
    entries.sort(key=lambda item: _parse_timeline_time(item.get("timestamp")))
    return entries


def _render_audit_entries(entries: list[dict], *, limit: int | None) -> list[str]:
    lines: list[str] = []
    rendered_entries = entries if limit is None else entries[:limit]
    for entry in rendered_entries:
        ts = _fmt_time(entry.get("timestamp"))
        agent = entry.get("agent") or "system"
        source = entry.get("source") or "日志"
        kind = entry.get("kind") or "info"
        content = _truncate_text(str(entry.get("content") or ""), 320)
        lines.append(f"- **[{ts}] {source} / {agent}** ({kind}): {content}")
    if limit is not None and len(entries) > limit:
        lines.append(f"- ... 及其他 {len(entries) - limit} 条审计记录")
    return lines


def _build_full_audit_log_sections(agent_logs: list, analysis_states: list, audit_logs: list, *, limit: int = REPORT_AUDIT_LOG_LIMIT) -> list[str]:
    entries = _collect_audit_entries(agent_logs, analysis_states, audit_logs)
    return _render_audit_entries(entries, limit=limit)


def _dict_to_markdown(data: dict, indent: int = 0) -> str:
    """将字典递归转为 Markdown 列表，自动把 ISO 时间戳转为北京时间"""
    lines = []
    prefix = "  " * indent
    for key, value in data.items():
        if key in SKIP_REPORT_KEYS:
            continue
        if key in MARKDOWN_REPORT_FIELDS and isinstance(value, str):
            lines.append(_render_markdown_field(key, value, indent))
            continue
        if key == "tool_results" and isinstance(value, list):
            lines.append(f"{prefix}- **{key}**:")
            lines.append(_render_tool_results(value, indent + 1))
            continue
        if key == "search_results" and isinstance(value, list):
            lines.append(f"{prefix}- **{key}**:")
            lines.append(_render_search_results(value, indent + 1))
            continue
        if key == "provenance_graph" and isinstance(value, dict):
            lines.append(f"{prefix}- **{key}**:")
            lines.append(_render_provenance_graph_summary(value, indent + 1))
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}- **{key}**:")
            lines.append(_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}- **{key}**:")
            for item in value[:12]:
                if isinstance(item, dict):
                    lines.append(_dict_to_markdown(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {_truncate_text(_maybe_fmt_time(item), 360)}")
            if len(value) > 12:
                lines.append(f"{prefix}  - ... 及其他 {len(value) - 12} 项")
        else:
            rendered = _maybe_fmt_time(value)
            if isinstance(rendered, str):
                rendered = _truncate_text(rendered)
            lines.append(f"{prefix}- **{key}**: {rendered}")
    return "\n".join(lines)


def _render_rag_result(result: dict | None, *, hit_label: str, miss_label: str, degraded_label: str) -> list[str]:
    lines: list[str] = []
    if not result:
        lines.append(f"- 未记录{hit_label}调用。")
        return lines
    status = result.get("status", "unknown")
    summary = result.get("summary") or "无摘要"
    matches = [item for item in (result.get("matches") or []) if isinstance(item, dict)]
    lines.append(f"- 调用状态：{status}")
    lines.append(f"- 调用摘要：{summary}")
    if result.get("degraded"):
        lines.append(f"- 影响说明：{degraded_label}")
    if not matches:
        lines.append(f"- {miss_label}")
        return lines

    lines.append(f"- {hit_label}：")
    groups: dict[str, list[dict]] = {}
    for item in matches:
        title = item.get("title") or item.get("case_id") or item.get("entry_id") or "未命名条目"
        groups.setdefault(str(title), []).append(item)
    for title, chunks in list(groups.items())[:5]:
        best_score = max(
            (c.get("score", c.get("similarity")) for c in chunks if isinstance(c.get("score", c.get("similarity")), (int, float))),
            default=None,
        )
        score_text = f"{float(best_score):.2f}" if best_score is not None else "N/A"
        source_kind = chunks[0].get("source_kind") or chunks[0].get("target_agent") or "rag"
        lines.append(f"  - **{title}**（{source_kind}，最高相似度 {score_text}，共 {len(chunks)} 个片段）")
        for chunk in chunks[:4]:
            snippet = str(chunk.get("snippet") or chunk.get("chunk_text") or chunk.get("summary") or "").strip()
            chunk_score = chunk.get("score", chunk.get("similarity"))
            chunk_score_text = f"{float(chunk_score):.2f}" if isinstance(chunk_score, (int, float)) else "N/A"
            if snippet:
                lines.append(f"    - 片段（相似度 {chunk_score_text}）：{snippet[:200]}")
        if len(chunks) > 4:
            lines.append(f"    - ... 及其他 {len(chunks) - 4} 个片段")
    if len(groups) > 5:
        lines.append(f"  - ... 及其他 {len(groups) - 5} 个条目")
    return lines


def _build_case_rag_sections(
    forensics_case_rag: dict | None,
    forensics_experience_rag: dict | None,
    osint_case_rag: dict | None,
    osint_experience_rag: dict | None,
    challenger_experience_rag: dict | None,
) -> list[str]:
    sections = [
        "> 公开案例 RAG 与个人经验 RAG 均用于提示相似手法、复核路径和补证方向；不得替代当前检材、外部工具结果或人工判断。",
        "",
    ]
    items = [
        (_agent_display_name("forensics"), forensics_case_rag, forensics_experience_rag, True),
        (_agent_display_name("osint"), osint_case_rag, osint_experience_rag, True),
        (_agent_display_name("challenger"), None, challenger_experience_rag, False),
    ]
    rendered_any = False
    for label, case_result, experience_result, has_case_rag in items:
        sections.append(f"### {label}")
        if has_case_rag:
            sections.extend(_render_rag_result(
                case_result,
                hit_label="命中案例",
                miss_label="未命中相似公开案例。",
                degraded_label="公开案例 RAG 不可用，不影响当前检材的独立鉴伪与溯源流程。",
            ))
        else:
            sections.append("- 未配置公开案例 RAG 工具。")
        sections.extend(_render_rag_result(
            experience_result,
            hit_label="命中经验",
            miss_label="未命中可复用个人经验。",
            degraded_label="个人经验 RAG 不可用，不影响当前检材的独立鉴伪与溯源流程。",
        ))
        rendered_any = rendered_any or bool(case_result or experience_result)
        sections.append("- 边界说明：以上命中只提示可复核方向，不能替代当前样本证据、外部工具结果或人工判断。")
        sections.append("")
    if not rendered_any:
        sections.append("- 本任务未启用或未记录公开案例/个人经验 RAG。")
    return sections


def _build_challenger_timeline_sections(analysis_states: list, agent_logs: list) -> list[str]:
    """Build timeline grouped by Challenger's phase-specific review rounds."""
    phase_names = {
        "forensics": _agent_display_name("forensics"),
        "osint": _agent_display_name("osint"),
        "commander": _agent_display_name("commander"),
    }
    sections: list[str] = []
    seen: set[tuple[str, int, str]] = set()

    def _action_label(feedback: dict) -> str:
        action = str(feedback.get("next_action") or "").strip()
        if action == "return_for_reinforcement" or feedback.get("requires_more_evidence"):
            return "打回"
        if action == "max_rounds_release" or feedback.get("max_rounds_release"):
            return "轮次上限放行"
        if action == "release_after_collaboration" or feedback.get("collaboration_release"):
            return "人机协同后放行"
        if feedback.get("consultation_required") or feedback.get("collaboration_required"):
            return "启动人机协同"
        return "放行"

    def _collaboration_label(feedback: dict) -> str:
        required = feedback.get("collaboration_required", feedback.get("consultation_required"))
        event_type = feedback.get("collaboration_event_type") or feedback.get("consultation_event_type")
        if required:
            return f"是（{event_type or 'collaboration_required'}）"
        return "否"

    for state in analysis_states:
        snapshot = state.get("result_snapshot") or {}
        feedback = snapshot.get("challenger")
        if not isinstance(feedback, dict):
            continue
        phase = str(feedback.get("phase") or "unknown")
        phase_round = int(feedback.get("phase_round") or state.get("round_number") or 1)
        timestamp = _fmt_time(feedback.get("timestamp") or state.get("created_at"))
        key = (phase, phase_round, timestamp)
        if key in seen:
            continue
        seen.add(key)
        label = phase_names.get(phase, phase)
        action_label = _action_label(feedback)
        action_reason = (
            feedback.get("action_reason")
            or feedback.get("convergence_reason")
            or ("需要补充证据" if feedback.get("requires_more_evidence") else "进入下一阶段")
        )
        sections.append(f"### 逻辑质询Agent ↔ {label} 第 {phase_round} 轮")
        sections.append("")
        sections.append(f"- 时间: {timestamp}")
        sections.append(f"- 质询对象: {label}")
        sections.append(f"- 置信度/质量分: {_fmt_confidence(feedback.get('confidence', feedback.get('quality_score', 'N/A')))}")
        if feedback.get("quality_delta") is not None:
            sections.append(f"- 置信度变化 Δ(t): {float(feedback.get('quality_delta')):.3f}")
        sections.append(f"- 下一步行动: {action_label}")
        sections.append(f"- 是否启动人机协同: {_collaboration_label(feedback)}")
        sections.append(f"- 问题数: {feedback.get('issue_count', 0)}（高严重度 {feedback.get('high_severity_count', 0)}）")
        sections.append(f"- 放行/打回说明: {action_reason}")
        if feedback.get("max_rounds_release"):
            sections.append("- 特殊标记: 轮次上限放行，残留风险已进入最终报告。")
        issues = feedback.get("issues_found") or []
        if issues:
            sections.append("- 发现的问题:")
        for issue in issues[:3]:
            if isinstance(issue, dict):
                sections.append(
                    f"  - {issue.get('severity', 'unknown')}: "
                    f"{_truncate_text(str(issue.get('description') or issue.get('type') or ''), 220)}"
                )
        sections.append("")

    if sections:
        return sections

    # Backward-compatible fallback for old rows that only have agent_logs.
    for log in agent_logs:
        content = str(log.get("content", ""))
        match = re.search(r"phase=(\w+), phase_round=(\d+)", content)
        if not match:
            continue
        phase, phase_round = match.group(1), int(match.group(2))
        label = phase_names.get(phase, phase)
        sections.append(f"### 逻辑质询Agent ↔ {label} 第 {phase_round} 轮")
        sections.append("")
        sections.append(f"- 时间: {_fmt_time(log.get('timestamp', log.get('created_at')))}")
        sections.append(f"- 质询对象: {label}")
        sections.append(f"- 质询结论: {_truncate_text(content, 260)}")
        sections.append("")
    return sections


def _group_logs_by_round(logs: list) -> dict:
    """按轮次分组 agent_logs"""
    grouped: dict[int, list] = {}
    for log in logs:
        round_num = log.get("round", log.get("round_number", 0))
        grouped.setdefault(round_num, []).append(log)
    return dict(sorted(grouped.items()))


PDF_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/PingFang.ttc",
]


def _find_pdf_font_path() -> str | None:
    for path in PDF_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _load_pdf_font(size: int):
    from PIL import ImageFont

    for path in PDF_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render_markdown_pdf_with_fpdf_or_pillow(markdown_content: str) -> bytes:
    try:
        return _render_markdown_pdf_with_fpdf(markdown_content)
    except Exception as exc:
        logger.warning("Text PDF generation failed, using Pillow PDF fallback: %s", exc)
        try:
            return _render_markdown_pdf_with_pillow(markdown_content)
        except Exception as fallback_exc:
            logger.error("Pillow PDF fallback failed: %s", fallback_exc)
            raise HTTPException(status_code=500, detail="PDF 生成失败")


def _render_markdown_pdf_with_fpdf(markdown_content: str) -> bytes:
    from fpdf import FPDF

    font_path = _find_pdf_font_path()
    if not font_path:
        raise RuntimeError("No usable PDF font found")

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(left=16, top=16, right=16)
    pdf.add_page()
    pdf.add_font("TruthSeeker", "", font_path)

    text_width = pdf.w - pdf.l_margin - pdf.r_margin

    def add_line(text: str, level: int) -> None:
        style = _fpdf_text_style(level, text)
        pdf.set_font("TruthSeeker", size=style["size"])
        pdf.set_text_color(*style["color"])
        if style["before"]:
            pdf.ln(style["before"])
        for wrapped in _wrap_fpdf_text_for_width(text, pdf, text_width):
            pdf.cell(w=text_width, h=style["height"], text=wrapped, new_x="LMARGIN", new_y="NEXT")
        if style["rule"]:
            y = pdf.get_y() + 1
            pdf.set_draw_color(*style["rule_color"])
            pdf.set_line_width(0.25)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)
        elif style["after"]:
            pdf.ln(style["after"])

    for raw_line in markdown_content.splitlines():
        text, level = _display_markdown_line(raw_line)
        if not text:
            pdf.ln(3)
            continue
        add_line(text, level)

    return bytes(pdf.output())


def _fpdf_text_style(level: int, text: str) -> dict:
    body_color = (17, 24, 39)
    if level == 1:
        return {
            "size": 17,
            "height": 9,
            "color": (15, 59, 95),
            "before": 1,
            "after": 0,
            "rule": True,
            "rule_color": (37, 99, 135),
        }
    if level == 2:
        return {
            "size": 14,
            "height": 8,
            "color": (15, 59, 95),
            "before": 3,
            "after": 1,
            "rule": False,
            "rule_color": (37, 99, 135),
        }
    if level == 3:
        return {
            "size": 12,
            "height": 7,
            "color": (31, 95, 133),
            "before": 2,
            "after": 1,
            "rule": False,
            "rule_color": (37, 99, 135),
        }
    warning_markers = ("注意", "降级", "失败", "错误", "风险")
    if any(marker in text for marker in warning_markers):
        color = (146, 64, 14)
    else:
        color = body_color
    return {
        "size": 10.5,
        "height": 6,
        "color": color,
        "before": 0,
        "after": 0,
        "rule": False,
        "rule_color": (37, 99, 135),
    }


def _wrap_fpdf_text_for_width(text: str, pdf, max_width: float) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    current = ""
    for char in text:
        candidate = f"{current}{char}"
        if current and pdf.get_string_width(candidate) > max_width:
            lines.append(current.rstrip())
            current = char.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return lines or [""]


def _wrap_text_for_width(text: str, font, max_width: int, draw) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = f"{current}{char}"
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _render_markdown_pdf_with_pillow(markdown_content: str) -> bytes:
    from PIL import Image, ImageDraw

    width, height = 1240, 1754  # A4 at roughly 150 DPI
    margin_x = 90
    margin_y = 88
    body_font = _load_pdf_font(24)
    h1_font = _load_pdf_font(40)
    h2_font = _load_pdf_font(32)
    h3_font = _load_pdf_font(28)
    fonts = {0: body_font, 1: h1_font, 2: h2_font, 3: h3_font}

    pages: list[Image.Image] = []
    page = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(page)
    y = margin_y

    def new_page() -> None:
        nonlocal page, draw, y
        pages.append(page)
        page = Image.new("RGB", (width, height), "#ffffff")
        draw = ImageDraw.Draw(page)
        y = margin_y

    def add_text(text: str, level: int) -> None:
        nonlocal y
        font = fonts.get(level, body_font)
        fill = "#111827" if level == 0 else "#0f3b5f"
        line_height = 34 if level == 0 else 48
        spacing = 10 if level == 0 else 18
        for wrapped in _wrap_text_for_width(text, font, width - margin_x * 2, draw):
            if y + line_height > height - margin_y:
                new_page()
            draw.text((margin_x, y), wrapped, font=font, fill=fill)
            y += line_height
        y += spacing

    for raw_line in markdown_content.splitlines():
        text, level = _display_markdown_line(raw_line)
        if not text:
            y += 20
            if y > height - margin_y:
                new_page()
            continue
        add_text(text, level)

    pages.append(page)
    output = io.BytesIO()
    first, rest = pages[0], pages[1:]
    first.save(output, format="PDF", save_all=True, append_images=rest, resolution=150.0)
    return output.getvalue()


def _resolve_final_result(task: dict, report: dict | None) -> Optional[dict]:
    if report and isinstance(report.get("verdict_payload"), dict):
        return normalize_final_verdict(report["verdict_payload"])
    task_result = task.get("result")
    if isinstance(task_result, dict):
        return normalize_final_verdict(task_result)
    return None


def _clean_markdown_markup(text: str) -> str:
    """移除 Markdown 标记符号，用于纯文本 / Pillow PDF fallback 渲染"""
    # 粗体 **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 斜体 *text*（确保不处理已被替换的或连续 *）
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    # 行内代码 `text`
    text = re.sub(r"`(.+?)`", r"\1", text)
    # 链接 [text](url) -> text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = text.replace("⚠️", "注意").replace("⚠", "注意")
    text = text.replace("↔", "<->").replace("Δ", "Delta")
    return text


def _display_markdown_line(line: str) -> tuple[str, int]:
    stripped = line.strip()
    if not stripped:
        return "", 0
    if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", stripped):
        return "", 0
    if stripped.startswith("#"):
        level = len(stripped) - len(stripped.lstrip("#"))
        text = _clean_markdown_markup(stripped[level:].strip())
        return text, min(level, 3)
    if stripped.startswith("|"):
        text = stripped.replace("|", "  ")
        text = _clean_markdown_markup(text)
        return text, 0
    # 移除列表与引用标记
    if stripped.startswith("- "):
        stripped = stripped[2:]
    elif stripped.startswith("* "):
        stripped = stripped[2:]
    elif stripped.startswith("> "):
        stripped = stripped[2:]
    text = _clean_markdown_markup(stripped)
    return text, 0
