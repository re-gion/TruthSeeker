"""报告生成服务 — Markdown + PDF 报告"""
import asyncio
import importlib
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.services.analysis_persistence import normalize_final_verdict
from app.services.consultation_workflow import filter_human_consultation_messages
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

MAX_REPORT_FIELD_CHARS = 1200
MAX_SEARCH_SUMMARY_CHARS = 280
SKIP_REPORT_KEYS = {"signed_url", "raw_response"}
MARKDOWN_REPORT_FIELDS = {
    "llm_analysis": "LLM 分析",
    "llm_cross_validation": "LLM 逻辑质询",
    "llm_ruling": "LLM 最终研判",
}


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

async def _fetch_task_data(task_id: str) -> dict:
    """从 Supabase 获取任务的完整数据。"""
    return await asyncio.to_thread(_sync_fetch_task_data, task_id)


def _sync_fetch_task_data(task_id: str) -> dict:
    """同步获取任务数据（在线程池中执行）"""
    # 1. 任务基本信息
    task_resp = supabase.table("tasks").select("*").eq("id", task_id).execute()
    if not task_resp.data:
        raise ValueError(f"Task not found: {task_id}")
    task = task_resp.data[0]

    # 2. 分析状态
    analysis_resp = (
        supabase.table("analysis_states")
        .select("*")
        .eq("task_id", task_id)
        .execute()
    )
    analysis_states = analysis_resp.data or []

    # 3. Agent 日志
    logs_resp = (
        supabase.table("agent_logs")
        .select("*")
        .eq("task_id", task_id)
        .order("timestamp", desc=False)
        .execute()
    )
    agent_logs = logs_resp.data or []

    audit_resp = (
        supabase.table("audit_logs")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=False)
        .execute()
    )
    audit_logs = audit_resp.data or []

    sessions_resp = (
        supabase.table("consultation_sessions")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=False)
        .execute()
    )
    consultation_sessions = sessions_resp.data or []

    messages_resp = (
        supabase.table("consultation_messages")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=False)
        .execute()
    )
    consultation_messages = messages_resp.data or []

    report_resp = (
        supabase.table("reports")
        .select("*")
        .eq("task_id", task_id)
        .order("generated_at", desc=True)
        .execute()
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

    lines: list[str] = []

    # ---- 标题 ----
    lines.append("# TruthSeeker 鉴伪与溯源分析报告")
    lines.append("")

    # ---- 任务信息 ----
    lines.append("## 一、任务信息")
    lines.append("")
    lines.append(f"| 项目 | 内容 |")
    lines.append(f"|------|------|")
    lines.append(f"| 任务 ID | `{task.get('id', 'N/A')}` |")
    lines.append(f"| 标题 | {task.get('title', 'N/A')} |")
    lines.append(f"| 输入类型 | {task.get('input_type', 'N/A')} |")
    lines.append(f"| 状态 | {task.get('status', 'N/A')} |")
    lines.append(f"| 创建时间 | {_fmt_time(task.get('created_at'))} |")
    lines.append(f"| 更新时间 | {_fmt_time(task.get('updated_at'))} |")
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
    osint = _extract_agent_result(analysis_states, "osint")
    degraded_items: list[str] = []
    tool_failures: list[str] = []

    def _collect_tool_failures(agent_result: dict | None) -> None:
        if not agent_result:
            return
        tool_results = agent_result.get("tool_results") or agent_result.get("tool_matrix") or []
        for item in tool_results:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if status in ("degraded", "failed"):
                tool_name = item.get("tool", "unknown")
                target = item.get("target", "")
                error = item.get("error", "")
                summary = item.get("summary", "")
                detail = f"{tool_name} ({target})"
                if error:
                    detail += f" — 错误: {error}"
                elif summary:
                    detail += f" — {summary}"
                tool_failures.append(detail)

    if forensics and forensics.get("degraded"):
        tool_summary = forensics.get("tool_summary") or {}
        degraded_items.append(
            f"Forensics 取证降级（成功 {tool_summary.get('success', '?')}/{tool_summary.get('total', '?')}，"
            f"降级 {tool_summary.get('degraded', 0)}，失败 {tool_summary.get('failed', 0)}）"
        )
        _collect_tool_failures(forensics)
    if osint and osint.get("degraded"):
        tool_summary = osint.get("tool_summary") or {}
        degraded_items.append(
            f"OSINT 情报降级（成功 {tool_summary.get('success', '?')}/{tool_summary.get('total', '?')}，"
            f"降级 {tool_summary.get('degraded', 0)}，失败 {tool_summary.get('failed', 0)}）"
        )
        _collect_tool_failures(osint)
    if result:
        forensics_degraded = (result.get("forensics_summary") or {}).get("degraded")
        osint_degraded = (result.get("osint_summary") or {}).get("degraded")
        if forensics_degraded and not forensics:
            degraded_items.append("Forensics 取证降级（详情见分析状态）")
        if osint_degraded and not osint:
            degraded_items.append("OSINT 情报降级（详情见分析状态）")
    if degraded_items:
        lines.append("## ⚠️ 降级状态汇总")
        lines.append("")
        for item in degraded_items:
            lines.append(f"- {item}")
        if tool_failures:
            lines.append("")
            lines.append("**具体工具失败详情**:")
            for detail in tool_failures[:10]:
                lines.append(f"  - {detail}")
            if len(tool_failures) > 10:
                lines.append(f"  - ... 及其他 {len(tool_failures) - 10} 个工具失败")
        lines.append("")
        lines.append("> **注意**: 降级模式下部分结果基于启发式模拟或本地推理，可靠性低于完整外部检测。"
                    "建议在网络恢复或服务正常后重新检测。")
        lines.append("")

    # ---- Forensics 分析 ----
    if forensics:
        lines.append("## 三、Forensics 取证分析")
        lines.append("")
        lines.extend(_dict_to_markdown(forensics).splitlines())
        lines.append("")

    # ---- OSINT 情报 ----
    if osint:
        lines.append("## 四、OSINT 开源情报")
        lines.append("")
        lines.extend(_dict_to_markdown(osint).splitlines())
        lines.append("")

    # ---- Challenger 逻辑质询 ----
    challenger = _extract_agent_result(analysis_states, "challenger")
    if challenger:
        lines.append("## 五、Challenger 逻辑质询")
        lines.append("")
        lines.extend(_dict_to_markdown(challenger).splitlines())
        lines.append("")

    # ---- 质询时间线 ----
    timeline_sections = _build_challenger_timeline_sections(analysis_states, agent_logs)
    lines.append("## 六、质询时间线")
    lines.append("")
    if timeline_sections:
        lines.extend(timeline_sections)
    else:
        lines.append("- 暂无 Challenger 局部质询轮次记录。")
        lines.append("")

    # ---- 全程审计日志 ----
    audit_sections = _build_full_audit_log_sections(agent_logs, analysis_states, audit_logs)
    lines.append("## 七、全程审计日志")
    lines.append("")
    if audit_sections:
        lines.extend(audit_sections)
    else:
        lines.append("- 暂无可展示的审计日志。")
    lines.append("")

    # ---- 人机协同专家会诊 ----
    consultation_sections = _build_consultation_sections(consultation_sessions, consultation_messages, result or {})
    lines.append("## 八、人机协同专家会诊")
    lines.append("")
    if consultation_sections:
        lines.extend(consultation_sections)
    else:
        lines.append("- 本任务未触发专家会诊。")
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
    lines.append(f"*TruthSeeker - 跨模态 Deepfake 鉴伪与溯源系统*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF 报告
# ---------------------------------------------------------------------------

async def generate_pdf_report(task_id: str) -> bytes:
    """生成 PDF 格式的鉴伪与溯源分析报告"""
    md_content = await generate_markdown_report(task_id)

    # MD -> HTML
    try:
        import markdown as md_lib
        html_body = md_lib.markdown(
            md_content,
            extensions=["tables", "fenced_code", "toc"],
        )
    except ImportError:
        # 极简 fallback
        html_body = f"<pre>{md_content}</pre>"

    html_full = _wrap_html_template(html_body)

    # HTML -> PDF
    try:
        HTML = importlib.import_module("weasyprint").HTML

        pdf_bytes = HTML(string=html_full).write_pdf()
        return pdf_bytes
    except ImportError as exc:
        logger.warning("weasyprint not installed, using Pillow PDF fallback: %s", exc)
        return _render_markdown_pdf_with_pillow(md_content)
    except Exception as e:
        logger.warning("weasyprint PDF generation failed, using Pillow PDF fallback: %s", e)
        try:
            return _render_markdown_pdf_with_pillow(md_content)
        except Exception as fallback_exc:
            logger.error("Pillow PDF fallback failed: %s", fallback_exc)
            raise HTTPException(status_code=500, detail="PDF 生成失败")


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


def _extract_agent_result(analysis_states: list, agent_name: str) -> Optional[dict]:
    """从 analysis_states 中提取指定 agent 的结果"""
    for state in reversed(analysis_states):
        result_snapshot = state.get("result_snapshot") or {}
        if result_snapshot.get(agent_name):
            return result_snapshot[agent_name]
        if state.get("agent_name") == agent_name or state.get("agent") == agent_name:
            return state.get("result") or state.get("data")
    return None


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
        lines.append(f"### 会诊轮次 {index}")
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
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        parts.append(f"{key_text}={_truncate_text(rendered, 90)}")
        if len(parts) >= 4:
            break
    return "，".join(parts)


def _build_full_audit_log_sections(agent_logs: list, analysis_states: list, audit_logs: list) -> list[str]:
    """Merge agent logs, persisted timeline events, and audit_logs into one chronological audit trail."""
    entries: list[dict] = []
    for log in agent_logs:
        timestamp = log.get("timestamp") or log.get("created_at")
        entries.append({
            "timestamp": timestamp,
            "source": "Agent 日志",
            "agent": log.get("agent", log.get("agent_name", "unknown")),
            "kind": log.get("type", log.get("log_type", "info")),
            "content": str(log.get("content") or ""),
        })

    for state in analysis_states:
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

    lines: list[str] = []
    for entry in entries[:80]:
        ts = _fmt_time(entry.get("timestamp"))
        agent = entry.get("agent") or "system"
        source = entry.get("source") or "日志"
        kind = entry.get("kind") or "info"
        content = _truncate_text(str(entry.get("content") or ""), 320)
        lines.append(f"- **[{ts}] {source} / {agent}** ({kind}): {content}")
    if len(entries) > 80:
        lines.append(f"- ... 及其他 {len(entries) - 80} 条审计记录")
    return lines


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


def _build_challenger_timeline_sections(analysis_states: list, agent_logs: list) -> list[str]:
    """Build timeline grouped by Challenger's phase-specific review rounds."""
    phase_names = {
        "forensics": "Forensics",
        "osint": "OSINT",
        "commander": "Commander",
    }
    sections: list[str] = []
    seen: set[tuple[str, int, str]] = set()
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
        sections.append(f"### Challenger ↔ {label} 第 {phase_round} 轮")
        sections.append("")
        sections.append(f"- 时间: {timestamp}")
        sections.append(f"- 质询对象: {label}")
        sections.append(f"- 置信度/质量分: {_fmt_confidence(feedback.get('confidence', feedback.get('quality_score', 'N/A')))}")
        if feedback.get("quality_delta") is not None:
            sections.append(f"- 置信度变化 Δ(t): {float(feedback.get('quality_delta')):.3f}")
        sections.append(f"- 问题数: {feedback.get('issue_count', 0)}（高严重度 {feedback.get('high_severity_count', 0)}）")
        reason = feedback.get("convergence_reason") or (
            "需要补充证据" if feedback.get("requires_more_evidence") else "进入下一阶段"
        )
        sections.append(f"- 质询结论: {reason}")
        issues = feedback.get("issues_found") or []
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
        sections.append(f"### Challenger ↔ {label} 第 {phase_round} 轮")
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


def _load_pdf_font(size: int):
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


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
    return text


def _display_markdown_line(line: str) -> tuple[str, int]:
    stripped = line.strip()
    if not stripped:
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


def _wrap_html_template(body: str) -> str:
    """将 HTML body 包裹在带暗色主题样式的完整 HTML 模板中"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>TruthSeeker 鉴伪与溯源分析报告</title>
<style>
  @page {{
    size: A4;
    margin: 2cm;
  }}
  body {{
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    font-size: 12pt;
    line-height: 1.7;
    color: #e0e0e0;
    background-color: #1a1a2e;
    padding: 2rem;
  }}
  h1 {{
    color: #00d4ff;
    border-bottom: 2px solid #00d4ff;
    padding-bottom: 0.4em;
    text-align: center;
  }}
  h2 {{
    color: #0abde3;
    border-bottom: 1px solid #333;
    padding-bottom: 0.3em;
    margin-top: 1.8em;
  }}
  h3 {{
    color: #48dbfb;
    margin-top: 1.2em;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    background-color: #16213e;
  }}
  th, td {{
    border: 1px solid #333;
    padding: 0.5em 0.8em;
    text-align: left;
  }}
  th {{
    background-color: #0f3460;
    color: #48dbfb;
  }}
  tr:nth-child(even) {{
    background-color: #1a1a3e;
  }}
  code {{
    background-color: #2d2d44;
    padding: 0.15em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
  }}
  pre {{
    background-color: #0f0f23;
    padding: 1em;
    border-radius: 5px;
    overflow-x: auto;
  }}
  strong {{
    color: #feca57;
  }}
  a {{
    color: #54a0ff;
  }}
  hr {{
    border: none;
    border-top: 1px solid #333;
    margin: 2em 0;
  }}
  em {{
    color: #a0a0b0;
  }}
</style>
</head>
<body>
{body}
</body>
</html>"""
