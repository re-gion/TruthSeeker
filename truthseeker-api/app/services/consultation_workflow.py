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

    high_issues = []
    for record in trigger.get("recent_challenges") or []:
        for issue in record.get("issues") or []:
            if isinstance(issue, dict) and str(issue.get("severity")).lower() == "high":
                high_issues.append(issue)

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
        "help_needed": [
            issue.get("description")
            for issue in high_issues[:5]
            if isinstance(issue, dict) and issue.get("description")
        ],
        "trigger": trigger,
        "created_at": utc_now_iso(),
    }


def build_moderator_summary(
    *,
    messages: list[dict[str, Any]],
    user_confirmed_summary: str | None = None,
) -> dict[str, Any]:
    """Create the Commander moderator summary payload for reports and resume."""
    normalized_messages = [item for item in messages if isinstance(item, dict)]
    key_quotes = []
    for item in normalized_messages:
        message = str(item.get("message") or item.get("text") or "").strip()
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
        generated = "；".join(f"{quote['role']}：{quote['message']}" for quote in key_quotes[:3])

    confirmed = (user_confirmed_summary or "").strip() or generated
    return {
        "generated_summary": generated,
        "confirmed_summary": confirmed,
        "user_confirmed_summary": confirmed if user_confirmed_summary else None,
        "message_count": len(normalized_messages),
        "key_quotes": key_quotes,
        "confirmed_at": utc_now_iso() if user_confirmed_summary else None,
    }
