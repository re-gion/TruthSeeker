"""Human-in-the-loop collaboration workflow helpers."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from app.config import settings


CONSULTATION_ACTIVE_STATUSES = {
    "requested",
    "waiting_user_approval",
    "active",
    "summary_pending",
    "summary_confirmed",
}

HUMAN_CONSULTATION_ROLES = {"expert", "user", "viewer", "analyst", "moderator"}
SYSTEM_CONSULTATION_ROLES = {"commander", "system", "summary"}
SYSTEM_MESSAGE_TYPES = {
    "approval",
    "moderator_note",
    "skip",
    "summary",
    "summary_confirmed",
    "system",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _is_high_challenge(record: dict[str, Any]) -> bool:
    if int(record.get("high_severity_count") or 0) > 0:
        return True
    for issue in record.get("issues") or []:
        if isinstance(issue, dict) and str(issue.get("severity")).lower() == "high":
            return True
    return False


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _message_text(item: dict[str, Any]) -> str:
    return str(item.get("message") or item.get("text") or item.get("content") or "").strip()


def _normalize_agent_names(text: str) -> str:
    return re.sub(r"(?i)(电子取证|情报溯源|逻辑质询|研判指挥)\s*agent", r"\1 Agent", text)


def _trim_complete_sentence(text: str, *, max_chars: int = 180) -> str:
    normalized = re.sub(r"\s+", " ", text).strip("，,；;。 ")
    if len(normalized) <= max_chars:
        return f"{normalized}。" if normalized else ""
    candidate = normalized[:max_chars]
    boundary = max(candidate.rfind(mark) for mark in "。！？；")
    if boundary >= max_chars // 2:
        candidate = candidate[: boundary + 1]
    else:
        comma = max(candidate.rfind(mark) for mark in "，,")
        candidate = candidate[:comma] if comma >= max_chars // 2 else candidate
    return candidate.rstrip("，,；;。 ") + "。"


def _expert_point_summary(point: str) -> str:
    text = re.sub(r"^(?:（(?:[一二三四五六七八九十\d]+)）|\(\d+\))", "", point).strip()
    text = re.sub(r"^对于第[^—:：，,]{1,12}(?:点)?[—:：，,]+", "", text)
    quoted = re.match(r"^[“\"](?P<issue>(?:.|\n)*?)[”\"]\s*[—:：]+(?P<answer>.*)$", text)
    topic = ""
    if quoted:
        issue = quoted.group("issue")
        text = quoted.group("answer").strip()
        topic = re.split(r"[。；;，,]", issue, maxsplit=1)[0]
        topic = re.sub(r"(?:degraded|scan_available|error)\s*=\s*[^/\s，,；;]+/?", "", topic, flags=re.I)
        topic = re.sub(r"(?:degraded|scan_available|error)", "", topic, flags=re.I)
        topic = topic.strip("：:、/，,；;。 ")[:60]

    normalized = _normalize_agent_names(re.sub(r"\s+", "", text))
    normalized = re.sub(r"我(?:个人)?(?:认为|觉得)", "专家认为", normalized)
    normalized = normalized.replace("基本无影响", "不影响").replace("影响不大", "影响有限")
    normalized = normalized.replace("不需要进行", "无需重复处理").replace("交给后面的", "由后续")
    normalized = normalized.replace("即可", "处理")
    normalized = re.sub(r"Agent(?=[\u4e00-\u9fff])", "Agent ", normalized)
    clauses = [clause.strip() for clause in re.split(r"[。；;，,]", normalized) if clause.strip()]
    decision_words = ("建议", "应当", "应该", "无需", "不需要", "交给", "影响", "认可", "同意", "接受", "放行", "补证")
    reason_words = ("因为", "由于", "可能", "概率", "大概率", "只是")
    decision_clauses = [clause for clause in clauses if any(word in clause for word in decision_words)]
    selected = decision_clauses[:1]
    if selected and any(word in selected[0] for word in ("无需", "不需要")):
        handoff = next((clause for clause in clauses if "交给" in clause or "由后续" in clause), "")
        if handoff:
            selected.append(handoff)
    reason = next((clause for clause in clauses if any(word in clause for word in reason_words)), "")
    if reason and reason not in selected:
        selected.append(reason)
    if not selected:
        selected = clauses[:2]

    conclusion = "；".join(selected)
    if topic and conclusion.startswith(("该", "此", "上述")):
        conclusion = re.sub(r"^(?:该|此|上述)(?:项|问题|情况|降级)?", "", conclusion)
        conclusion = f"关于{topic}，{conclusion}"
    return _trim_complete_sentence(conclusion)


def _fallback_collaboration_summary(messages: list[dict[str, Any]]) -> str:
    expert_points: list[str] = []
    user_messages: list[str] = []
    for item in messages:
        role = str(item.get("role") or "").strip().lower()
        message = _message_text(item)
        if role in {"expert", "analyst", "viewer"}:
            points = [
                part for part in re.split(r"(?=（(?:[一二三四五六七八九十\d]+)）|\(\d+\))", message)
                if part.strip()
            ]
            expert_points.extend(filter(None, (_expert_point_summary(point) for point in points)))
        elif role in {"user", "moderator"}:
            user_messages.append(message)

    lines = ["协同结论："]
    for index, point in enumerate(expert_points[:6], start=1):
        lines.append(f"{index}. {point}")

    acknowledgements = ("认可", "同意", "赞同", "没问题", "好的", "谢谢")
    if user_messages and all(
        len(message) <= 100 and any(word in message for word in acknowledgements)
        for message in user_messages
    ):
        lines.append("用户反馈：用户认可专家意见，未提出新的异议或补充证据。")
    elif user_messages:
        user_summary = "；".join(
            summary for summary in (_trim_complete_sentence(message, max_chars=120) for message in user_messages[:2])
            if summary
        )
        if user_summary:
            lines.append(f"用户反馈：{user_summary}")

    lines.append("回注建议：后续 Agent 应结合原始检测证据采用上述人工判断；尚未解决的事项继续保留为待补证项。")
    return "\n".join(lines)


def _issue_key(issue: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(issue.get("type") or "issue").strip().lower(),
        str(issue.get("description") or issue.get("summary") or "").strip(),
        str(issue.get("agent") or issue.get("target_agent") or "").strip().lower(),
    )


def _dedupe_recent_issues(records: list[dict[str, Any]], *, high_only: bool = False) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        for issue in record.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            severity = str(issue.get("severity") or "medium").lower()
            if high_only and severity != "high":
                continue
            normalized = dict(issue)
            normalized["description"] = str(
                normalized.get("description") or normalized.get("summary") or normalized.get("type") or "质询问题"
            ).strip()
            normalized["severity"] = severity if severity in {"high", "medium", "low"} else "medium"
            key = _issue_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            issues.append(normalized)
    return issues


def _dedupe_high_issues(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _dedupe_recent_issues(records, high_only=True)


def is_human_consultation_message(item: dict[str, Any]) -> bool:
    """Return True for user/expert-authored collaboration content."""
    if not isinstance(item, dict):
        return False
    role = str(item.get("role") or "").strip().lower()
    message_type = str(item.get("message_type") or "").strip().lower()
    if role in SYSTEM_CONSULTATION_ROLES or message_type in SYSTEM_MESSAGE_TYPES:
        return False
    if role and role not in HUMAN_CONSULTATION_ROLES:
        return False
    return bool(_message_text(item))


def filter_human_consultation_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter and de-duplicate human collaboration messages while preserving order."""
    filtered: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in messages:
        if not is_human_consultation_message(item):
            continue
        text = _message_text(item)
        key = (
            str(item.get("id") or ""),
            str(item.get("session_id") or ""),
            str(item.get("role") or "").strip().lower(),
            text,
        )
        if not key[0]:
            key = ("", key[1], key[2], key[3])
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(item)
        normalized["message"] = text
        filtered.append(normalized)
    return filtered


