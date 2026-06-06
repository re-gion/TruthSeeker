"""Challenger Agent - 阶段式逻辑质询 Agent。"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.agents.state import AgentLog, TruthSeekerState
from app.agents.edges.conditions import evaluate_phase_convergence
from app.agents.tools.llm_client import (
    build_sample_references,
    challenger_model_review,
    commander_dedupe_consultation_context,
)
from app.services.audit_log import record_audit_event
from app.services.consultation_workflow import (
    build_timeline_event,
    build_consultation_context,
    evaluate_consultation_trigger,
    filter_human_consultation_messages,
    latest_human_consultation_messages,
)
from app.services.experience_library import experience_rag_search
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


def _evidence_confidence_floor(forensics: dict[str, Any], osint: dict[str, Any], phase: str) -> float:
    floor = 0.0
    aigc_probability = float(forensics.get("aigc_probability", forensics.get("deepfake_probability", 0.0)) or 0.0)
    forensics_confidence = float(forensics.get("confidence", 0.0) or 0.0)
    if aigc_probability >= 0.9 and forensics_confidence >= 0.7:
        floor = max(floor, 0.58)
    elif aigc_probability >= 0.75 and forensics_confidence >= 0.6:
        floor = max(floor, 0.48)

    vt_score = float(forensics.get("vt_threat_score", osint.get("threat_score", 0.0)) or 0.0)
    threat_score = float(osint.get("threat_score", 0.0) or 0.0)
    if max(vt_score, threat_score) >= 0.75:
        floor = max(floor, 0.58)

    text_risk_score = float(osint.get("text_risk_score", 0.0) or 0.0)
    social_engineering_score = float(osint.get("social_engineering_score", 0.0) or 0.0)
    if max(text_risk_score, social_engineering_score) >= 0.7:
        floor = max(floor, 0.50)

    graph = osint.get("provenance_graph") or {}
    if isinstance(graph, dict):
        nodes = graph.get("nodes") or []
        citations = graph.get("citations") or []
        if len(nodes) >= 3 and citations:
            floor = max(floor, 0.45)

    if phase == "commander" and forensics_confidence >= 0.7 and threat_score >= 0.7:
        floor = max(floor, 0.55)
    return min(0.65, floor)


def _apply_evidence_floor(
    confidence: float,
    evidence_floor: float,
    high: list[dict[str, Any]],
    medium: list[dict[str, Any]],
) -> float:
    if evidence_floor <= 0 or confidence >= evidence_floor:
        return confidence
    gap_penalty = min(0.14, len(high) * 0.06 + len(medium) * 0.03)
    return max(confidence, evidence_floor - gap_penalty)


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


def _issue_target_agent(issue: dict[str, Any]) -> str:
    return str(issue.get("agent") or issue.get("target_agent") or "").strip()


def _current_phase_issues(issues: list[dict[str, Any]], phase: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    cross_phase: list[dict[str, Any]] = []
    for issue in issues:
        target = _issue_target_agent(issue)
        if target and target != phase:
            cross_phase.append(issue)
            continue
        normalized = dict(issue)
        normalized["agent"] = phase
        current.append(normalized)
    return current, cross_phase


def _fetch_consultation_sessions(task_id: str) -> list[dict[str, Any]]:
    for table_name in ("collaboration_sessions", "consultation_sessions"):
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
            rows = [item for item in (resp.data or []) if isinstance(item, dict)]
            if rows:
                return rows
        except Exception:
            continue
    return []


def _fetch_collaboration_messages(task_id: str) -> list[dict[str, Any]]:
    for table_name in ("collaboration_messages", "consultation_messages"):
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
            rows = [item for item in (resp.data or []) if isinstance(item, dict)]
            if rows:
                return rows
        except Exception:
            continue
    return []


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


def _resume_consultation_context(
    expert_messages: list[dict[str, Any]],
    confirmed_summary: Any,
) -> dict[str, Any] | None:
    if not expert_messages and not confirmed_summary:
        return None
    return {
        "type": "human_collaboration",
        "expert_messages": expert_messages,
        "confirmed_summary": confirmed_summary,
    }


def _collaboration_release_decision(
    confirmed_summary: Any,
    expert_messages: list[dict[str, Any]],
    resume_payload: Any,
) -> tuple[bool, str | None]:
    """Return whether human collaboration explicitly allows release below threshold."""
    texts: list[str] = []
    if isinstance(confirmed_summary, dict):
        for key in ("confirmed_summary", "user_confirmed_summary", "generated_summary", "summary"):
            value = confirmed_summary.get(key)
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
    elif isinstance(confirmed_summary, str) and confirmed_summary.strip():
        texts.append(confirmed_summary.strip())

    for message in expert_messages[-5:]:
        if not isinstance(message, dict):
            continue
        value = message.get("message") or message.get("content") or message.get("text")
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())

    action = resume_payload.get("action") if isinstance(resume_payload, dict) else None
    if action == "skip_consultation":
        return True, "用户在人机协同审批中选择跳过本次重复协同，允许带残留风险继续推进"

    joined = "\n".join(texts)
    if not joined:
        return False, None
    reinforce_markers = ("打回", "补强", "继续调查", "进一步核验", "继续补证", "不应放行")
    release_markers = ("可以放行", "允许放行", "继续推进", "不要再强求", "能力上限", "工具上限", "无法获得更多证据", "带残留风险")
    if any(marker in joined for marker in reinforce_markers):
        return False, None
    if any(marker in joined for marker in release_markers):
        return True, "人机协同意见认为目标 Agent 已触及当前工具/证据能力上限，允许带残留风险放行"
    return False, None


def _experience_query(*, phase: str, case_prompt: str, issues: list[dict[str, Any]], llm_cross_validation: str) -> str:
    issue_text = "；".join(
        str(item.get("description") or item.get("summary") or item.get("type") or "")
        for item in issues[:5]
        if isinstance(item, dict)
    )
    return "\n".join([
        f"agent={phase}",
        f"case_prompt={case_prompt}",
        f"issues={issue_text}",
        f"challenger_review={llm_cross_validation[:1200]}",
    ])


def _phase_already_experience_assisted(state: TruthSeekerState, phase: str) -> bool:
    feedback = state.get("challenger_feedback") or {}
    if feedback.get("phase") == phase and feedback.get("experience_assisted"):
        return True
    for item in state.get("collaboration_trigger_history") or state.get("consultation_trigger_history") or []:
        if isinstance(item, dict) and item.get("phase") == phase and item.get("experience_assisted"):
            return True
    return False


def _should_suppress_issue_by_experience(issue: dict[str, Any], matches: list[dict[str, Any]]) -> bool:
    issue_text = str(issue.get("description") or issue.get("summary") or issue.get("type") or "")
    issue_tokens = set(re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]", issue_text.lower()))
    if not issue_tokens:
        return False
    for match in matches:
        text = " ".join(str(match.get(key) or "") for key in ("title", "chunk_text", "snippet"))
        if not text:
            continue
        lowered = text.lower()
        if not any(marker in text for marker in ("不用", "不必", "无需", "不再", "可以不")):
            continue
        if not any(marker in text for marker in ("质询", "打回", "补强", "作为质询点")):
            continue
        match_tokens = set(re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]", lowered))
        overlap = len(issue_tokens & match_tokens) / max(1, min(len(issue_tokens), 24))
        if overlap >= 0.18:
            return True
    return False


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
    elif citation_coverage < 0.60:
        issues.append(_issue("low_citation_coverage", f"图谱引用覆盖率偏低（{citation_coverage:.1%}，低于 60% 门槛）", "medium", agent="osint"))
    if inferred_ratio > 0.35:
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
    consultation_sessions = list(state.get("collaboration_sessions") or state.get("consultation_sessions") or [])
    consultation_trigger_history = list(state.get("collaboration_trigger_history") or state.get("consultation_trigger_history") or [])
    active_consultation_session = state.get("active_collaboration_session") or state.get("active_consultation_session")
    pending_consultation_approval = state.get("pending_collaboration_approval") or state.get("pending_consultation_approval")
    confirmed_consultation_summary = state.get("confirmed_collaboration_summary") or state.get("confirmed_consultation_summary")
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

    resume_payload_from_state = state.get("collaboration_resume") or state.get("consultation_resume")
    if isinstance(resume_payload_from_state, dict):
        resumed_messages = resume_payload_from_state.get("expert_messages")
        if isinstance(resumed_messages, list):
            expert_messages.extend(m for m in resumed_messages if isinstance(m, dict))
            expert_messages = filter_human_consultation_messages(expert_messages)
        resumed_sessions = resume_payload_from_state.get("collaboration_sessions") or resume_payload_from_state.get("consultation_sessions")
        if isinstance(resumed_sessions, list):
            consultation_sessions = [m for m in resumed_sessions if isinstance(m, dict)]
        summary = resume_payload_from_state.get("confirmed_collaboration_summary") or resume_payload_from_state.get("confirmed_consultation_summary")
        if isinstance(summary, dict):
            summary.setdefault("phase", phase)
            summary.setdefault("target_agent", phase)
            confirmed_consultation_summary = summary
        if expert_messages or confirmed_consultation_summary:
            log("thinking", "已从恢复载荷纳入用户/专家意见与协同摘要")

    try:
        db_sessions = _fetch_consultation_sessions(task_id)
        if db_sessions:
            consultation_sessions = db_sessions
        known_ids = {m.get("id") for m in expert_messages if isinstance(m, dict) and m.get("id")}
        latest_messages = latest_human_consultation_messages(
            await asyncio.to_thread(lambda: _fetch_collaboration_messages(task_id)),
            consultation_sessions,
        )
        new_messages = [m for m in latest_messages if m.get("id") not in known_ids]
        if new_messages:
            expert_messages.extend(new_messages)
            expert_messages = filter_human_consultation_messages(expert_messages)
            log("thinking", f"纳入 {len(new_messages)} 条新增用户/专家协同意见")
    except Exception as exc:
        if expert_messages or confirmed_consultation_summary:
            log("action", f"读取协同意见补充失败，已使用恢复载荷继续质询: {type(exc).__name__}")
        else:
            log("action", f"读取协同意见失败，继续自动质询: {type(exc).__name__}")

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
    review_challenges = list(state.get("challenges") or [])
    human_context = _resume_consultation_context(expert_messages, confirmed_consultation_summary)
    if human_context:
        review_challenges.append(human_context)
    log("action", "调用 Kimi 多模态上下文进行逻辑交叉审查")
    try:
        model_review = await challenger_model_review(
            forensics,
            {**osint, "final_verdict": final_verdict if phase == "commander" else None},
            review_challenges,
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
    challenger_experience = await experience_rag_search(
        query=_experience_query(
            phase="challenger",
            case_prompt=case_prompt,
            issues=issues_found,
            llm_cross_validation=llm_cross_validation,
        ),
        user_id=str(state.get("user_id") or ""),
        agent="challenger",
    )
    suppressed_issues = [
        issue for issue in issues_found
        if _should_suppress_issue_by_experience(issue, challenger_experience.get("matches") or [])
    ]
    if suppressed_issues:
        suppressed_ids = {id(issue) for issue in suppressed_issues}
        issues_found = [issue for issue in issues_found if id(issue) not in suppressed_ids]
        model_requires_more_evidence = False if not issues_found else model_requires_more_evidence
        log("thinking", f"个人经验库命中，压低 {len(suppressed_issues)} 个冗余质询点")
        record_audit_event(
            action="experience_rag.guided_challenger",
            task_id=task_id,
            agent="challenger",
            metadata={
                "phase": phase,
                "suppressed_issue_count": len(suppressed_issues),
                "match_count": len(challenger_experience.get("matches") or []),
            },
        )
    issues_found, cross_phase_issues = _current_phase_issues(issues_found, phase)
    if cross_phase_issues:
        model_requires_more_evidence = False
        model_target_agent = phase
        log("thinking", f"忽略 {len(cross_phase_issues)} 个跨阶段质询点，当前仅审查 {phase} 阶段")
    high = [issue for issue in issues_found if issue.get("severity") == "high"]
    medium = [issue for issue in issues_found if issue.get("severity") == "medium"]
    # The LLM confidence is already a review score. Deterministic issues cap it,
    # rather than subtracting the same issue twice.
    confidence = min(model_confidence, _score_issues(issues_found, base=1.0))
    confidence = _apply_evidence_floor(
        confidence,
        _evidence_confidence_floor(forensics, osint, phase),
        high,
        medium,
    )
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
    satisfaction_threshold = float(settings.CHALLENGER_SATISFACTION_THRESHOLD)
    low_confidence = confidence < satisfaction_threshold
    blocking_issues = bool(high) or model_requires_more_evidence
    collaboration_release, collaboration_release_reason = _collaboration_release_decision(
        confirmed_consultation_summary,
        expert_messages,
        resume_payload_from_state,
    )
    threshold_release = not low_confidence and not blocking_issues
    max_rounds_release = bool(maxed)
    requires_more_evidence = not maxed and not threshold_release and not collaboration_release
    residual_risks: list[dict[str, Any]] = []
    if maxed and (issues_found or low_confidence):
        maxed_issues = issues_found or [
            _issue(
                "low_confidence_max_rounds",
                f"逻辑质询置信度 {confidence:.1%} 仍低于 {satisfaction_threshold:.0%}，但阶段达到第 {max_rounds} 轮上限",
                "medium",
                agent=phase,
            )
        ]
        residual_risks = [
            {
                "phase": phase,
                "issue": issue,
                "reason": "轮次上限放行：阶段达到最大轮次，继续推进并写入残留风险",
                "timestamp": _now(),
            }
            for issue in maxed_issues
        ]
    if model_residual_risks:
        residual_risks.extend(model_residual_risks)
    if collaboration_release and (low_confidence or issues_found):
        residual_risks.append({
            "phase": phase,
            "issue": {
                "type": "collaboration_release_below_threshold",
                "description": f"人机协同后仍有低置信或未完全解决问题，置信度 {confidence:.1%}",
            },
            "reason": collaboration_release_reason or "人机协同意见允许放行",
            "timestamp": _now(),
        })

    if max_rounds_release:
        log("challenge", f"{phase} 阶段达到第 {max_rounds} 轮上限，低置信或未解决问题将作为残留风险放行")
    elif collaboration_release:
        log("action", collaboration_release_reason or "人机协同意见允许带残留风险放行")
    elif requires_more_evidence and low_confidence:
        log("challenge", f"置信度 {confidence:.1%} 低于 {satisfaction_threshold:.0%} 门槛，打回 {phase} 阶段补强")
    elif phase_stable and not high:
        log("action", f"质量变化 {delta:.3f} 小于阈值 {threshold:.3f}，置信度 {confidence:.1%}，阶段收敛")
    elif threshold_release:
        log("action", f"置信度 {confidence:.1%} 超过放行阈值且无阻断高危问题，阶段继续推进")
    elif requires_more_evidence:
        log("challenge", f"模型建议或硬门槛要求补证，打回 {phase} 阶段重审")
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

    target_agent = phase if requires_more_evidence else None
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
    if issues_found or requires_more_evidence or low_confidence:
        consultation_trigger_history.append(challenge_record)

    db_sessions = _fetch_consultation_sessions(task_id)
    if db_sessions:
        consultation_sessions = db_sessions
    current_phase_trigger_history = [
        item for item in consultation_trigger_history
        if isinstance(item, dict) and item.get("phase") == phase and item.get("target_agent") == phase
    ]
    consultation_trigger = evaluate_consultation_trigger(
        current_phase_trigger_history,
        existing_sessions=consultation_sessions,
        max_rounds=max_rounds,
    )
    consultation_required = bool(consultation_trigger.get("should_pause"))
    experience_assist = None
    if consultation_required and phase in {"forensics", "osint"} and not _phase_already_experience_assisted(state, phase):
        experience_assist = await experience_rag_search(
            query=_experience_query(
                phase=phase,
                case_prompt=case_prompt,
                issues=high or issues_found,
                llm_cross_validation=llm_cross_validation,
            ),
            user_id=str(state.get("user_id") or ""),
            agent=phase,
        )
        if experience_assist.get("matches"):
            consultation_required = False
            requires_more_evidence = True
            target_agent = phase
            challenge_record["experience_assisted"] = True
            challenge_record["experience_rag"] = experience_assist
            consultation_trigger = {
                **consultation_trigger,
                "should_pause": False,
                "deferred_by_experience": True,
                "experience_match_count": len(experience_assist.get("matches") or []),
            }
            log("thinking", f"命中个人经验 {len(experience_assist.get('matches') or [])} 条，先打回 {phase} 按经验补强一轮")
            record_audit_event(
                action="experience_rag.assisted",
                task_id=task_id,
                agent="challenger",
                metadata={
                    "phase": phase,
                    "match_count": len(experience_assist.get("matches") or []),
                    "degraded": bool(experience_assist.get("degraded")),
                },
            )
    consultation_resumed = False
    consultation_resume_payload = None
    if consultation_required and interrupt is not None:
        event_type = str(consultation_trigger.get("event_type") or "collaboration_required")
        context_payload = build_consultation_context(
            task_id=task_id,
            case_prompt=case_prompt,
            evidence_files=_all_evidence_files(state),
            forensics_result=forensics,
            osint_result=osint,
            challenger_feedback={"confidence": confidence, "issues_found": issues_found},
            trigger=consultation_trigger,
        )
        context_payload = await commander_dedupe_consultation_context(
            context_payload,
            case_prompt=case_prompt,
            sample_refs=sample_refs,
        )
        log("thinking", "Commander 主持已整理协同需要帮助字段")
        payload = {
            "type": event_type,
            "task_id": task_id,
            "round": round_num,
            "phase": phase,
            "target_agent": consultation_trigger.get("target_agent"),
            "repeat_index": consultation_trigger.get("repeat_index"),
            "requires_user_approval": consultation_trigger.get("requires_user_approval", False),
            "reason": consultation_trigger.get("reason") or (issues_found[0].get("description") if issues_found else "连续低置信触发人机协同"),
            "issues": issues_found,
            "case_prompt": case_prompt,
            "context": context_payload,
        }
        pending_consultation_approval = payload if event_type == "collaboration_approval_required" else None
        active_consultation_session = payload if event_type == "collaboration_required" else None
        consultation_resume_payload = interrupt(payload)
        consultation_resumed = True
        if isinstance(consultation_resume_payload, dict):
            resumed_messages = consultation_resume_payload.get("expert_messages")
            if isinstance(resumed_messages, list):
                expert_messages.extend(m for m in resumed_messages if isinstance(m, dict))
                expert_messages = filter_human_consultation_messages(expert_messages)
            resumed_sessions = consultation_resume_payload.get("collaboration_sessions") or consultation_resume_payload.get("consultation_sessions")
            if isinstance(resumed_sessions, list):
                consultation_sessions = [m for m in resumed_sessions if isinstance(m, dict)]
            summary = consultation_resume_payload.get("confirmed_collaboration_summary") or consultation_resume_payload.get("confirmed_consultation_summary")
            if isinstance(summary, dict):
                summary.setdefault("phase", phase)
                summary.setdefault("target_agent", phase)
                confirmed_consultation_summary = summary
                residual_risks.append({
                    "phase": phase,
                    "issue": {"type": "collaboration_summary", "description": summary.get("confirmed_summary", "")},
                    "reason": "用户确认的协同摘要已回注证据板",
                    "timestamp": _now(),
                })
            active_consultation_session = None
            pending_consultation_approval = None
            if consultation_resume_payload.get("action") == "skip_consultation":
                requires_more_evidence = False
                target_agent = None
                collaboration_release = True
                collaboration_release_reason = "用户在人机协同审批中选择跳过本次重复协同，允许带残留风险继续推进"
            log("thinking", f"协同已恢复，恢复指令: {consultation_resume_payload.get('action', 'resume')}")
    elif consultation_required:
        log("action", "当前 LangGraph 运行时不可用 interrupt，继续自动重审/推进")

    for issue in issues_found:
        challenges.append({
            "round": round_num,
            "phase": phase,
            "issue": issue,
            "timestamp": _now(),
        })

    if max_rounds_release:
        next_action = "max_rounds_release"
        action_reason = (
            f"第 {phase_round} 轮达到 max_rounds={max_rounds}，按轮次上限放行；"
            f"置信度 {confidence:.1%}，残留风险已写入报告。"
        )
    elif collaboration_release and not requires_more_evidence:
        next_action = "release_after_collaboration"
        action_reason = collaboration_release_reason or "人机协同意见允许带残留风险放行。"
    elif requires_more_evidence:
        next_action = "return_for_reinforcement"
        reasons: list[str] = []
        if low_confidence:
            reasons.append(f"置信度 {confidence:.1%} 低于 {satisfaction_threshold:.0%} 阈值")
        if model_requires_more_evidence:
            reasons.append("模型审查要求补充证据")
        if high:
            reasons.append(f"仍有 {len(high)} 个高严重度问题")
        if not reasons and issues_found:
            reasons.append("仍有未解决质询问题")
        action_reason = "；".join(reasons) + f"，打回 {phase} Agent 针对性补强。"
    else:
        next_action = "release"
        action_reason = f"置信度 {confidence:.1%} 已达到 {satisfaction_threshold:.0%} 阈值，且未发现阻断性问题，放行进入下一阶段。"

    feedback = {
        "round": round_num,
        "phase": phase,
        "phase_round": phase_round,
        "next_phase": phase if requires_more_evidence else _next_phase(phase),
        "issues_found": issues_found,
        "requires_more_evidence": requires_more_evidence,
        "target_agent": target_agent,
        "next_action": next_action,
        "action_reason": action_reason,
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
        "satisfaction_threshold": satisfaction_threshold,
        "convergence_stable": phase_stable,
        "convergence_reason": convergence.get("reason"),
        "maxed_rounds": maxed,
        "max_rounds_release": max_rounds_release,
        "low_confidence": low_confidence,
        "residual_risks": residual_risks,
        "llm_cross_validation": llm_cross_validation,
        "experience_guided": bool(challenger_experience.get("matches")),
        "challenger_experience_rag": challenger_experience,
        "suppressed_issue_count": len(suppressed_issues),
        "suppressed_issues": suppressed_issues,
        "consultation_required": consultation_required,
        "collaboration_required": consultation_required,
        "experience_assisted": bool(experience_assist and experience_assist.get("matches")),
        "experience_rag": experience_assist,
        "consultation_resumed": consultation_resumed,
        "collaboration_resumed": consultation_resumed,
        "consultation_resume_payload": consultation_resume_payload if isinstance(consultation_resume_payload, dict) else None,
        "consultation_event_type": consultation_trigger.get("event_type") if consultation_required else None,
        "collaboration_event_type": consultation_trigger.get("event_type") if consultation_required else None,
        "consultation_trigger": consultation_trigger,
        "collaboration_trigger": consultation_trigger,
        "consultation_sessions": consultation_sessions,
        "collaboration_sessions": consultation_sessions,
        "consultation_trigger_history": consultation_trigger_history,
        "collaboration_trigger_history": consultation_trigger_history,
        "active_consultation_session": active_consultation_session,
        "active_collaboration_session": active_consultation_session,
        "pending_consultation_approval": pending_consultation_approval,
        "pending_collaboration_approval": pending_consultation_approval,
        "confirmed_consultation_summary": confirmed_consultation_summary,
        "confirmed_collaboration_summary": confirmed_consultation_summary,
        "collaboration_release": collaboration_release,
        "collaboration_release_reason": collaboration_release_reason,
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
        "collaboration_sessions": consultation_sessions,
        "consultation_trigger_history": consultation_trigger_history,
        "collaboration_trigger_history": consultation_trigger_history,
        "active_consultation_session": active_consultation_session,
        "active_collaboration_session": active_consultation_session,
        "pending_consultation_approval": pending_consultation_approval,
        "pending_collaboration_approval": pending_consultation_approval,
        "confirmed_consultation_summary": confirmed_consultation_summary,
        "confirmed_collaboration_summary": confirmed_consultation_summary,
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
            content=f"逻辑质询Agent 质询 {phase}: 第 {phase_round} 轮，置信度 {confidence:.1%}，下一步 {next_action}",
            phase=phase,
            phase_round=phase_round,
            quality_score=quality_score,
            confidence=confidence,
            satisfaction=confidence,
            quality_delta=delta,
            requires_more_evidence=requires_more_evidence,
            next_action=next_action,
            action_reason=action_reason,
            model_requires_more_evidence=model_requires_more_evidence,
            model_target_agent=model_target_agent,
            maxed_rounds=maxed,
            max_rounds_release=max_rounds_release,
            collaboration_required=consultation_required,
            collaboration_event_type=consultation_trigger.get("event_type") if consultation_required else None,
            consultation_event_type=consultation_trigger.get("event_type") if consultation_required else None,
        )],
        "expert_messages": expert_messages,
        "current_round": round_num + (1 if requires_more_evidence else 0),
    }
