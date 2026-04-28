"""Challenger Agent - 阶段式逻辑质询 Agent。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.agents.state import AgentLog, TruthSeekerState
from app.agents.tools.llm_client import build_sample_references, challenger_cross_validate
from app.services.audit_log import record_audit_event
from app.utils.supabase_client import supabase

try:
    from langgraph.types import interrupt
except ImportError:  # pragma: no cover
    interrupt = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _all_evidence_files(state: TruthSeekerState) -> list[dict[str, Any]]:
    return [dict(item) for item in (state.get("evidence_files") or []) if isinstance(item, dict)]


def _next_phase(phase: str) -> str:
    return {"forensics": "osint", "osint": "commander", "commander": "complete"}.get(phase, "osint")


def _issue(issue_type: str, description: str, severity: str, *, agent: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": issue_type,
        "description": description,
        "severity": severity,
    }
    if agent:
        payload["agent"] = agent
    return payload


def _score_issues(issues: list[dict[str, Any]], base: float = 1.0) -> float:
    score = base
    for issue in issues:
        severity = issue.get("severity")
        if severity == "high":
            score -= 0.30
        elif severity == "medium":
            score -= 0.15
        else:
            score -= 0.05
    return max(0.0, min(1.0, score))


def _phase_delta(history: list[float], current: float) -> float | None:
    if not history:
        return None
    return abs(float(history[-1]) - float(current))


def _forensics_issues(forensics: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    confidence = float(forensics.get("confidence", 0.0) or 0.0)
    tool_summary = forensics.get("tool_summary") or {}
    failed = int(tool_summary.get("failed", 0) or 0)
    degraded = int(tool_summary.get("degraded", 0) or 0)
    total = int(tool_summary.get("total", 0) or 0)

    if not forensics:
        issues.append(_issue("missing_forensics", "电子取证报告缺失，无法进入情报溯源阶段", "high", agent="forensics"))
    if total == 0:
        issues.append(_issue("missing_tool_matrix", "电子取证未形成工具矩阵，不能证明已等待外部工具结果", "high", agent="forensics"))
    if failed > 0:
        issues.append(_issue("tool_failed", f"电子取证有 {failed} 个工具调用失败，需要重跑或记录风险", "high", agent="forensics"))
    if degraded > 0:
        issues.append(_issue("tool_degraded", f"电子取证有 {degraded} 个工具降级，结论可靠性下降", "medium", agent="forensics"))
    if confidence < 0.55:
        issues.append(_issue("low_confidence", f"电子取证置信度偏低（{confidence:.1%}）", "high", agent="forensics"))
    return issues


def _osint_issues(osint: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    graph = osint.get("provenance_graph") or {}
    quality = graph.get("quality") or {}
    citation_coverage = float(quality.get("citation_coverage", 0.0) or 0.0)
    inferred_ratio = float(quality.get("model_inferred_ratio", 0.0) or 0.0)
    nodes = graph.get("nodes") or []
    citations = graph.get("citations") or []
    tool_summary = osint.get("tool_summary") or {}
    failed = int(tool_summary.get("failed", 0) or 0)
    degraded = int(tool_summary.get("degraded", 0) or 0)
    total = int(tool_summary.get("total", 0) or 0)

    if not osint:
        issues.append(_issue("missing_osint", "情报溯源报告缺失，无法进入最终研判阶段", "high", agent="osint"))
    if not graph:
        issues.append(_issue("missing_graph", "情报溯源图谱缺失", "high", agent="osint"))
    if len(nodes) < 3:
        issues.append(_issue("thin_graph", "图谱节点过少，实体、来源或声明不足", "medium", agent="osint"))
    if not citations:
        issues.append(_issue("missing_citations", "图谱缺少引用来源，不能支撑外部事实", "high", agent="osint"))
    elif citation_coverage < 0.25:
        issues.append(_issue("low_citation_coverage", f"图谱引用覆盖率偏低（{citation_coverage:.1%}）", "medium", agent="osint"))
    if inferred_ratio > 0.65:
        issues.append(_issue("too_many_model_inferred_edges", f"模型推断关系占比过高（{inferred_ratio:.1%}）", "medium", agent="osint"))
    if total == 0:
        issues.append(_issue("missing_osint_tool_matrix", "情报溯源未形成工具矩阵，不能证明已等待外部工具结果", "high", agent="osint"))
    if failed > 0:
        issues.append(_issue("osint_tool_failed", f"情报溯源有 {failed} 个工具调用失败，需要重跑或记录风险", "high", agent="osint"))
    if degraded > 0:
        issues.append(_issue("osint_tool_degraded", f"情报溯源有 {degraded} 个工具降级，结论可靠性下降", "medium", agent="osint"))
    return issues


def _commander_issues(final_verdict: dict[str, Any], provenance_graph: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    verdict = final_verdict.get("verdict")
    confidence = float(final_verdict.get("confidence", 0.0) or 0.0)
    recommendations = final_verdict.get("recommendations") or []

    if verdict not in {"authentic", "suspicious", "forged", "inconclusive"}:
        issues.append(_issue("invalid_verdict", "最终裁决未使用兼容枚举", "high", agent="commander"))
    if not provenance_graph:
        issues.append(_issue("missing_final_graph", "最终报告未携带审定版 provenance_graph", "high", agent="commander"))
    if confidence < 0.35 and verdict != "inconclusive":
        issues.append(_issue("overconfident_verdict", "低置信证据不应给出确定性裁决", "high", agent="commander"))
    if not recommendations:
        issues.append(_issue("missing_recommendations", "最终报告缺少后续处置建议", "medium", agent="commander"))
    return issues


async def challenger_node(state: TruthSeekerState) -> dict:
    """
    逻辑质询 Agent：
    - Forensics 阶段审查工具矩阵和取证报告；
    - OSINT 阶段审查图谱节点、关系、引用和模型推断标记；
    - Commander 阶段只审查最终报告，不重新打开取证/OSINT 工具链。
    """
    task_id = state["task_id"]
    phase = state.get("analysis_phase") or "forensics"
    round_num = state.get("current_round", 1)
    max_rounds = int(state.get("max_rounds", 3) or 3)
    threshold = float(state.get("convergence_threshold", 0.08) or 0.08)
    phase_rounds = dict(state.get("phase_rounds") or {"forensics": 1, "osint": 1, "commander": 1})
    phase_round = int(phase_rounds.get(phase, 1))
    quality_history = dict(state.get("phase_quality_history") or {"forensics": [], "osint": [], "commander": []})
    expert_messages = list(state.get("expert_messages") or [])
    sample_refs = build_sample_references(_all_evidence_files(state))
    case_prompt = state.get("case_prompt", "")

    logs: list[AgentLog] = []
    challenges: list[dict[str, Any]] = []

    def log(log_type: str, content: str) -> None:
        logs.append({
            "agent": "challenger",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": _now(),
        })

    log("thinking", f"逻辑质询Agent 启动：phase={phase}, phase_round={phase_round}/{max_rounds}")
    if case_prompt:
        log("thinking", f"全局检测目标: {case_prompt[:120]}")
    record_audit_event(
        action="challenger.start",
        task_id=task_id,
        agent="challenger",
        metadata={"phase": phase, "phase_round": phase_round},
    )

    try:
        known_ids = {m.get("id") for m in expert_messages if isinstance(m, dict) and m.get("id")}
        resp = await asyncio.to_thread(
            lambda: supabase.table("consultation_messages").select("*").eq("task_id", task_id).order("created_at", desc=False).execute()
        )
        new_messages = [m for m in (resp.data or []) if m.get("id") not in known_ids]
        if new_messages:
            expert_messages.extend(new_messages)
            log("thinking", f"纳入 {len(new_messages)} 条新增专家意见")
    except Exception as exc:
        log("action", f"读取专家意见失败，继续自动质询: {type(exc).__name__}")

    forensics = state.get("forensics_result") or {}
    osint = state.get("osint_result") or {}
    final_verdict = state.get("final_verdict") or {}
    provenance_graph = state.get("provenance_graph") or osint.get("provenance_graph") or final_verdict.get("provenance_graph") or {}

    if phase == "forensics":
        issues_found = _forensics_issues(forensics)
        base_quality = float(forensics.get("confidence", 0.5) or 0.5)
    elif phase == "osint":
        issues_found = _osint_issues(osint)
        graph_quality = (provenance_graph.get("quality") or {}).get("completeness", 0.5) if isinstance(provenance_graph, dict) else 0.5
        base_quality = float(graph_quality or osint.get("confidence", 0.5) or 0.5)
    else:
        issues_found = _commander_issues(final_verdict, provenance_graph if isinstance(provenance_graph, dict) else {})
        base_quality = float(final_verdict.get("quality_score", final_verdict.get("confidence", 0.5)) or 0.5)

    llm_cross_validation = ""
    log("action", "调用 Kimi 多模态上下文进行逻辑交叉审查")
    try:
        llm_cross_validation = await challenger_cross_validate(
            forensics,
            {**osint, "final_verdict": final_verdict if phase == "commander" else None},
            state.get("challenges") or [],
            case_prompt,
            sample_refs,
        )
        if any(keyword in llm_cross_validation for keyword in ["矛盾", "冲突", "不一致"]):
            issues_found.append(_issue(
                "llm_logic_challenge",
                "LLM 逻辑审查提示存在潜在矛盾或不一致",
                "medium",
                agent=phase,
            ))
    except Exception as exc:
        llm_cross_validation = f"[降级模式: LLM不可用] 逻辑审查异常: {exc}"
        log("action", f"LLM 逻辑审查异常: {type(exc).__name__}")

    high = [issue for issue in issues_found if issue.get("severity") == "high"]
    medium = [issue for issue in issues_found if issue.get("severity") == "medium"]
    quality_score = _score_issues(issues_found, base=base_quality)
    previous_scores = list(quality_history.get(phase) or [])
    delta = _phase_delta(previous_scores, quality_score)
    quality_history[phase] = previous_scores + [quality_score]

    maxed = phase_round >= max_rounds
    requires_more_evidence = bool(high) and not maxed
    residual_risks: list[dict[str, Any]] = []
    if bool(high) and maxed:
        residual_risks = [
            {
                "phase": phase,
                "issue": issue,
                "reason": "阶段达到最大轮次，继续推进并写入残留风险",
                "timestamp": _now(),
            }
            for issue in high
        ]

    if delta is not None and delta < threshold and not high:
        log("action", f"质量变化 {delta:.3f} 小于阈值 {threshold:.3f}，阶段收敛")
    elif requires_more_evidence:
        log("challenge", f"发现 {len(high)} 个高严重度问题，打回 {phase} 阶段重审")
    elif high and maxed:
        log("challenge", f"{phase} 阶段达到最大轮次，保留 {len(high)} 个高风险问题并继续推进")
    elif issues_found:
        log("action", f"记录 {len(issues_found)} 个非阻断问题，阶段继续推进")
    else:
        log("action", "审查通过，无阻断问题")

    if issues_found:
        record_audit_event(
            action="challenger.issues_found",
            task_id=task_id,
            agent="challenger",
            metadata={
                "phase": phase,
                "high": len(high),
                "medium": len(medium),
                "quality_score": quality_score,
                "requires_more_evidence": requires_more_evidence,
            },
        )

    consultation_required = bool(phase == "forensics" and phase_round == 1 and high)
    consultation_resumed = False
    consultation_resume_payload = None
    if consultation_required and interrupt is not None:
        payload = {
            "type": "consultation_required",
            "task_id": task_id,
            "round": round_num,
            "phase": phase,
            "reason": high[0].get("description", "电子取证阶段存在高严重度问题"),
            "issues": high,
            "case_prompt": case_prompt,
        }
        consultation_resume_payload = interrupt(payload)
        consultation_resumed = True
        if isinstance(consultation_resume_payload, dict):
            resumed_messages = consultation_resume_payload.get("expert_messages")
            if isinstance(resumed_messages, list):
                expert_messages.extend(m for m in resumed_messages if isinstance(m, dict))
            log("thinking", f"会诊已恢复，恢复指令: {consultation_resume_payload.get('action', 'resume')}")
    elif consultation_required:
        log("action", "当前 LangGraph 运行时不可用 interrupt，继续自动重审/推进")

    for issue in issues_found:
        challenges.append({
            "round": round_num,
            "phase": phase,
            "issue": issue,
            "timestamp": _now(),
        })

    target_agent = phase if requires_more_evidence else None
    if phase == "commander" and requires_more_evidence:
        target_agent = "commander"

    feedback = {
        "round": round_num,
        "phase": phase,
        "phase_round": phase_round,
        "next_phase": phase if requires_more_evidence else _next_phase(phase),
        "issues_found": issues_found,
        "requires_more_evidence": requires_more_evidence,
        "target_agent": target_agent,
        "issue_count": len(issues_found),
        "high_severity_count": len(high),
        "medium_severity_count": len(medium),
        "quality_score": quality_score,
        "quality_delta": delta,
        "convergence_threshold": threshold,
        "maxed_rounds": maxed,
        "residual_risks": residual_risks,
        "llm_cross_validation": llm_cross_validation,
        "consultation_required": consultation_required,
        "consultation_resumed": consultation_resumed,
        "consultation_resume_payload": consultation_resume_payload if isinstance(consultation_resume_payload, dict) else None,
        "timestamp": _now(),
    }

    if requires_more_evidence:
        phase_rounds[phase] = phase_round + 1

    log("conclusion", f"逻辑质询完成：phase={phase}，质量 {quality_score:.1%}，问题 {len(issues_found)} 个")
    record_audit_event(
        action="challenger.complete",
        task_id=task_id,
        agent="challenger",
        metadata={
            "phase": phase,
            "quality_score": quality_score,
            "issue_count": len(issues_found),
            "requires_more_evidence": requires_more_evidence,
        },
    )

    return {
        "analysis_phase": phase,
        "phase_rounds": phase_rounds,
        "phase_quality_history": quality_history,
        "phase_residual_risks": residual_risks,
        "challenger_feedback": feedback,
        "challenges": challenges,
        "logs": logs,
        "expert_messages": expert_messages,
        "current_round": round_num + (1 if requires_more_evidence else 0),
    }
