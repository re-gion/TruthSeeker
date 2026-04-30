"""Challenger Agent - 阶段式逻辑质询 Agent。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.agents.state import AgentLog, TruthSeekerState
from app.agents.edges.conditions import evaluate_phase_convergence
from app.agents.tools.llm_client import build_sample_references, challenger_model_review
from app.services.audit_log import record_audit_event
from app.services.consultation_workflow import (
    build_timeline_event,
    build_consultation_context,
    evaluate_consultation_trigger,
    filter_human_consultation_messages,
    latest_human_consultation_messages,
)
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


def _merge_issues(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for issue in group:
            if not isinstance(issue, dict):
                continue
            issue_type = str(issue.get("type") or "model_challenge")
            description = str(issue.get("description") or issue.get("summary") or issue_type)
            severity = str(issue.get("severity") or "medium").lower()
            if severity not in {"high", "medium", "low"}:
                severity = "medium"
            agent = str(issue.get("agent") or "")
            key = (issue_type, description, agent)
            if key in seen:
                continue
            normalized = dict(issue)
            normalized.update({"type": issue_type, "description": description, "severity": severity})
            if agent:
                normalized["agent"] = agent
            seen.add(key)
            merged.append(normalized)
    return merged


def _normalize_target_agent(value: Any, fallback: str) -> str:
    if value in {"forensics", "osint", "commander"}:
        return str(value)
    return fallback if fallback in {"forensics", "osint", "commander"} else "forensics"


def _fetch_consultation_sessions(task_id: str) -> list[dict[str, Any]]:
    try:
        resp = (
            supabase.table("consultation_sessions")
            .select("*")
            .eq("task_id", task_id)
            .order("created_at", desc=False)
            .execute()
        )
        return [item for item in (resp.data or []) if isinstance(item, dict)]
    except Exception:
        return []


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
    max_rounds = min(int(state.get("max_rounds", 5) or 5), 5)
    threshold = float(state.get("convergence_threshold", 0.08) or 0.08)
    phase_rounds = dict(state.get("phase_rounds") or {"forensics": 1, "osint": 1, "commander": 1})
    phase_round = int(phase_rounds.get(phase, 1))
    quality_history = dict(state.get("phase_quality_history") or {"forensics": [], "osint": [], "commander": []})
    expert_messages = list(state.get("expert_messages") or [])
    consultation_sessions = list(state.get("consultation_sessions") or [])
    consultation_trigger_history = list(state.get("consultation_trigger_history") or [])
    active_consultation_session = state.get("active_consultation_session")
    pending_consultation_approval = state.get("pending_consultation_approval")
    confirmed_consultation_summary = state.get("confirmed_consultation_summary")
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
        db_sessions = _fetch_consultation_sessions(task_id)
        if db_sessions:
            consultation_sessions = db_sessions
        known_ids = {m.get("id") for m in expert_messages if isinstance(m, dict) and m.get("id")}
        resp = await asyncio.to_thread(
            lambda: supabase.table("consultation_messages").select("*").eq("task_id", task_id).order("created_at", desc=False).execute()
        )
        latest_messages = latest_human_consultation_messages(resp.data or [], consultation_sessions)
        new_messages = [m for m in latest_messages if m.get("id") not in known_ids]
        if new_messages:
            expert_messages.extend(new_messages)
            expert_messages = filter_human_consultation_messages(expert_messages)
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
    model_confidence = base_quality
    model_requires_more_evidence = False
    model_target_agent = phase
    model_issues: list[dict[str, Any]] = []
    model_residual_risks: list[dict[str, Any]] = []
    log("action", "调用 Kimi 多模态上下文进行逻辑交叉审查")
    try:
        model_review = await challenger_model_review(
            forensics,
            {**osint, "final_verdict": final_verdict if phase == "commander" else None},
            state.get("challenges") or [],
            case_prompt,
            sample_refs,
            phase=phase,
            phase_round=phase_round,
            base_confidence=base_quality,
            deterministic_issues=issues_found,
        )
        llm_cross_validation = str(model_review.get("markdown") or "")
        model_confidence = float(model_review.get("confidence", base_quality) or base_quality)
        model_requires_more_evidence = bool(model_review.get("requires_more_evidence"))
        model_target_agent = _normalize_target_agent(model_review.get("target_agent"), phase)
        model_issues = [issue for issue in (model_review.get("issues") or []) if isinstance(issue, dict)]
        model_residual_risks = [risk for risk in (model_review.get("residual_risks") or []) if isinstance(risk, dict)]
    except Exception as exc:
        llm_cross_validation = (
            "### 质询对象与本轮置信度\n"
            f"- 质询对象: {phase}\n"
            f"- 本轮置信度: {base_quality:.1%}\n\n"
            "### 主要质询点\n"
            f"- Kimi 逻辑审查异常: {type(exc).__name__}\n\n"
            "### 打回/放行建议\n"
            "- 使用代码侧硬门槛继续判定，并建议人工复核。\n\n"
            "### 收敛依据\n"
            f"- 异常详情: {exc}"
        )
        log("action", f"LLM 逻辑审查异常: {type(exc).__name__}")

    issues_found = _merge_issues(issues_found, model_issues)
    high = [issue for issue in issues_found if issue.get("severity") == "high"]
    medium = [issue for issue in issues_found if issue.get("severity") == "medium"]
    confidence = _score_issues(issues_found, base=model_confidence)
    quality_score = confidence
    previous_scores = list(quality_history.get(phase) or [])
    delta = _phase_delta(previous_scores, confidence)
    quality_history[phase] = previous_scores + [confidence]

    convergence = evaluate_phase_convergence(
        quality_delta=delta,
        confidence=confidence,
        round_count=phase_round,
        max_rounds=max_rounds,
        threshold=threshold,
    )
    maxed = bool(convergence.get("force_max_rounds"))
    phase_stable = bool(convergence.get("is_stable"))
    requires_more_evidence = (
        not maxed
        and (
            phase_round < 2
            or model_requires_more_evidence
            or (bool(high) and not phase_stable)
        )
    )
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
    if model_residual_risks:
        residual_risks.extend(model_residual_risks)

    if phase_stable and not high:
        log("action", f"质量变化 {delta:.3f} 小于阈值 {threshold:.3f}，置信度 {confidence:.1%}，阶段收敛")
    elif phase_round < 2 and not maxed:
        log("challenge", f"最少质询轮次未满足，继续打回 {model_target_agent or phase} 阶段复核")
    elif requires_more_evidence:
        log("challenge", f"模型建议或硬门槛要求补证，打回 {model_target_agent or phase} 阶段重审")
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
                "confidence": confidence,
                "requires_more_evidence": requires_more_evidence,
                "model_requires_more_evidence": model_requires_more_evidence,
                "model_target_agent": model_target_agent,
            },
        )

    target_agent = model_target_agent if requires_more_evidence else None
    if requires_more_evidence and phase_round < 2:
        target_agent = phase
    if phase == "commander" and requires_more_evidence:
        target_agent = "commander"

    challenge_record = {
        "round": round_num,
        "phase": phase,
        "phase_round": phase_round,
        "target_agent": target_agent or model_target_agent or phase,
        "confidence": confidence,
        "quality_delta": delta,
        "high_severity_count": len(high),
        "medium_severity_count": len(medium),
        "issues": issues_found,
        "timestamp": _now(),
    }
    if high or requires_more_evidence:
        consultation_trigger_history.append(challenge_record)

    db_sessions = _fetch_consultation_sessions(task_id)
    if db_sessions:
        consultation_sessions = db_sessions
    consultation_trigger = evaluate_consultation_trigger(
        consultation_trigger_history,
        existing_sessions=consultation_sessions,
    )
    consultation_required = bool(consultation_trigger.get("should_pause"))
    consultation_resumed = False
    consultation_resume_payload = None
    if consultation_required and interrupt is not None:
        event_type = str(consultation_trigger.get("event_type") or "consultation_required")
        context_payload = build_consultation_context(
            task_id=task_id,
            case_prompt=case_prompt,
            evidence_files=_all_evidence_files(state),
            forensics_result=forensics,
            osint_result=osint,
            challenger_feedback={"confidence": confidence, "issues_found": issues_found},
            trigger=consultation_trigger,
        )
        payload = {
            "type": event_type,
            "task_id": task_id,
            "round": round_num,
            "phase": phase,
            "target_agent": consultation_trigger.get("target_agent"),
            "repeat_index": consultation_trigger.get("repeat_index"),
            "requires_user_approval": consultation_trigger.get("requires_user_approval", False),
            "reason": consultation_trigger.get("reason") or (high[0].get("description") if high else "连续高质询触发会诊"),
            "issues": high,
            "case_prompt": case_prompt,
            "context": context_payload,
        }
        pending_consultation_approval = payload if event_type == "consultation_approval_required" else None
        active_consultation_session = payload if event_type == "consultation_required" else None
        consultation_resume_payload = interrupt(payload)
        consultation_resumed = True
        if isinstance(consultation_resume_payload, dict):
            resumed_messages = consultation_resume_payload.get("expert_messages")
            if isinstance(resumed_messages, list):
                expert_messages.extend(m for m in resumed_messages if isinstance(m, dict))
                expert_messages = filter_human_consultation_messages(expert_messages)
            resumed_sessions = consultation_resume_payload.get("consultation_sessions")
            if isinstance(resumed_sessions, list):
                consultation_sessions = [m for m in resumed_sessions if isinstance(m, dict)]
            summary = consultation_resume_payload.get("confirmed_consultation_summary")
            if isinstance(summary, dict):
                confirmed_consultation_summary = summary
                residual_risks.append({
                    "phase": phase,
                    "issue": {"type": "consultation_summary", "description": summary.get("confirmed_summary", "")},
                    "reason": "用户确认的会诊摘要已回注证据板",
                    "timestamp": _now(),
                })
            if consultation_resume_payload.get("action") in {"skip_consultation", "resume_after_consultation"}:
                requires_more_evidence = False
                target_agent = None
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
        "confidence": confidence,
        "satisfaction": confidence,
        "model_confidence": model_confidence,
        "model_requires_more_evidence": model_requires_more_evidence,
        "model_target_agent": model_target_agent,
        "quality_delta": delta,
        "convergence_threshold": threshold,
        "convergence_stable": phase_stable,
        "convergence_reason": convergence.get("reason"),
        "maxed_rounds": maxed,
        "residual_risks": residual_risks,
        "llm_cross_validation": llm_cross_validation,
        "consultation_required": consultation_required,
        "consultation_resumed": consultation_resumed,
        "consultation_resume_payload": consultation_resume_payload if isinstance(consultation_resume_payload, dict) else None,
        "consultation_event_type": consultation_trigger.get("event_type") if consultation_required else None,
        "consultation_trigger": consultation_trigger,
        "consultation_sessions": consultation_sessions,
        "consultation_trigger_history": consultation_trigger_history,
        "active_consultation_session": active_consultation_session,
        "pending_consultation_approval": pending_consultation_approval,
        "confirmed_consultation_summary": confirmed_consultation_summary,
        "timestamp": _now(),
    }

    if requires_more_evidence:
        phase_rounds[phase] = phase_round + 1

    log("conclusion", f"逻辑质询完成：phase={phase}，置信度 {confidence:.1%}，问题 {len(issues_found)} 个")
    record_audit_event(
        action="challenger.complete",
        task_id=task_id,
        agent="challenger",
        metadata={
            "phase": phase,
            "confidence": confidence,
            "issue_count": len(issues_found),
            "requires_more_evidence": requires_more_evidence,
            "model_requires_more_evidence": model_requires_more_evidence,
            "model_target_agent": model_target_agent,
        },
    )

    return {
        "analysis_phase": phase,
        "phase_rounds": phase_rounds,
        "phase_quality_history": quality_history,
        "phase_residual_risks": residual_risks,
        "consultation_sessions": consultation_sessions,
        "consultation_trigger_history": consultation_trigger_history,
        "active_consultation_session": active_consultation_session,
        "pending_consultation_approval": pending_consultation_approval,
        "confirmed_consultation_summary": confirmed_consultation_summary,
        "challenger_feedback": feedback,
        "challenges": challenges,
        "logs": logs,
        "timeline_events": [build_timeline_event(
            round_number=round_num,
            agent="challenger",
            event_type="phase_review",
            source_kind="agent",
            from_phase=phase,
            target_agent=target_agent or model_target_agent or phase,
            content=f"Challenger 质询 {phase}: 第 {phase_round} 轮，置信度 {confidence:.1%}",
            phase=phase,
            phase_round=phase_round,
            quality_score=quality_score,
            confidence=confidence,
            satisfaction=confidence,
            quality_delta=delta,
            requires_more_evidence=requires_more_evidence,
            model_requires_more_evidence=model_requires_more_evidence,
            model_target_agent=model_target_agent,
            maxed_rounds=maxed,
            consultation_event_type=consultation_trigger.get("event_type") if consultation_required else None,
        )],
        "expert_messages": expert_messages,
        "current_round": round_num + (1 if requires_more_evidence else 0),
    }
