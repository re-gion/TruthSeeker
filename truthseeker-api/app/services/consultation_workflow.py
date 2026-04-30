"""Human-in-the-loop consultation workflow helpers."""
from __future__ import annotations

from datetime import datetime, timezone
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


def _issue_key(issue: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(issue.get("type") or "issue").strip().lower(),
        str(issue.get("description") or issue.get("summary") or "").strip(),
        str(issue.get("agent") or issue.get("target_agent") or "").strip().lower(),
    )


def _dedupe_high_issues(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        for issue in record.get("issues") or []:
            if not isinstance(issue, dict) or str(issue.get("severity")).lower() != "high":
                continue
            normalized = dict(issue)
            normalized["description"] = str(
                normalized.get("description") or normalized.get("summary") or normalized.get("type") or "高风险问题"
            ).strip()
            normalized["severity"] = "high"
            key = _issue_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            issues.append(normalized)
    return issues


def is_human_consultation_message(item: dict[str, Any]) -> bool:
    """Return True for user/expert-authored consultation content."""
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
    """Filter and de-duplicate human consultation messages while preserving order."""
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
    """Return de-duplicated human messages scoped to the latest consultation session."""
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
    if not target:
        return []
    if all(item.get("target_agent") == target for item in recent):
        return recent
    return []


def _adjacent_confidence_deltas_are_stable(records: list[dict[str, Any]], delta_threshold: float) -> bool:
    if len(records) < 2:
        return False
    scores = [_as_float(item.get("confidence"), 1.0) for item in records]
    return all(abs(scores[index] - scores[index - 1]) < delta_threshold for index in range(1, len(scores)))


def _completed_session_count(existing_sessions: list[dict[str, Any]]) -> int:
    return sum(1 for item in existing_sessions if item.get("status") in {"summary_confirmed", "skipped"})


def evaluate_consultation_trigger(
    challenge_records: list[dict[str, Any]],
    *,
    existing_sessions: list[dict[str, Any]] | None = None,
    stuck_rounds: int | None = None,
    confidence_threshold: float | None = None,
    delta_threshold: float | None = None,
) -> dict[str, Any]:
    """Decide whether Challenger should pause for human/expert consultation."""
    stuck_rounds = int(stuck_rounds or settings.CONSULTATION_STUCK_ROUNDS)
    confidence_threshold = float(confidence_threshold or settings.CONSULTATION_CONFIDENCE_THRESHOLD)
    delta_threshold = float(delta_threshold or settings.CONSULTATION_DELTA_THRESHOLD)
    existing_sessions = existing_sessions or []

    recent = _same_target_recent_records(challenge_records, stuck_rounds)
    if not recent:
        return {"should_pause": False, "reason": "最近质询记录不足或目标 Agent 不一致"}

    current = recent[-1]
    if not all(_is_high_challenge(item) for item in recent):
        return {"should_pause": False, "reason": "最近三轮并非均为 high 质询"}
    if _as_float(current.get("confidence"), 1.0) >= confidence_threshold:
        return {"should_pause": False, "reason": "当前置信度未低于会诊阈值"}
    if not _adjacent_confidence_deltas_are_stable(recent, delta_threshold):
        return {"should_pause": False, "reason": "最近三轮相邻置信度变化未持续小于阈值"}

    repeat_index = _completed_session_count(existing_sessions) + 1
    requires_user_approval = repeat_index > 1
    target_agent = str(current.get("target_agent") or current.get("phase") or "unknown")
    event_type = "consultation_approval_required" if requires_user_approval else "consultation_required"
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
        "reason": f"{target_agent} 连续 {stuck_rounds} 轮低置信高质询且置信度变化停滞",
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
    expert_tasks = []
    for index, issue in enumerate(high_issues[:5], start=1):
        target_agent = issue.get("agent") or issue.get("target_agent") or trigger.get("target_agent")
        description = str(issue.get("description") or "高风险问题").strip()
        expert_tasks.append({
            "id": f"expert-task-{index}",
            "target_agent": target_agent or "unknown",
            "issue_type": issue.get("type", "issue"),
            "severity": "high",
            "question": f"请专家判断并补充：{description}",
            "requested_action": "请给出判断依据、可补充证据、以及是否需要重跑/人工复核该环节。",
            "expected_output": "一到三条可执行结论：风险判断、缺失证据、建议继续检测或人工复核的动作。",
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
        "help_needed": [issue["description"] for issue in high_issues[:5] if issue.get("description")],
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

    generated = "本轮会诊未收到新增人工意见。"
    if key_quotes:
        roles = sorted({str(item.get("role") or "participant") for item in key_quotes})
        expert_views = [quote["message"] for quote in key_quotes if quote["role"] in {"expert", "analyst", "viewer"}]
        user_views = [quote["message"] for quote in key_quotes if quote["role"] in {"user", "moderator"}]
        fragments = [f"本轮会诊共收到 {len(normalized_messages)} 条人工意见，参与角色：{'、'.join(roles)}。"]
        if expert_views:
            fragments.append(f"专家侧主要认为：{'；'.join(expert_views[:3])}")
        if user_views:
            fragments.append(f"用户侧补充或确认：{'；'.join(user_views[:2])}")
        fragments.append("Commander 已将上述意见纳入后续裁决，请结合原检测证据判断是否恢复分析、补证或调整结论。")
        generated = (
            "\n".join(fragments)
        )

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