def latest_consultation_session(sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [item for item in sessions if isinstance(item, dict)]
    if not valid:
        return None
    return sorted(valid, key=lambda item: _parse_time(item.get("created_at")))[-1]


def latest_human_consultation_messages(
    messages: list[dict[str, Any]],
    sessions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return de-duplicated human messages scoped to the latest collaboration session."""
    latest = latest_consultation_session(sessions or [])
    scoped = messages
    if latest and latest.get("id"):
        latest_id = latest.get("id")
        scoped = [item for item in messages if isinstance(item, dict) and item.get("session_id") == latest_id]
    return filter_human_consultation_messages(scoped)


def build_timeline_event(
    *,
    agent: str,
    event_type: str,
    content: str,
    round_number: int | None = None,
    source_kind: str = "agent",
    from_phase: str | None = None,
    target_agent: str | None = None,
    timestamp: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    event = {
        "agent": agent,
        "type": event_type,
        "event_type": event_type,
        "source_kind": source_kind,
        "from_phase": from_phase,
        "target_agent": target_agent or agent,
        "content": content,
        "summary": content,
        "timestamp": timestamp or utc_now_iso(),
    }
    if round_number is not None:
        event["round"] = round_number
    event.update({key: value for key, value in extra.items() if value is not None})
    return event


def _same_target_recent_records(challenge_records: list[dict[str, Any]], stuck_rounds: int) -> list[dict[str, Any]]:
    if len(challenge_records) < stuck_rounds:
        return []
    recent = challenge_records[-stuck_rounds:]
    target = recent[-1].get("target_agent")
    phase = recent[-1].get("phase")
    if not target:
        return []
    if not phase or target != phase:
        return []
    if all(item.get("target_agent") == target and item.get("phase") == phase for item in recent):
        return recent
    return []


def _adjacent_confidence_deltas_are_stable(records: list[dict[str, Any]], delta_threshold: float) -> bool:
    if len(records) < 2:
        return False
    scores = [_as_float(item.get("confidence"), 1.0) for item in records]
    return all(abs(scores[index] - scores[index - 1]) < delta_threshold for index in range(1, len(scores)))


def _completed_session_count(existing_sessions: list[dict[str, Any]], target_agent: str | None = None) -> int:
    count = 0
    for item in existing_sessions:
        if item.get("status") not in {"summary_confirmed", "skipped"}:
            continue
        session_target = str(item.get("triggered_by_agent") or item.get("trigger_phase") or "").strip()
        if target_agent and session_target and session_target != target_agent:
            continue
        count += 1
    return count


def evaluate_consultation_trigger(
    challenge_records: list[dict[str, Any]],
    *,
    existing_sessions: list[dict[str, Any]] | None = None,
    stuck_rounds: int | None = None,
    confidence_threshold: float | None = None,
    delta_threshold: float | None = None,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    """Decide whether Challenger should pause for human collaboration."""
    stuck_rounds = int(stuck_rounds or settings.CONSULTATION_STUCK_ROUNDS)
    confidence_threshold = float(confidence_threshold or settings.CONSULTATION_CONFIDENCE_THRESHOLD)
    delta_threshold = float(delta_threshold or settings.CONSULTATION_DELTA_THRESHOLD)
    max_rounds = int(max_rounds or settings.MAX_ROUNDS)
    existing_sessions = existing_sessions or []

    recent = _same_target_recent_records(challenge_records, stuck_rounds)
    if not recent:
        return {"should_pause": False, "reason": "最近质询记录不足或目标 Agent 不一致"}

    current = recent[-1]
    if not all(_as_float(item.get("confidence"), 1.0) < confidence_threshold for item in recent):
        return {"should_pause": False, "reason": "最近三轮并非均低于人机协同置信度阈值"}
    if not _adjacent_confidence_deltas_are_stable(recent, delta_threshold):
        return {"should_pause": False, "reason": "最近三轮相邻置信度变化未持续小于阈值"}

    current_phase_round = int(current.get("phase_round") or current.get("round") or 0)
    if current_phase_round >= max_rounds:
        return {"should_pause": False, "reason": "当前阶段已达到最大轮次，直接放行并保留残留风险"}

    target_agent = str(current.get("target_agent") or current.get("phase") or "unknown")
    completed_sessions = _completed_session_count(existing_sessions, target_agent)
    max_consultations = max(0, max_rounds - stuck_rounds)
    if completed_sessions >= max_consultations:
        return {"should_pause": False, "reason": "当前阶段协同次数已达上限，直接放行并保留残留风险"}

    repeat_index = completed_sessions + 1
    requires_user_approval = repeat_index > 1
    event_type = "collaboration_approval_required" if requires_user_approval else "collaboration_required"
    return {
        "should_pause": True,
        "event_type": event_type,
        "requires_user_approval": requires_user_approval,
        "repeat_index": repeat_index,
        "target_agent": target_agent,
        "phase": current.get("phase"),
        "round": current.get("round"),
        "phase_round": current.get("phase_round"),
        "confidence": _as_float(current.get("confidence"), 0.0),
        "quality_delta": current.get("quality_delta"),
        "reason": f"{target_agent} 连续 {stuck_rounds} 轮低置信且置信度变化停滞，需人机协同打破僵局",
        "recent_challenges": recent,
    }


def build_consultation_context(
    *,
    task_id: str,
    case_prompt: str,
    evidence_files: list[dict[str, Any]],
    forensics_result: dict[str, Any] | None,
    osint_result: dict[str, Any] | None,
    challenger_feedback: dict[str, Any] | None,
    trigger: dict[str, Any],
) -> dict[str, Any]:
    """Build the moderator context shown to user and experts."""
    sample_links = []
    for item in evidence_files:
        if not isinstance(item, dict):
            continue
        sample_links.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "modality": item.get("modality"),
                "mime_type": item.get("mime_type"),
                "size_bytes": item.get("size_bytes"),
                "storage_path": item.get("storage_path"),
                "file_url": item.get("file_url"),
            }
        )

    high_issues = _dedupe_high_issues(trigger.get("recent_challenges") or [])
    review_issues = high_issues or _dedupe_recent_issues(trigger.get("recent_challenges") or [])
    expert_tasks = []
    for index, issue in enumerate(review_issues[:5], start=1):
        target_agent = issue.get("agent") or issue.get("target_agent") or trigger.get("target_agent")
        severity = str(issue.get("severity") or "medium")
        description = str(issue.get("description") or "质询问题").strip()
        expert_tasks.append({
            "id": f"expert-task-{index}",
            "target_agent": target_agent or "unknown",
            "issue_type": issue.get("type", "issue"),
            "severity": severity,
            "question": f"请判断并补充：{description}",
            "requested_action": "请给出判断依据、可补充证据、以及是否应打回补强或允许带残留风险放行。",
            "expected_output": "一到三条可执行结论：风险判断、缺失证据、建议继续补强或放行的动作。",
        })

    return {
        "task_id": task_id,
        "case_prompt": case_prompt,
        "sample_links": sample_links,
        "background": case_prompt or "用户未补充额外背景。",
        "progress_summary": {
            "forensics_confidence": (forensics_result or {}).get("confidence"),
            "forensics_degraded": (forensics_result or {}).get("degraded"),
            "osint_confidence": (osint_result or {}).get("confidence"),
            "osint_degraded": (osint_result or {}).get("degraded"),
            "challenger_confidence": (challenger_feedback or {}).get("confidence"),
        },
        "current_blocker": trigger.get("reason"),
        "help_needed": [issue["description"] for issue in review_issues[:5] if issue.get("description")],
        "expert_tasks": expert_tasks,
        "trigger": trigger,
        "created_at": utc_now_iso(),
    }


def build_moderator_summary(
    *,
    messages: list[dict[str, Any]],
    user_confirmed_summary: str | None = None,
) -> dict[str, Any]:
    """Create the Commander moderator summary payload for reports and resume."""
    normalized_messages = filter_human_consultation_messages([item for item in messages if isinstance(item, dict)])
    key_quotes = []
    for item in normalized_messages:
        message = _message_text(item)
        if not message:
            continue
        key_quotes.append(
            {
                "role": item.get("role", "expert"),
                "message": message[:300],
                "message_type": item.get("message_type", "expert_opinion"),
                "created_at": item.get("created_at"),
            }
        )
        if len(key_quotes) >= 5:
            break

    generated = "本轮人机协同未收到新增人工意见。"
    if key_quotes:
        generated = _fallback_collaboration_summary(normalized_messages)

    confirmed = (user_confirmed_summary or "").strip() or generated
    unresolved_questions = []
    for item in normalized_messages:
        message = _message_text(item)
        if ("?" in message or "？" in message) and message not in unresolved_questions:
            unresolved_questions.append(message[:300])
    return {
        "generated_summary": generated,
        "confirmed_summary": confirmed,
        "user_confirmed_summary": confirmed if user_confirmed_summary else None,
        "human_message_count": len(normalized_messages),
        "used_message_count": len(key_quotes),
        "message_count": len(normalized_messages),
        "key_quotes": key_quotes,
        "unresolved_questions": unresolved_questions,
        "confirmed_at": utc_now_iso() if user_confirmed_summary else None,
    }
