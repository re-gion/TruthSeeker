"""Best-effort audit logging helpers."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

REDACT_KEYS = {
    "access_token",
    "authorization",
    "file_url",
    "file_urls",
    "invite_token",
    "refresh_token",
    "share_token",
    "signed_url",
    "signedurl",
    "token",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in REDACT_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def build_audit_log_row(
    *,
    action: str,
    task_id: str | None = None,
    user_id: str | None = None,
    actor_role: str = "user",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "action": action,
        "task_id": task_id,
        "user_id": user_id,
        "actor_role": actor_role,
        "metadata": _redact(metadata or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def record_audit_event(
    *,
    action: str,
    task_id: str | None = None,
    user_id: str | None = None,
    actor_role: str = "user",
    metadata: dict[str, Any] | None = None,
    client=None,
) -> None:
    row = build_audit_log_row(
        action=action,
        task_id=task_id,
        user_id=user_id,
        actor_role=actor_role,
        metadata=metadata,
    )
    try:
        active_client = client
        if active_client is None:
            from app.utils.supabase_client import supabase

            active_client = supabase
        active_client.table("audit_logs").insert(row).execute()
    except Exception as exc:
        logger.warning("Failed to record audit event %s for task %s: %s", action, task_id, exc)
