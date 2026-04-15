"""报告生成服务 — Markdown + PDF 报告"""
import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

async def _fetch_task_data(task_id: str) -> dict:
    """从 Supabase 获取任务的完整数据（task + analysis_states + agent_logs）"""
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
        .order("created_at", desc=False)
        .execute()
    )
    agent_logs = logs_resp.data or []

    return {
        "task": task,
        "analysis_states": analysis_states,
        "agent_logs": agent_logs,
    }


# ---------------------------------------------------------------------------
# Markdown 报告
# ---------------------------------------------------------------------------

async def generate_markdown_report(task_id: str) -> str:
    """生成 Markdown 格式的鉴伪与溯源分析报告"""
    data = await _fetch_task_data(task_id)
    task = data["task"]
    analysis_states = data["analysis_states"]
    agent_logs = data["agent_logs"]

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
    lines.append("")

    # ---- 最终裁决 ----
    result = task.get("result")
    if result and isinstance(result, dict):
        lines.append("## 二、最终裁决")
        lines.append("")
        verdict = result.get("verdict", "N/A")
        confidence = result.get("confidence", "N/A")
        lines.append(f"- **裁决结论**: {verdict}")
        lines.append(f"- **置信度**: {_fmt_confidence(confidence)}")
        key_evidence = result.get("key_evidence", [])
        if key_evidence:
            lines.append("- **关键证据**:")
            for ev in key_evidence:
                if isinstance(ev, dict):
                    lines.append(f"  - [{ev.get('type', '?')}] {ev.get('description', ev)}")
                else:
                    lines.append(f"  - {ev}")
        lines.append("")

    # ---- Forensics 分析 ----
    forensics = _extract_agent_result(analysis_states, "forensics")
    if forensics:
        lines.append("## 三、Forensics 取证分析")
        lines.append("")
        lines.append(_dict_to_markdown(forensics))
        lines.append("")

    # ---- OSINT 情报 ----
    osint = _extract_agent_result(analysis_states, "osint")
    if osint:
        lines.append("## 四、OSINT 开源情报")
        lines.append("")
        lines.append(_dict_to_markdown(osint))
        lines.append("")

    # ---- Challenger 交叉验证 ----
    challenger = _extract_agent_result(analysis_states, "challenger")
    if challenger:
        lines.append("## 五、Challenger 交叉验证")
        lines.append("")
        lines.append(_dict_to_markdown(challenger))
        lines.append("")

    # ---- 证据时间线 ----
    if agent_logs:
        lines.append("## 六、证据时间线（按轮次）")
        lines.append("")
        grouped = _group_logs_by_round(agent_logs)
        for round_num, logs in grouped.items():
            lines.append(f"### 第 {round_num} 轮")
            lines.append("")
            for log in logs:
                agent = log.get("agent", "unknown")
                log_type = log.get("type", "info")
                content = log.get("content", "")
                ts = _fmt_time(log.get("created_at"))
                lines.append(f"- **[{ts}] {agent}** ({log_type}): {content}")
            lines.append("")

    # ---- 建议 ----
    lines.append("## 七、建议与说明")
    lines.append("")
    if result and isinstance(result, dict):
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
    lines.append(f"*报告生成时间: {datetime.now(timezone.utc).isoformat()}*")
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
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_full).write_pdf()
        return pdf_bytes
    except ImportError:
        logger.warning("weasyprint not installed, falling back to HTML bytes")
        return html_full.encode("utf-8")
    except Exception as e:
        logger.error("weasyprint PDF generation failed: %s", e)
        return html_full.encode("utf-8")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _fmt_time(value: Optional[str]) -> str:
    """格式化时间戳"""
    if not value:
        return "N/A"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return str(value)


def _fmt_confidence(value) -> str:
    """格式化置信度"""
    if isinstance(value, (int, float)):
        return f"{value:.1%}"
    return str(value)


def _extract_agent_result(analysis_states: list, agent_name: str) -> Optional[dict]:
    """从 analysis_states 中提取指定 agent 的结果"""
    for state in analysis_states:
        if state.get("agent_name") == agent_name or state.get("agent") == agent_name:
            return state.get("result") or state.get("data")
    return None


def _dict_to_markdown(data: dict, indent: int = 0) -> str:
    """将字典递归转为 Markdown 列表"""
    lines = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}- **{key}**:")
            lines.append(_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}- **{key}**:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(_dict_to_markdown(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}- **{key}**: {value}")
    return "\n".join(lines)


def _group_logs_by_round(logs: list) -> dict:
    """按轮次分组 agent_logs"""
    grouped: dict[int, list] = {}
    for log in logs:
        round_num = log.get("round", 0)
        grouped.setdefault(round_num, []).append(log)
    return dict(sorted(grouped.items()))


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
