"""OSINT Agent - 情报溯源图谱 Agent。"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable

import httpx

from app.agents.state import AgentLog, EvidenceItem, TruthSeekerState
from app.agents.tools.llm_client import build_sample_references, osint_interpret
from app.agents.tools.osint_search import build_deidentified_queries, search_osint
from app.agents.tools.provenance_graph import build_provenance_graph
from app.agents.tools.text_detection import analyze_text, extract_urls_from_text
from app.agents.tools.threat_intel import analyze_urls
from app.services.audit_log import record_audit_event

logger = logging.getLogger(__name__)

TEXT_MAX_CHARS = 10000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


async def _read_text_sample(file_info: dict[str, Any]) -> str:
    url = file_info.get("file_url") or file_info.get("storage_path")
    if not isinstance(url, str) or not url or url.startswith("mock://"):
        return ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.text[:TEXT_MAX_CHARS]


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
        degraded = bool(result.get("degraded")) or status in {"degraded", "no_key"}
        if degraded and status == "success":
            status = "degraded"
        if status not in {"success", "degraded", "failed"}:
            status = "degraded" if degraded else "success"
        return {
            "tool": tool,
            "target": target,
            "status": status,
            "degraded": degraded or status == "failed",
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
        return f"Exa status={result.get('status')}, results={len(result.get('results') or [])}"
    if tool == "virustotal_osint_ioc":
        vt = result.get("virustotal") or {}
        return f"VT threat_score={result.get('threat_score', 0):.2f}, malicious={vt.get('malicious', 0)}"
    if tool == "text_claim_extract":
        return f"claims={len(result.get('key_claims') or [])}, ai_probability={result.get('ai_probability', 0):.2f}"
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


async def osint_node(state: TruthSeekerState) -> dict:
    """
    情报溯源图谱 Agent：
    1. 读取全局证据板、取证结果、用户样本和全局提示词；
    2. 用脱敏线索调用 Exa 搜索，结合 VirusTotal 与文本声明抽取；
    3. 生成可视化情报溯源图谱并提交给 Challenger 审查。
    """
    task_id = state["task_id"]
    input_type = state.get("input_type", "mixed")
    case_prompt = state.get("case_prompt", "")
    round_num = state.get("current_round", 1)
    phase_rounds = dict(state.get("phase_rounds") or {"forensics": 1, "osint": 1, "commander": 1})

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
    if case_prompt:
        log("thinking", f"全局检测目标: {case_prompt[:120]}")
    record_audit_event(
        action="osint.start",
        task_id=task_id,
        agent="osint",
        metadata={"round": round_num, "file_count": len(files)},
    )

    text_contents: list[str] = []
    urls_to_check = extract_urls_from_text(case_prompt)
    text_analysis_result: dict[str, Any] | None = None
    tool_results: list[dict[str, Any]] = []

    for item in text_files:
        try:
            content = await _read_text_sample(item)
            if content:
                text_contents.append(content)
                urls_to_check.extend(extract_urls_from_text(content))
        except Exception as exc:
            log("action", f"文本检材读取失败: {item.get('name', 'unknown')} ({type(exc).__name__})")

    if text_contents:
        combined = "\n\n".join(text_contents)[:TEXT_MAX_CHARS]
        text_tool = await _settle_tool(
            tool="text_claim_extract",
            target="uploaded_text",
            coro=analyze_text(combined),
            timeout=120.0,
        )
        tool_results.append(text_tool)
        text_analysis_result = text_tool.get("result") if isinstance(text_tool.get("result"), dict) else None

    urls_to_check = list(dict.fromkeys(urls_to_check))
    vt_tasks = [
        _settle_tool(
            tool="virustotal_osint_ioc",
            target=url,
            coro=analyze_urls([url]),
            timeout=45.0,
        )
        for url in urls_to_check[:5]
    ]
    if vt_tasks:
        log("action", f"正在查询 {len(vt_tasks)} 个 URL/域名 IOC 的 VirusTotal 情报")
        tool_results.extend(await asyncio.gather(*vt_tasks))

    threat_indicators: list[str] = []
    vt_threat_score = 0.0
    virustotal_summaries: list[dict[str, Any]] = []
    for item in tool_results:
        result = item.get("result") or {}
        if item.get("tool") == "virustotal_osint_ioc":
            vt_threat_score = max(vt_threat_score, float(result.get("threat_score", 0.0) or 0.0))
            threat_indicators.extend(str(v) for v in result.get("indicators") or [])
            virustotal_summaries.append(result)

    if text_analysis_result:
        ai_prob = float(text_analysis_result.get("ai_probability", 0.0) or 0.0)
        if ai_prob > 0.6:
            threat_indicators.append(f"文本 AI 生成概率高 ({ai_prob:.1%})")
        social = text_analysis_result.get("social_engineering") or {}
        social_score = float(social.get("score", 0.0) or 0.0)
        if social_score >= 0.45:
            threat_indicators.append(f"文本社工诱导风险高 ({social_score:.1%})")
        threat_indicators.extend(str(v) for v in (social.get("indicators") or [])[:5])
        threat_indicators.extend(str(v) for v in (text_analysis_result.get("anomalies") or [])[:3])

    queries = build_deidentified_queries(
        case_prompt=case_prompt,
        threat_indicators=threat_indicators,
        urls=urls_to_check,
        file_names=file_names,
    )
    log("action", f"生成 {len(queries)} 条脱敏 OSINT 查询，调用 Exa 搜索")
    exa_tool = await _settle_tool(
        tool="exa_search",
        target="; ".join(queries)[:180] or "no_query",
        coro=search_osint(queries),
        timeout=60.0,
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
        ai_prob = float(text_analysis_result.get("ai_probability", 0.0) or 0.0)
        text_ai_score = 0.55 if ai_prob >= 0.75 and urls_to_check else 0.0
    text_risk_score = max(text_social_score, text_manipulation_score, text_ai_score)
    threat_score = min(1.0, max(vt_threat_score, exa_signal, text_risk_score))
    if not threat_indicators and search_results:
        threat_indicators.append("Exa 检索返回相关公开情报来源，需结合引用人工复核")
    if not threat_indicators:
        threat_indicators.append("未发现明确外部威胁或溯源线索")

    degraded = any(item.get("status") in {"degraded", "failed"} for item in tool_results)
    if degraded:
        failed_count = sum(1 for item in tool_results if item.get("status") == "failed")
        degraded_count = sum(1 for item in tool_results if item.get("status") == "degraded")
        record_audit_event(
            action="osint.degraded",
            task_id=task_id,
            agent="osint",
            metadata={"failed": failed_count, "degraded": degraded_count, "total": len(tool_results)},
        )

    osint_confidence = 0.25 if exa_tool.get("status") == "failed" and not virustotal_summaries else min(0.92, 0.62 + len(search_results) * 0.04)
    model_claims = _model_claims_from_text(text_analysis_result, threat_indicators)

    partial_result = {
        "threat_score": threat_score,
        "social_engineering_score": text_social_score,
        "text_risk_score": text_risk_score,
        "is_malicious": threat_score > 0.75,
        "is_suspicious": threat_score > 0.4,
        "confidence": osint_confidence,
        "threat_indicators": threat_indicators,
        "virustotal_summary": virustotal_summaries,
        "search_results": search_results,
        "search_queries": queries,
        "text_analysis": text_analysis_result,
        "model_claims": model_claims,
        "tool_results": tool_results,
        "tool_summary": {
            "total": len(tool_results),
            "success": sum(1 for item in tool_results if item.get("status") == "success"),
            "degraded": sum(1 for item in tool_results if item.get("status") == "degraded"),
            "failed": sum(1 for item in tool_results if item.get("status") == "failed"),
        },
        "degraded": degraded,
        "timestamp": _now(),
    }

    log("action", "正在调用 Kimi 进行情报归纳与溯源图谱解释")
    llm_analysis = await osint_interpret(partial_result, input_type, case_prompt, sample_refs)
    partial_result["llm_analysis"] = llm_analysis

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
        },
        "tool_results": {"osint": tool_results},
        "logs": logs,
        "timeline_events": [{
            "round": round_num,
            "agent": "osint",
            "event_type": "provenance_graph",
            "summary": f"图谱生成完成: {len(provenance_graph['nodes'])} 节点 / {len(provenance_graph['edges'])} 边",
        }],
    }
