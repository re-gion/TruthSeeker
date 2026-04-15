"""Analysis persistence helpers for task, report, and debate history."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_final_verdict(final_verdict: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize verdict fields and provide backward-compatible aliases."""
    verdict = dict(final_verdict or {})
    confidence = verdict.get("confidence", verdict.get("confidence_overall", 0.0))
    llm_ruling = verdict.get("llm_ruling", "")
    key_evidence = verdict.get("key_evidence") or []
    agent_weights = verdict.get("agent_weights", verdict.get("agent_weights_used", {}))

    normalized = {
        **verdict,
        "confidence": confidence,
        "confidence_overall": confidence,
        "verdict_label": verdict.get("verdict", verdict.get("verdict_label", "inconclusive")),
        "analysis_summary": verdict.get("analysis_summary") or llm_ruling,
        "agent_weights": agent_weights,
        "agent_weights_used": agent_weights,
        "key_evidence": key_evidence,
        "total_evidence": len(key_evidence),
    }
    return normalized


def build_report_row(
    task_id: str,
    final_verdict: dict[str, Any],
    *,
    generated_at: str | None = None,
    existing_share_token: str | None = None,
) -> dict[str, Any]:
    verdict = normalize_final_verdict(final_verdict)
    return {
        "task_id": task_id,
        "verdict": verdict.get("verdict"),
        "confidence_overall": verdict.get("confidence_overall"),
        "summary": verdict.get("analysis_summary"),
        "key_evidence": verdict.get("key_evidence") or [],
        "recommendations": verdict.get("recommendations") or [],
        "generated_at": generated_at or utc_now_iso(),
        "share_token": existing_share_token,
        "verdict_payload": verdict,
    }


def build_agent_log_rows(task_id: str, node_name: str, updates: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for log_entry in updates.get("logs", []):
        rows.append(
            {
                "task_id": task_id,
                "round_number": log_entry.get("round", updates.get("current_round", 1)),
                "agent_name": log_entry.get("agent", node_name),
                "log_type": log_entry.get("type", "action"),
                "content": log_entry.get("content", ""),
                "metadata": {"node": node_name},
                "timestamp": log_entry.get("timestamp", utc_now_iso()),
            }
        )
    return rows


def build_analysis_state_row(
    task_id: str,
    node_name: str,
    updates: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    result_snapshot = {
        "forensics": updates.get("forensics_result"),
        "osint": updates.get("osint_result"),
        "challenger": updates.get("challenger_feedback"),
        "final_verdict": normalize_final_verdict(updates.get("final_verdict")) if updates.get("final_verdict") else None,
    }
    forensics_result = updates.get("forensics_result") or {}
    osint_result = updates.get("osint_result") or {}

    timestamp = created_at or utc_now_iso()
    return {
        "task_id": task_id,
        "round_number": updates.get("current_round", 1),
        "current_agent": node_name,
        "forensics_score": forensics_result.get("confidence", forensics_result.get("forensics_score")),
        "osint_score": osint_result.get("confidence", osint_result.get("threat_score")),
        "convergence_delta": None,
        "evidence_board": {
            "evidence": updates.get("evidence_board") or [],
            "challenges": updates.get("challenges") or [],
            "timeline_events": updates.get("timeline_events") or [],
        },
        "result_snapshot": result_snapshot,
        "is_converged": updates.get("is_converged", False),
        "termination_reason": updates.get("termination_reason"),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


class AnalysisPersistenceService:
    """Handles best-effort persistence of detection progress."""

    def __init__(self, client=supabase):
        self.client = client

    def mark_task_started(
        self,
        task_id: str,
        *,
        input_files: dict[str, Any] | None = None,
        priority_focus: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now_iso()
        payload: dict[str, Any] = {
            "status": "analyzing",
            "started_at": now,
            "updated_at": now,
        }
        if input_files is not None:
            payload["storage_paths"] = input_files
        if priority_focus:
            payload["priority_focus"] = priority_focus
        if metadata is not None:
            payload["metadata"] = metadata
        self._safe_update("tasks", payload, task_id)

    def persist_update(self, task_id: str, node_name: str, updates: dict[str, Any]) -> None:
        log_rows = build_agent_log_rows(task_id, node_name, updates)
        if log_rows:
            self._safe_insert_many("agent_logs", log_rows)

        snapshot_row = build_analysis_state_row(task_id, node_name, updates)
        if snapshot_row["result_snapshot"]["forensics"] or snapshot_row["result_snapshot"]["osint"] or snapshot_row["result_snapshot"]["challenger"] or snapshot_row["result_snapshot"]["final_verdict"] or snapshot_row["evidence_board"]["evidence"] or snapshot_row["evidence_board"]["timeline_events"]:
            self._safe_insert("analysis_states", snapshot_row)

        if updates.get("final_verdict"):
            self.upsert_report(task_id, updates["final_verdict"])

    def upsert_report(self, task_id: str, final_verdict: dict[str, Any]) -> None:
        existing_token = self._fetch_share_token(task_id)
        report_row = build_report_row(task_id, final_verdict, existing_share_token=existing_token)
        self._safe_upsert("reports", report_row, on_conflict="task_id")

    def mark_task_completed(self, task_id: str, final_verdict: dict[str, Any] | None) -> None:
        normalized = normalize_final_verdict(final_verdict)
        now = utc_now_iso()
        payload = {
            "status": "completed" if final_verdict else "failed",
            "result": normalized if final_verdict else None,
            "completed_at": now,
            "updated_at": now,
        }
        self._safe_update("tasks", payload, task_id)

    def _fetch_share_token(self, task_id: str) -> str | None:
        try:
            resp = self.client.table("reports").select("share_token").eq("task_id", task_id).execute()
            if resp.data:
                return resp.data[0].get("share_token")
        except Exception as exc:
            logger.warning("Failed to fetch share token for %s: %s", task_id, exc)
        return None

    def _safe_insert(self, table_name: str, payload: dict[str, Any]) -> None:
        try:
            self.client.table(table_name).insert(payload).execute()
        except Exception as exc:
            logger.warning("Failed to insert into %s: %s", table_name, exc)

    def _safe_insert_many(self, table_name: str, payload: list[dict[str, Any]]) -> None:
        try:
            self.client.table(table_name).insert(payload).execute()
        except Exception as exc:
            logger.warning("Failed to insert many rows into %s: %s", table_name, exc)

    def _safe_update(self, table_name: str, payload: dict[str, Any], task_id: str) -> None:
        try:
            self.client.table(table_name).update(payload).eq("id", task_id).execute()
        except Exception as exc:
            logger.warning("Failed to update %s for task %s: %s", table_name, task_id, exc)

    def _safe_upsert(self, table_name: str, payload: dict[str, Any], *, on_conflict: str) -> None:
        try:
            self.client.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception as exc:
            logger.warning("Failed to upsert into %s: %s", table_name, exc)
