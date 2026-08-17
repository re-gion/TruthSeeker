"""OSINT Agent - 情报溯源图谱 Agent。"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable

from app.agents.state import AgentLog, EvidenceItem, TruthSeekerState
from app.agents.skills.loader import finalize_skill_execution, load_agent_skill
from app.agents.tools.llm_client import (
    build_sample_references,
    extract_osint_search_entities,
    osint_interpret,
    summarize_previous_analysis,
)
from app.agents.tools.domain_provenance import analyze_domain_provenance
from app.agents.tools.internal_text_aigc import detect_ai_generated_text, text_fingerprint
from app.agents.tools.osint_search import (
    EXA_CONNECT_MAX_ATTEMPTS,
    EXA_TIMEOUT_SECONDS,
    MAX_EXA_QUERIES,
    build_deidentified_queries,
    search_osint,
)
from app.agents.tools.provenance_graph import build_provenance_graph
from app.agents.tools.text_detection import analyze_text, extract_urls_from_text
from app.agents.tools.threat_intel import analyze_urls
from app.config import resolve_kimi_runtime
from app.services.audit_log import record_audit_event
from app.services.case_rag import build_rag_query, case_rag_search
from app.services.consultation_workflow import build_timeline_event
from app.services.evidence_access import download_evidence_bytes
from app.services.experience_library import experience_rag_search
from app.services.text_validation import decode_text_bytes

logger = logging.getLogger(__name__)

TEXT_MAX_CHARS = 10000
EXA_BATCH_TIMEOUT_SECONDS = (
    EXA_TIMEOUT_SECONDS * MAX_EXA_QUERIES * EXA_CONNECT_MAX_ATTEMPTS + 10.0
)
# 实体抽取是一次小型 LLM 调用：超时即回退既有查询源，不得拖慢 OSINT 主流程
ENTITY_EXTRACT_TIMEOUT_SECONDS = 30.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_key(result: dict[str, Any]) -> tuple[str, str]:
    return str(result.get("tool", "")), str(result.get("target", ""))


def _build_reinforcement_context(state: TruthSeekerState, agent: str, previous_analysis: dict[str, Any]) -> dict[str, Any] | None:
    feedback = state.get("challenger_feedback") or {}
    consultation_summary = state.get("confirmed_collaboration_summary") or state.get("confirmed_consultation_summary")
    feedback_phase = str(feedback.get("phase") or "")
    target_agent = str(feedback.get("target_agent") or feedback_phase or "")
    feedback_relevant = target_agent == agent or feedback_phase == agent
    summary_target = ""
    if isinstance(consultation_summary, dict):
        summary_target = str(consultation_summary.get("target_agent") or consultation_summary.get("phase") or "")
    summary_relevant = bool(consultation_summary) and (summary_target == agent or (not summary_target and feedback_relevant))
    consultation_summary_text = (
        consultation_summary.get("confirmed_summary")
        if isinstance(consultation_summary, dict)
        else consultation_summary
    )
    previous_analysis_text = (
        previous_analysis.get("llm_analysis")
        or previous_analysis.get("analysis_summary")
        or previous_analysis.get("summary")
        if isinstance(previous_analysis, dict)
        else previous_analysis
    )
    issues = [issue for issue in (feedback.get("issues_found") or []) if isinstance(issue, dict)]
    relevant_issues = [
        issue for issue in issues
        if not issue.get("agent") or issue.get("agent") == agent or target_agent == agent
    ]
    has_feedback = bool(
        relevant_issues
        or (feedback_relevant and feedback.get("llm_cross_validation"))
        or (feedback_relevant and feedback.get("residual_risks"))
        or summary_relevant
    )
    if not has_feedback:
        return None
    return {
        "target_agent": agent,
        "challenger_phase": feedback.get("phase"),
        "challenger_confidence": feedback.get("confidence"),
        "challenger_issues": relevant_issues or issues,
        "llm_cross_validation": feedback.get("llm_cross_validation"),
        "residual_risks": feedback.get("residual_risks") or [],
        "collaboration_summary": consultation_summary_text if summary_relevant else None,
        "consultation_summary": consultation_summary_text if summary_relevant else None,
        "collaboration_summary_payload": consultation_summary if summary_relevant else None,
        "consultation_summary_payload": consultation_summary if summary_relevant else None,
        "previous_analysis": previous_analysis_text,
        "previous_analysis_payload": summarize_previous_analysis(previous_analysis),
        "instruction": "本轮只针对逻辑质询 Agent 打回点和人机协同摘要补强，不重复上一轮完整报告。",
    }


def _all_evidence_files(state: TruthSeekerState) -> list[dict[str, Any]]:
    files = state.get("evidence_files") or []
    if files:
        return [dict(item) for item in files if isinstance(item, dict)]

    input_files = state.get("input_files") or {}
    merged: list[dict[str, Any]] = []
    for key in ("forensics", "osint"):
        value = input_files.get(key)
        if isinstance(value, list):
            merged.extend(dict(item) for item in value if isinstance(item, dict))
    return merged


async def _read_text_sample(file_info: dict[str, Any]) -> dict[str, str]:
    url = file_info.get("file_url") or file_info.get("storage_path")
    if not isinstance(url, str) or not url or url.startswith("mock://"):
        return {"text": "", "encoding": "", "charset": ""}
    content, _ = await download_evidence_bytes(url, timeout=30.0)
    return decode_text_bytes(content, max_chars=TEXT_MAX_CHARS)


async def _settle_tool(
    *,
    tool: str,
    target: str,
    coro: Awaitable[dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    started_at = _now()
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        result = result if isinstance(result, dict) else {"value": result}
        status = str(result.get("status") or "success")
        degraded = bool(result.get("degraded")) or status in {"degraded", "no_key", "partial"}
        if degraded and status == "success":
            status = "degraded"
        if status not in {"success", "partial", "degraded", "failed"}:
            status = "degraded" if degraded else "success"
        return {
            "tool": tool,
            "target": target,
            "status": status,
            "degraded": degraded or status in {"partial", "failed"},
            "result": result,
            "summary": _summarize_tool(tool, result),
            "started_at": started_at,
            "completed_at": _now(),
        }
    except asyncio.TimeoutError:
        logger.warning("Tool timeout: %s target=%s after %.0fs", tool, target, timeout)
        return {
            "tool": tool,
            "target": target,
            "status": "failed",
            "degraded": True,
            "error": "timeout",
            "summary": f"{tool} 超时",
            "started_at": started_at,
            "completed_at": _now(),
        }
    except Exception as exc:
        logger.warning("Tool failed: %s target=%s error=%s", tool, target, exc)
        return {
            "tool": tool,
            "target": target,
            "status": "failed",
            "degraded": True,
            "error": f"{type(exc).__name__}: {exc}",
            "summary": f"{tool} 调用失败",
            "started_at": started_at,
            "completed_at": _now(),
        }


def _summarize_tool(tool: str, result: dict[str, Any]) -> str:
    if tool == "exa_search":
        reason = result.get("reason")
        if reason == "no_case_specific_matches":
            return (
                f"Exa 搜索完成，检查 {int(result.get('searched_result_count', 0) or 0)} 条候选，"
                "未发现与本案 IOC 直接匹配的公开来源"
            )
        if reason == "no_results":
            return "Exa 搜索完成，未返回公开结果"
        return f"Exa status={result.get('status')}, results={len(result.get('results') or [])}"
    if tool == "virustotal_osint_ioc":
        vt = result.get("virustotal") or {}
        return f"VT threat_score={result.get('threat_score', 0):.2f}, malicious={vt.get('malicious', 0)}"
    if tool == "whoisxml_domain_provenance":
        return result.get("summary") or f"domain={result.get('domain', 'unknown')}, status={result.get('status')}"
    if tool == "ai_text_detector":
        provider = result.get("provider") or "external"
        return result.get("summary") or f"{provider} AI probability={result.get('ai_probability', 0):.2f}"
    if tool == "text_claim_extract":
        social = result.get("social_engineering") or {}
        social_score = float(social.get("score", 0.0) or 0.0)
        return (
            f"文本社工风险抽取: 关键声明 {len(result.get('key_claims') or [])} 条，"
            f"社工评分 {social_score:.1%}"
        )
    return "工具完成"


def _model_claims_from_text(text_result: dict[str, Any] | None, threat_indicators: list[str]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    if text_result:
        for index, claim in enumerate(text_result.get("key_claims") or [], 1):
            claims.append({
                "id": f"text-claim-{index}",
                "label": str(claim),
                "confidence": text_result.get("confidence", 0.5),
                "citation_ids": [],
            })
    for index, indicator in enumerate(threat_indicators[:4], 1):
        claims.append({
            "id": f"indicator-claim-{index}",
            "label": str(indicator),
            "confidence": 0.55,
            "citation_ids": [],
        })
    return claims


def _sanitize_text_claim_extract_result(result: dict[str, Any]) -> dict[str, Any]:
    """Keep text_claim_extract focused on social-engineering claims, not AIGC scoring."""
    sanitized: dict[str, Any] = {
        "method": "social_claim_extract",
        "scope": "social_engineering_claims",
        "key_claims": result.get("key_claims") or [],
        "anomalies": result.get("anomalies") or [],
        "extracted_urls": result.get("extracted_urls") or [],
        "social_engineering": result.get("social_engineering") or {},
        "manipulation_score": float(result.get("manipulation_score", 0.0) or 0.0),
        "limitations": [
            "text_claim_extract 仅用于社工风险 claim 提取与诱导话术分析",
        ],
    }
    return sanitized


def _previous_successes(state: TruthSeekerState) -> dict[tuple[str, str], dict[str, Any]]:
    previous = (state.get("tool_results") or {}).get("osint")
    if not previous:
        previous = (state.get("osint_result") or {}).get("tool_results") or []
    return {
        _tool_key(item): item
        for item in previous
        if isinstance(item, dict) and item.get("status") == "success"
    }


def _reuse_forensics_text_aigc(state: TruthSeekerState, text: str) -> dict[str, Any] | None:
    fingerprint = text_fingerprint(text)
    candidates = []
    candidates.extend((state.get("tool_results") or {}).get("forensics") or [])
    candidates.extend((state.get("forensics_result") or {}).get("tool_results") or [])
    for item in candidates:
        if not isinstance(item, dict) or item.get("tool") != "ai_text_detector" or item.get("status") != "success":
            continue
        result = item.get("result")
        if not isinstance(result, dict) or result.get("status") != "success":
            continue
        if result.get("text_fingerprint") != fingerprint:
            continue
        return {
            **item,
            "reused": True,
            "reused_from": "forensics",
            "result": {**result, "reused_from": "forensics"},
        }
    return None


def _upstream_verified_conclusions(state: TruthSeekerState) -> dict[str, Any] | None:
    """汇总取证阶段经逻辑质询核验的鉴伪结论，供 OSINT 阶段直接引用。

    阶段推进到 OSINT 即代表取证结论已通过 Challenger 放行门槛，
    属于可信上游结论；OSINT 讨论检材真伪时必须引用，不得独立重建
    分歧的低置信判断（跨阶段证据复用）。
    """
    forensics = state.get("forensics_result") or {}
    if not isinstance(forensics, dict) or not forensics:
        return None
    aigc_probability = float(
        forensics.get("aigc_probability", forensics.get("deepfake_probability", 0.0)) or 0.0
    )
    is_aigc = bool(forensics.get("is_aigc", forensics.get("is_deepfake", False)))
    media_summaries: list[str] = []
    text_summaries: list[str] = []
    audio_transcript_summaries: list[str] = []
    for item in forensics.get("tool_results") or []:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "success":
            continue
        summary = str(item.get("summary") or "").strip()
        if not summary:
            continue
        # 文本 AIGC 检测同样是取证阶段的鉴伪结论：只纳入上游引用，
        # 避免 OSINT 复用后当作自己的独立推断复述（跨阶段证据复用）。
        # video_keyframe_aigc 是视频画面维度的检测结论，必须与音轨结论
        # 一并引用，否则下游只见 RD 音轨概率，会误判画面维度缺失或把
        # 音轨概率当成画面伪造概率。
        if item.get("tool") in {"aigc_image_detector", "reality_defender", "video_keyframe_aigc"}:
            media_summaries.append(summary[:200])
        elif item.get("tool") == "ai_text_detector":
            text_summaries.append(summary[:200])
        elif item.get("tool") == "audio_transcription":
            # ASR 转写属于证据内容而非鉴伪结论，供 OSINT 做音频语义与
            # 文本主题/外部情报的一致性分析时引用。
            audio_transcript_summaries.append(summary[:200])
    return {
        "verified_by": "电子取证阶段结论，已通过逻辑质询 Agent 阶段审查",
        "aigc_probability": aigc_probability,
        "is_aigc": is_aigc,
        "forensics_confidence": float(forensics.get("confidence", 0.0) or 0.0),
        "forensics_degraded": bool(forensics.get("degraded", False)),
        "model_used": forensics.get("model_used"),
        "media_detection_summaries": media_summaries[:4],
        "text_detection_summaries": text_summaries[:4],
        "audio_transcript_summaries": audio_transcript_summaries[:4],
        "citation_rule": "涉及检材真伪、伪造性或是否 AI 生成的判断必须直接引用本结论，不得独立重建分歧的低置信判断。",
    }


def _find_reusable_exa_hit(previous_successes: dict[tuple[str, str], dict[str, Any]], phase_round: int) -> dict[str, Any] | None:
    """返回上一轮已有命中的 Exa 成功结果；零命中的有效负结果不复用。

    零命中结果若被复用，重跑轮次不会真实重搜，置信度精确停滞（Δ=0），
    案件会被硬门槛锁死在打回-协同循环里。
    """
    if phase_round <= 1:
        return None
    for (tool_name, _target), item in previous_successes.items():
        if tool_name == "exa_search" and ((item.get("result") or {}).get("results")):
            return {**item, "reused": True}
    return None


def _osint_search_confidence(exa_status: str, search_result_count: int, *, has_virustotal: bool) -> float:
    """按搜索覆盖而非仅命中数评估 OSINT 置信度。

    - Exa 失败且无 VT 佐证：低置信 0.25；
    - Exa 正常执行完成（success）：零命中也是完整覆盖（有效负结果），
      保底放行线 0.8，命中再加分；
    - 其他（degraded/partial 等）：沿用 0.62 基础分。
    """
    if exa_status == "failed" and not has_virustotal:
        return 0.25
    if exa_status == "success":
        return min(0.92, 0.80 + search_result_count * 0.03)
    return min(0.92, 0.62 + search_result_count * 0.04)


def _upstream_citation_markdown(task_id: str, conclusions: dict[str, Any]) -> str:
    """生成确定性注入 OSINT 报告开头的上游已核验结论引用块。

    引用块由代码而非模型生成：只要取证结论通过质询放行，报告中就必然
    出现带来源归因的引用，杜绝“叙事归属缺陷→反复打回→协同”的死锁。
    """
    is_aigc = bool(conclusions.get("is_aigc"))
    aigc_probability = float(conclusions.get("aigc_probability", 0.0) or 0.0)
    forensics_confidence = float(conclusions.get("forensics_confidence", 0.0) or 0.0)
    lines = [
        "### 上游已核验结论引用",
        "",
        f"- 来源：{conclusions.get('verified_by', '电子取证阶段结论')}（任务 {task_id}）",
        f"- 综合判定：{'检出 AIGC 特征' if is_aigc else '未检出 AIGC 特征'}"
        f"（AIGC 概率 {aigc_probability:.1%}，取证置信度 {forensics_confidence:.1%}）",
    ]
    for summary in conclusions.get("media_detection_summaries") or []:
        lines.append(f"- 图像/音视频检测：{summary}")
    for summary in conclusions.get("text_detection_summaries") or []:
        lines.append(f"- 文本检测：{summary}")
    for summary in conclusions.get("audio_transcript_summaries") or []:
        lines.append(f"- 音频语义转写（ASR）：{summary}")
    lines.extend([
        "",
        "> 本小节由系统确定性注入。本报告涉及检材真伪、伪造性或是否 AI 生成的判断均以本小节为准；"
        "正文如与上述数值不一致，以上游已核验结论为准。",
    ])
    return "\n".join(lines)


async def osint_node(state: TruthSeekerState) -> dict:
    """
    情报溯源图谱 Agent：
    1. 读取全局证据板、取证结果、用户样本和全局提示词；
    2. 用脱敏线索调用 Exa 搜索，结合 VirusTotal 与文本声明抽取；
    3. 生成可视化情报溯源图谱并提交给 Challenger 审查。
    """
    task_id = state["task_id"]
    input_type = state.get("input_type", "text")
    case_prompt = state.get("case_prompt", "")
    round_num = state.get("current_round", 1)
    phase_rounds = dict(state.get("phase_rounds") or {"forensics": 1, "osint": 1, "commander": 1})
    phase_round = int(phase_rounds.get("osint", 1))

    logs: list[AgentLog] = []

    def log(log_type: str, content: str) -> None:
        logs.append({
            "agent": "osint",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": _now(),
        })

    files = _all_evidence_files(state)
    sample_refs = build_sample_references(files)
    text_files = [item for item in files if item.get("modality") == "text"]
    file_names = [str(item.get("name") or "") for item in files if item.get("name")]

    log("thinking", f"情报溯源图谱Agent 启动，任务 ID: {task_id}")
    log("thinking", f"读取全局证据板与电子取证结果，准备抽取实体、声明、引用和关系")
    skill_load = load_agent_skill("osint", "primary_analysis")
    skill_initial = skill_load.execution
    if skill_initial.get("load_status") == "loaded":
        log("thinking", f"核心 Skill {skill_initial['skill_name']} v{skill_initial['skill_version']} 已加载，工作流 primary_analysis")
    else:
        reason = "；".join(skill_initial.get("limitations") or ["未知原因"])
        log("action", f"核心 Skill 未加载，继续使用系统提示词；原因：{reason}")
    record_audit_event(
        action=f"skill.{skill_initial.get('load_status', 'degraded')}",
        task_id=task_id,
        agent="osint",
        metadata=skill_initial,
    )
    if case_prompt:
        log("thinking", f"全局检测目标: {case_prompt[:120]}")
    record_audit_event(
        action="osint.start",
        task_id=task_id,
        agent="osint",
        metadata={"round": round_num, "file_count": len(files)},
    )

    text_contents: list[str] = []
    text_samples: list[dict[str, Any]] = []
    urls_to_check = extract_urls_from_text(case_prompt)
    text_analysis_result: dict[str, Any] | None = None
    tool_results: list[dict[str, Any]] = []
    previous_successes = _previous_successes(state)

    def maybe_reuse(tool: str, target: str) -> bool:
        if phase_round <= 1:
            return False
        previous = previous_successes.get((tool, target))
        if previous:
            tool_results.append({**previous, "reused": True})
            return True
        return False

    for item in text_files:
        try:
            decoded = await _read_text_sample(item)
            content = decoded.get("text", "")
            if content:
                text_contents.append(content)
                text_samples.append({
                    "name": str(item.get("name") or "text"),
                    "content": content[:4000],
                    "detected_encoding": decoded.get("encoding"),
                    "charset": decoded.get("charset"),
                })
                urls_to_check.extend(extract_urls_from_text(content))
        except Exception as exc:
            log("action", f"文本检材读取失败: {item.get('name', 'unknown')} ({type(exc).__name__})")

    if text_contents:
        combined = "\n\n".join(text_contents)[:TEXT_MAX_CHARS]
        if maybe_reuse("text_claim_extract", "uploaded_text"):
            text_tool = tool_results[-1]
        else:
            # 社工声明抽取只依赖本地规则（URL/结构化特征/诱导话术），
            # 不调用 LLM：LLM 版 AIGC 概率由下方独立 ai_text_detector 工具承担，
            # 避免 LLM 不可用时本工具挂起至 120s 超时导致整轮降级。
            text_tool = await _settle_tool(
                tool="text_claim_extract",
                target="uploaded_text",
                coro=analyze_text(combined, use_llm=False),
                timeout=30.0,
            )
            tool_results.append(text_tool)
        if isinstance(text_tool.get("result"), dict):
            text_analysis_result = _sanitize_text_claim_extract_result(text_tool["result"])
            text_tool["result"] = text_analysis_result
            text_tool["summary"] = _summarize_tool("text_claim_extract", text_analysis_result)
        else:
            text_analysis_result = None
        if not maybe_reuse("ai_text_detector", "uploaded_text"):
            text_aigc_tool = _reuse_forensics_text_aigc(state, combined)
            if text_aigc_tool is None:
                text_aigc_tool = await _settle_tool(
                    tool="ai_text_detector",
                    target="uploaded_text",
                    coro=detect_ai_generated_text(combined, target="uploaded_text"),
                    timeout=45.0,
                )
            else:
                # 复用的就是取证阶段已核验结论：摘要显式标注来源，
                # 避免 LLM 把上游数字包装成 OSINT 独立推断（跨阶段证据复用）。
                base_summary = str(text_aigc_tool.get("summary") or "")
                if not base_summary.startswith("引用电子取证阶段已核验结论"):
                    text_aigc_tool["summary"] = f"引用电子取证阶段已核验结论（复用）: {base_summary}"
            tool_results.append(text_aigc_tool)

    urls_to_check = list(dict.fromkeys(urls_to_check))
    vt_tasks = [
        _settle_tool(
            tool="virustotal_osint_ioc",
            target=url,
            coro=analyze_urls([url]),
            timeout=45.0,
        )
        for url in urls_to_check[:5]
        if not maybe_reuse("virustotal_osint_ioc", url)
    ]
    if vt_tasks:
        log("action", f"正在查询 {len(vt_tasks)} 个 URL/域名 IOC 的 VirusTotal 情报")
        tool_results.extend(await asyncio.gather(*vt_tasks))

    domain_tasks = [
        _settle_tool(
            tool="whoisxml_domain_provenance",
            target=url,
            coro=analyze_domain_provenance(url),
            # 工具内部按 whois -> dns -> geo 串行调用最多 3 个组件，
            # 超时预算必须覆盖组件总和，否则慢响应会在中途被整体杀掉。
            timeout=90.0,
        )
        for url in urls_to_check[:5]
        if not maybe_reuse("whoisxml_domain_provenance", url)
    ]
    if domain_tasks:
        log("action", f"正在查询 {len(domain_tasks)} 个 URL/域名的 WhoisXML 注册、当前 DNS 与 IP 归属")
        tool_results.extend(await asyncio.gather(*domain_tasks))

    threat_indicators: list[str] = []
    vt_threat_score = 0.0
    virustotal_summaries: list[dict[str, Any]] = []
    domain_provenance_summaries: list[dict[str, Any]] = []
    text_aigc_detection: dict[str, Any] | None = None
    for item in tool_results:
        result = item.get("result") or {}
        if item.get("tool") == "virustotal_osint_ioc":
            vt_threat_score = max(vt_threat_score, float(result.get("threat_score", 0.0) or 0.0))
            threat_indicators.extend(str(v) for v in result.get("indicators") or [])
            virustotal_summaries.append(result)
        if item.get("tool") == "whoisxml_domain_provenance":
            domain_provenance_summaries.append(result)
            if result.get("summary"):
                threat_indicators.append(str(result["summary"]))
        if item.get("tool") == "ai_text_detector" and result.get("status") == "success":
            text_aigc_detection = result

    if text_analysis_result:
        social = text_analysis_result.get("social_engineering") or {}
        social_score = float(social.get("score", 0.0) or 0.0)
        if social_score >= 0.45:
            threat_indicators.append(f"文本社工诱导风险高 ({social_score:.1%})")
        threat_indicators.extend(str(v) for v in (social.get("indicators") or [])[:5])
        threat_indicators.extend(str(v) for v in (text_analysis_result.get("anomalies") or [])[:3])
    if text_aigc_detection:
        external_text_prob = float(text_aigc_detection.get("ai_probability", 0.0) or 0.0)
        if external_text_prob >= 0.6:
            provider = text_aigc_detection.get("provider") or "外部工具"
            threat_indicators.append(f"{provider} 文本 AI 生成概率高 ({external_text_prob:.1%})")

    # 上一轮已有命中的搜索结果继续复用（节省配额）；
    # 零命中的有效负结果不复用——重跑轮次要带着可能更新的查询真实重搜，
    # 否则置信度停滞会把它锁死在打回循环里。
    previous_exa_hit = _find_reusable_exa_hit(previous_successes, phase_round)

    queries: list[str] = []
    if previous_exa_hit is not None:
        exa_tool = previous_exa_hit
        tool_results.append(exa_tool)
        reused_result = exa_tool.get("result") or {}
        queries = [str(q) for q in reused_result.get("queries") or []]
        log("action", f"复用上一轮已有命中的 Exa 搜索结果（命中 {len(reused_result.get('results') or [])} 条公开来源）")
    else:
        entities: list[str] = []
        if case_prompt or text_contents:
            try:
                entities = await asyncio.wait_for(
                    extract_osint_search_entities(case_prompt, text_contents),
                    timeout=ENTITY_EXTRACT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                log("action", "搜索实体抽取超时，回退既有查询源")
            except Exception as exc:
                log("action", f"搜索实体抽取失败（{type(exc).__name__}），回退既有查询源")
        if entities:
            log("action", f"抽取到 {len(entities)} 个可检索实体：{'、'.join(entities)}")
        queries = build_deidentified_queries(
            case_prompt=case_prompt,
            threat_indicators=threat_indicators,
            urls=urls_to_check,
            file_names=file_names,
            entities=entities,
        )
        log("action", f"生成 {len(queries)} 条脱敏 OSINT 查询，调用 Exa 搜索")
        exa_target = "; ".join(queries)[:180] or "no_query"
        exa_tool = await _settle_tool(
            tool="exa_search",
            target=exa_target,
            coro=search_osint(queries),
            timeout=EXA_BATCH_TIMEOUT_SECONDS,
        )
        tool_results.append(exa_tool)
    search_results = (exa_tool.get("result") or {}).get("results") or []

    exa_signal = 0.12 if search_results else 0.0
    text_social_score = 0.0
    text_manipulation_score = 0.0
    text_ai_score = 0.0
    if text_analysis_result:
        text_social_score = float((text_analysis_result.get("social_engineering") or {}).get("score", 0.0) or 0.0)
        text_manipulation_score = float(text_analysis_result.get("manipulation_score", 0.0) or 0.0)
    if text_aigc_detection:
        external_text_prob = float(text_aigc_detection.get("ai_probability", 0.0) or 0.0)
        text_ai_score = max(text_ai_score, external_text_prob * 0.5)
    text_risk_score = max(text_social_score, text_manipulation_score, text_ai_score)
    threat_score = min(1.0, max(vt_threat_score, exa_signal, text_risk_score))
    if not threat_indicators and search_results:
        threat_indicators.append("Exa 检索返回相关公开情报来源，需结合引用人工复核")
    if not threat_indicators:
        threat_indicators.append("未发现明确外部威胁或溯源线索")

    rag_query = build_rag_query(
        agent="osint",
        case_prompt=case_prompt,
        input_type=input_type,
        evidence_files=files,
        tool_summaries=threat_indicators[:8] + queries[:4],
    )
    case_rag = await case_rag_search(query=rag_query, agent="osint")
    tool_results.append(case_rag)
    log("action", f"公开案例 RAG 检索完成: {case_rag.get('summary', '无摘要')}")
    record_audit_event(
        action=f"case_rag.{case_rag.get('status', 'unknown')}",
        task_id=task_id,
        agent="osint",
        metadata={
            "match_count": len(case_rag.get("matches") or []),
            "degraded": bool(case_rag.get("degraded")),
        },
    )
    experience_rag = await experience_rag_search(
        query=rag_query,
        user_id=str(state.get("user_id") or ""),
        agent="osint",
    )
    tool_results.append(experience_rag)
    log("action", f"个人经验库检索完成: {experience_rag.get('summary', '无摘要')}")
    record_audit_event(
        action=f"experience_rag.{experience_rag.get('status', 'unknown')}",
        task_id=task_id,
        agent="osint",
        metadata={
            "match_count": len(experience_rag.get("matches") or []),
            "degraded": bool(experience_rag.get("degraded")),
        },
    )

    scoring_tools = [item for item in tool_results if item.get("tool") not in {"case_rag_search", "experience_rag_search"}]
    degraded = any(item.get("status") in {"partial", "degraded", "failed"} for item in scoring_tools)
    if degraded:
        failed_count = sum(1 for item in scoring_tools if item.get("status") == "failed")
        degraded_count = sum(1 for item in scoring_tools if item.get("status") == "degraded")
        partial_count = sum(1 for item in scoring_tools if item.get("status") == "partial")
        record_audit_event(
            action="osint.degraded",
            task_id=task_id,
            agent="osint",
            metadata={"failed": failed_count, "degraded": degraded_count, "partial": partial_count, "total": len(tool_results)},
        )

    osint_confidence = _osint_search_confidence(
        str(exa_tool.get("status") or ""),
        len(search_results),
        has_virustotal=bool(virustotal_summaries),
    )
    model_claims = _model_claims_from_text(text_analysis_result, threat_indicators)

    success_count = sum(1 for item in tool_results if item.get("status") == "success")
    partial_count = sum(1 for item in tool_results if item.get("status") == "partial")
    failed_count = sum(1 for item in scoring_tools if item.get("status") == "failed")
    degraded_count = sum(1 for item in scoring_tools if item.get("status") == "degraded")
    available_count = success_count + partial_count
    other_count = max(0, len(tool_results) - available_count - degraded_count - failed_count)

    partial_result = {
        "threat_score": threat_score,
        "social_engineering_score": text_social_score,
        "text_risk_score": text_risk_score,
        "is_malicious": threat_score > 0.75,
        "is_suspicious": threat_score > 0.4,
        "confidence": osint_confidence,
        "threat_indicators": threat_indicators,
        "virustotal_summary": virustotal_summaries,
        "domain_provenance_summary": domain_provenance_summaries,
        "search_results": search_results,
        "search_queries": queries,
        "text_analysis": text_analysis_result,
        "text_aigc_detection": text_aigc_detection,
        "text_samples": text_samples,
        "model_claims": model_claims,
        "tool_results": tool_results,
        "tool_summary": {
            "total": len(tool_results),
            "success": success_count,
            "partial": partial_count,
            "available": available_count,
            "other": other_count,
            "degraded": degraded_count,
            "failed": failed_count,
            "reused": sum(1 for item in tool_results if item.get("reused")),
            "case_rag_status": case_rag.get("status"),
            "case_rag_matches": len(case_rag.get("matches") or []),
            "experience_rag_status": experience_rag.get("status"),
            "experience_rag_matches": len(experience_rag.get("matches") or []),
        },
        "case_rag": case_rag,
        "experience_rag": experience_rag,
        "degraded": degraded,
        "timestamp": _now(),
        "skill_execution": skill_initial,
    }
    upstream_conclusions = _upstream_verified_conclusions(state)
    if upstream_conclusions:
        partial_result["upstream_verified_conclusions"] = upstream_conclusions
        log(
            "thinking",
            f"纳入上游取证已核验结论：AIGC 概率 {upstream_conclusions['aigc_probability']:.1%}，"
            f"取证置信度 {upstream_conclusions['forensics_confidence']:.1%}，检材真伪讨论将直接引用",
        )

    reinforcement_context = _build_reinforcement_context(state, "osint", state.get("osint_result") or {})
    if reinforcement_context:
        partial_result["reinforcement_context"] = reinforcement_context
        log("thinking", "读取 Challenger/会诊反馈，按打回点补强情报溯源分析")

    runtime = resolve_kimi_runtime()
    provider_label = {
        "minimax": "MiniMax",
        "mimo": "MiMo",
        "official": "Kimi",
        "coding": "Kimi",
        "siliconflow": "Kimi",
    }.get(runtime.get("provider", ""), "多模态模型")
    log("action", f"正在调用 {provider_label} 进行情报归纳与溯源图谱解释")
    llm_status: dict[str, Any] = {}
    llm_analysis = await osint_interpret(
        partial_result,
        input_type,
        case_prompt,
        sample_refs,
        skill_context=skill_load.prompt_context,
        upstream_conclusions=upstream_conclusions,
        llm_status=llm_status,
    )
    if upstream_conclusions:
        # 确定性注入：无论模型输出什么，报告开头必然出现带上游归因的引用块，
        # 质询 Agent 不再因叙事措辞归属反复打回。若模型自行写了同名小节，
        # 先移除再以系统版本为准，避免重复标题。
        stripped_analysis = re.sub(
            r"###\s*上游已核验结论引用.*?(?=\n###\s|\Z)",
            "",
            llm_analysis,
            flags=re.DOTALL,
        ).strip()
        llm_analysis = _upstream_citation_markdown(task_id, upstream_conclusions) + "\n\n" + stripped_analysis
        log("finding", "已确定性注入上游已核验结论引用块，检材真伪讨论以上游结论为准")
    partial_result["llm_analysis"] = llm_analysis
    skill_execution = finalize_skill_execution(skill_load, llm_analysis, llm_status=llm_status)
    partial_result["skill_execution"] = skill_execution
    skill_status = str(skill_execution.get("execution_status") or "skipped")
    if skill_status == "applied":
        log("finding", "核心 Skill 已应用，OSINT 输出契约检查通过")
    elif skill_status == "check_failed":
        log("action", "核心 Skill 已注入，但 OSINT 输出契约检查未通过")
    elif skill_execution.get("load_status") == "loaded":
        log("action", "LLM 已降级或未执行，本轮无法证明实际采用核心 Skill")
    record_audit_event(
        action=f"skill.{skill_status}",
        task_id=task_id,
        agent="osint",
        metadata=skill_execution,
    )

    provenance_graph = build_provenance_graph(
        task_id=task_id,
        evidence_files=files,
        forensics_result=state.get("forensics_result") or {},
        osint_result=partial_result,
        challenger_feedback=state.get("challenger_feedback") or {},
    )
    partial_result["provenance_graph"] = provenance_graph

    evidence_item: EvidenceItem = {
        "type": "osint",
        "source": "osint_agent",
        "description": (
            f"情报溯源：威胁评分 {threat_score:.1%}，"
            f"图谱节点 {len(provenance_graph['nodes'])} 个，引用 {len(provenance_graph['citations'])} 条"
        ),
        "confidence": osint_confidence,
        "metadata": {
            "threat_score": threat_score,
            "graph_quality": provenance_graph.get("quality"),
            "search_result_count": len(search_results),
            "threat_indicators": threat_indicators[:8],
        },
    }

    log("finding", f"情报图谱生成完成：节点 {len(provenance_graph['nodes'])}，边 {len(provenance_graph['edges'])}")
    record_audit_event(
        action="osint.complete",
        task_id=task_id,
        agent="osint",
        metadata={
            "threat_score": threat_score,
            "degraded": degraded,
            "search_results": len(search_results),
            "graph_nodes": len(provenance_graph["nodes"]),
        },
    )
    log("conclusion", "情报溯源图谱已写入全局证据板，等待逻辑质询Agent审查")

    return {
        "analysis_phase": "osint",
        "phase_rounds": phase_rounds,
        "osint_result": partial_result,
        "provenance_graph": provenance_graph,
        "evidence_board": [evidence_item],
        "degradation_status": {
            "exa": exa_tool.get("status", "unknown"),
            "virustotal": "degraded" if any(item.get("tool") == "virustotal_osint_ioc" and item.get("degraded") for item in tool_results) else "ok",
            "skill.osint": skill_status,
        },
        "tool_results": {"osint": tool_results},
        "logs": logs,
        "timeline_events": [build_timeline_event(
            round_number=round_num,
            agent="osint",
            event_type="provenance_graph",
            source_kind="agent",
            from_phase="osint",
            target_agent="challenger",
            content=f"图谱生成完成: {len(provenance_graph['nodes'])} 节点 / {len(provenance_graph['edges'])} 边",
        )],
    }
