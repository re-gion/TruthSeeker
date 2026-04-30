"""Forensics Agent - 电子取证 Agent，全模态取证鉴伪编排。"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable

import httpx

from app.agents.state import AgentLog, EvidenceItem, TruthSeekerState
from app.agents.tools.deepfake_api import analyze_media
from app.agents.tools.llm_client import build_sample_references, forensics_interpret
from app.agents.tools.threat_intel import analyze_urls, scan_file_hash
from app.config import settings
from app.services.audit_log import record_audit_event
from app.services.consultation_workflow import build_timeline_event
from app.services.text_validation import decode_text_bytes

logger = logging.getLogger(__name__)

MEDIA_MODALITIES = {"video", "audio", "image"}
TEXT_MAX_CHARS = 10000
TOOL_TIMEOUT_SECONDS = settings.FORENSICS_TOOL_TIMEOUT_SECONDS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_key(result: dict[str, Any]) -> tuple[str, str]:
    return str(result.get("tool", "")), str(result.get("target", ""))


def _extract_urls_from_text(text: str) -> list[str]:
    pattern = re.compile(r'https?://[^\s<>"\'\]\)}）】]+')
    return list(dict.fromkeys(pattern.findall(text or "")))


async def _read_text_sample(file_info: dict[str, Any]) -> dict[str, str]:
    url = file_info.get("file_url") or file_info.get("storage_path")
    if not isinstance(url, str) or not url or url.startswith("mock://"):
        return {"text": "", "encoding": "", "charset": ""}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return decode_text_bytes(resp.content, max_chars=TEXT_MAX_CHARS)


async def _settle_tool(
    *,
    tool: str,
    target: str,
    coro: Awaitable[dict[str, Any]],
    timeout: float = TOOL_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started_at = _now()
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        result = result if isinstance(result, dict) else {"value": result}
        status = "success"
        degraded = bool(result.get("degraded"))
        if tool == "virustotal_file_hash" and not result.get("scan_available") and not result.get("hash"):
            degraded = True
            result.setdefault("status", "unavailable")
        if result.get("status") in {"no_key", "error", "unavailable"}:
            degraded = True
        if degraded:
            status = "degraded"
        return {
            "tool": tool,
            "target": target,
            "status": status,
            "degraded": degraded,
            "result": result,
            "summary": _summarize_tool_result(tool, result),
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
            "summary": f"{tool} 超时，未取得检测结果",
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


def _summarize_tool_result(tool: str, result: dict[str, Any]) -> str:
    if tool == "reality_defender":
        if result.get("degraded") or not result.get("analysis_available", True):
            reason = (result.get("details") or {}).get("fallback_reason", "unavailable")
            return f"Reality Defender 未取得真实检测结论，降级原因={reason}"
        return (
            f"deepfake_probability={result.get('deepfake_probability', 0):.2f}, "
            f"confidence={result.get('confidence', 0):.2f}"
        )
    if tool == "virustotal_file_hash":
        return (
            f"hash={str(result.get('hash', ''))[:16]}, "
            f"malicious={result.get('malicious', 0)}, suspicious={result.get('suspicious', 0)}, "
            f"status={result.get('status', 'unknown')}"
        )
    if tool == "virustotal_text_ioc":
        vt = result.get("virustotal") or {}
        return f"threat_score={result.get('threat_score', 0):.2f}, malicious={vt.get('malicious', 0)}"
    return "工具完成"


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


def _previous_successes(state: TruthSeekerState) -> dict[tuple[str, str], dict[str, Any]]:
    previous = (state.get("tool_results") or {}).get("forensics")
    if not previous:
        previous = (state.get("forensics_result") or {}).get("tool_results") or []
    return {
        _tool_key(item): item
        for item in previous
        if isinstance(item, dict) and item.get("status") == "success"
    }


async def forensics_node(state: TruthSeekerState) -> dict:
    """
    电子取证 Agent：
    1. 接收所有模态检材和全局案件提示词；
    2. 媒体样本调用 Reality Defender，所有文件哈希和文本 IOC 调用 VirusTotal；
    3. 等待工具 all-settled 后，再交给 Kimi 多模态上下文生成取证报告。
    """
    task_id = state["task_id"]
    input_type = state.get("input_type", "text")
    case_prompt = state.get("case_prompt", "")
    round_num = state.get("current_round", 1)
    phase_rounds = dict(state.get("phase_rounds") or {"forensics": 1, "osint": 1, "commander": 1})
    phase_round = int(phase_rounds.get("forensics", 1))

    logs: list[AgentLog] = []
    timeline_events: list[dict] = []

    def log(log_type: str, content: str) -> None:
        logs.append({
            "agent": "forensics",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": _now(),
        })

    files = _all_evidence_files(state)
    sample_refs = build_sample_references(files)
    media_files = [item for item in files if item.get("modality") in MEDIA_MODALITIES]
    text_files = [item for item in files if item.get("modality") == "text"]

    log("thinking", f"电子取证Agent 启动，任务 ID: {task_id}")
    log("thinking", f"接收到 {len(files)} 个检材，媒体 {len(media_files)} 个，文本 {len(text_files)} 个")
    if case_prompt:
        log("thinking", f"全局检测目标: {case_prompt[:120]}")
    record_audit_event(
        action="forensics.start",
        task_id=task_id,
        agent="forensics",
        metadata={"round": round_num, "file_count": len(files), "media_count": len(media_files)},
    )

    previous_successes = _previous_successes(state)
    settled_results: list[dict[str, Any]] = []
    tool_tasks: list[Awaitable[dict[str, Any]]] = []

    def maybe_reuse(tool: str, target: str) -> bool:
        if phase_round <= 1:
            return False
        previous = previous_successes.get((tool, target))
        if previous:
            settled_results.append({**previous, "reused": True})
            return True
        return False

    for media in media_files:
        target = str(media.get("name") or media.get("file_url") or media.get("storage_path") or "media")
        url = str(media.get("file_url") or media.get("storage_path") or "")
        modality = str(media.get("modality") or input_type)
        if url and not maybe_reuse("reality_defender", target):
            tool_tasks.append(_settle_tool(
                tool="reality_defender",
                target=target,
                coro=analyze_media(url, modality),
            ))

    for item in files:
        target = str(item.get("name") or item.get("file_url") or item.get("storage_path") or "evidence")
        url = str(item.get("file_url") or item.get("storage_path") or "")
        if url and not maybe_reuse("virustotal_file_hash", target):
            tool_tasks.append(_settle_tool(
                tool="virustotal_file_hash",
                target=target,
                coro=scan_file_hash(url),
                timeout=60.0,
            ))

    text_urls: list[str] = []
    text_contents: list[dict[str, Any]] = []
    for item in text_files:
        try:
            decoded = await _read_text_sample(item)
            content = decoded.get("text", "")
            text_urls.extend(_extract_urls_from_text(content))
            text_contents.append({
                "name": str(item.get("name") or "text"),
                "content": content[:4000] if content else "",
                "detected_encoding": decoded.get("encoding"),
                "charset": decoded.get("charset"),
            })
        except Exception as exc:
            target = str(item.get("name") or "text")
            settled_results.append({
                "tool": "text_ioc_extract",
                "target": target,
                "status": "degraded",
                "degraded": True,
                "error": f"{type(exc).__name__}: {exc}",
                "summary": "文本检材读取失败，无法抽取 IOC",
                "completed_at": _now(),
            })

    for url in list(dict.fromkeys(text_urls)):
        if not maybe_reuse("virustotal_text_ioc", url):
            tool_tasks.append(_settle_tool(
                tool="virustotal_text_ioc",
                target=url,
                coro=analyze_urls([url]),
                timeout=45.0,
            ))

    if tool_tasks:
        log("action", f"启动 {len(tool_tasks)} 个外部/降级工具调用，等待 all-settled 结果")
        settled_results.extend(await asyncio.gather(*tool_tasks))
    else:
        log("action", "没有新增工具需要运行，复用上一轮已成功结果")

    rd_results = [
        item.get("result") or {}
        for item in settled_results
        if item.get("tool") == "reality_defender"
    ]
    rd_success_results = [
        item
        for item in rd_results
        if not item.get("degraded") and item.get("analysis_available", True)
    ]
    vt_results = [
        item.get("result") or {}
        for item in settled_results
        if str(item.get("tool", "")).startswith("virustotal")
    ]
    deepfake_prob = max([float(item.get("deepfake_probability", 0.0) or 0.0) for item in rd_success_results] or [0.0])
    rd_conf = max([float(item.get("confidence", 0.0) or 0.0) for item in rd_success_results] or [0.2])
    vt_threat = max([float(item.get("threat_score", 0.0) or 0.0) for item in vt_results] or [0.0])
    vt_malicious = sum(int(item.get("malicious", 0) or 0) for item in vt_results)

    is_deepfake = deepfake_prob > 0.5
    is_suspicious_ioc = vt_threat > 0.4 or vt_malicious > 0
    if rd_success_results:
        confidence = max(0.2, min(0.95, max(rd_conf, 0.55 + vt_threat * 0.25)))
    else:
        confidence = max(0.2, min(0.55, max(rd_conf, 0.35 + vt_threat * 0.30)))
    degraded = any(item.get("status") in {"degraded", "failed"} for item in settled_results)
    failed_count = sum(1 for item in settled_results if item.get("status") == "failed")
    degraded_count = sum(1 for item in settled_results if item.get("status") == "degraded")
    degradation_level = "failed" if failed_count else "degraded" if degraded_count else "ok"
    if degraded:
        degradation_details = [
            {
                "tool": item.get("tool", "unknown"),
                "target": str(item.get("target", ""))[:80],
                "status": item.get("status", "unknown"),
                "error": str(item.get("error", ""))[:120] if item.get("error") else None,
                "summary": str(item.get("summary", ""))[:120],
            }
            for item in settled_results
            if item.get("status") in {"degraded", "failed"}
        ]
        record_audit_event(
            action="forensics.degraded",
            task_id=task_id,
            agent="forensics",
            metadata={
                "failed": failed_count,
                "degraded": degraded_count,
                "total": len(settled_results),
                "details": degradation_details,
            },
        )

    indicators: list[str] = []
    for item in settled_results:
        if item.get("summary"):
            indicators.append(str(item["summary"]))
    if is_suspicious_ioc:
        indicators.append("VirusTotal/IOC 结果提示潜在威胁线索")

    raw_forensics = {
        "tool_matrix": settled_results,
        "is_deepfake": is_deepfake,
        "deepfake_probability": deepfake_prob,
        "confidence": confidence,
        "vt_threat_score": vt_threat,
        "is_suspicious_ioc": is_suspicious_ioc,
        "sample_refs": sample_refs,
        "degraded": degraded,
        "text_samples": text_contents,
    }

    log("action", "工具结果已全部返回，开始 Kimi 多模态取证推理")
    llm_analysis = await forensics_interpret(raw_forensics, input_type, case_prompt, sample_refs, text_contents=text_contents)
    log("finding", f"电子取证报告生成完成，工具结果 {len(settled_results)} 条")

    forensics_score = confidence
    result = {
        "is_deepfake": is_deepfake,
        "deepfake_probability": deepfake_prob,
        "confidence": confidence,
        "forensics_score": forensics_score,
        "model_used": "reality_defender+virustotal+kimi-k2.5",
        "model_scores": rd_success_results[:5],
        "degraded_model_scores": [item for item in rd_results if item.get("degraded")][:5],
        "frame_inferences_count": sum(len(item.get("frame_inferences") or []) for item in rd_success_results),
        "audio_score": next((item.get("audio_score") for item in rd_success_results if item.get("audio_score") is not None), None),
        "indicators": indicators[:8],
        "tool_results": settled_results,
        "tool_summary": {
            "total": len(settled_results),
            "success": sum(1 for item in settled_results if item.get("status") == "success"),
            "degraded": degraded_count,
            "failed": failed_count,
            "reused": sum(1 for item in settled_results if item.get("reused")),
        },
        "sample_refs": sample_refs,
        "degraded": degraded,
        "degradation_status": degradation_level,
        "llm_analysis": llm_analysis,
        "timestamp": _now(),
    }

    evidence_item: EvidenceItem = {
        "type": "forensics",
        "source": "forensics_agent",
        "description": (
            f"电子取证：伪造概率 {deepfake_prob:.1%}，VT 威胁评分 {vt_threat:.1%}，"
            f"工具成功 {result['tool_summary']['success']}/{len(settled_results)}"
        ),
        "confidence": confidence,
        "metadata": {
            "is_deepfake": is_deepfake,
            "is_suspicious_ioc": is_suspicious_ioc,
            "tool_summary": result["tool_summary"],
            "indicators": indicators[:8],
        },
    }

    confidence_history = list(state.get("confidence_history", []))
    confidence_history.append({"round": round_num, "scores": {"forensics": forensics_score}})

    timeline_events.append(build_timeline_event(
        round_number=round_num,
        agent="forensics",
        event_type="analysis_complete",
        source_kind="agent",
        from_phase="forensics",
        target_agent="challenger",
        content=f"电子取证完成: 伪造概率 {deepfake_prob:.1%}, 置信度 {confidence:.1%}",
    ))
    record_audit_event(
        action="forensics.complete",
        task_id=task_id,
        agent="forensics",
        metadata={
            "deepfake_probability": deepfake_prob,
            "degraded": degraded,
            "tool_success": result["tool_summary"]["success"],
            "tool_total": len(settled_results),
        },
    )
    log("conclusion", "电子取证报告已写入全局证据板，等待逻辑质询Agent审查")

    return {
        "analysis_phase": "forensics",
        "phase_rounds": phase_rounds,
        "forensics_result": result,
        "evidence_board": [evidence_item],
        "confidence_history": confidence_history,
        "logs": logs,
        "timeline_events": timeline_events,
        "degradation_status": {
            "reality_defender": "degraded" if any(r.get("tool") == "reality_defender" and r.get("degraded") for r in settled_results) else "ok",
            "virustotal": "degraded" if any(str(r.get("tool", "")).startswith("virustotal") and r.get("degraded") for r in settled_results) else "ok",
        },
        "tool_results": {"forensics": settled_results},
    }
