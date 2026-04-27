"""Analysis persistence helpers for task, report, and debate history."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.audit_log import record_audit_event
from app.services.report_integrity import build_report_hash

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


def _as_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_resume_state_from_rows(
    *,
    task_id: str,
    user_id: str,
    input_files: dict[str, Any],
    input_type: str,
    priority_focus: str,
    case_prompt: str,
    evidence_files: list[dict[str, Any]],
    max_rounds: int,
    expert_messages: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rebuild enough graph state to finalize a consultation after process restart."""
    forensics_result: dict[str, Any] | None = None
    osint_result: dict[str, Any] | None = None
    challenger_feedback: dict[str, Any] | None = None
    evidence_board: list[Any] = []
    challenges: list[Any] = []
    timeline_events: list[Any] = []
    round_number = 1
    analysis_phase = "forensics"
    phase_rounds = {"forensics": 1, "osint": 1, "commander": 1}
    phase_quality_history: dict[str, Any] = {"forensics": [], "osint": [], "commander": []}
    phase_residual_risks: list[Any] = []
    provenance_graph: dict[str, Any] | None = None
    tool_results: dict[str, Any] = {}

    for row in rows:
        round_number = max(round_number, int(row.get("round_number") or 1))
        snapshot = _as_record(row.get("result_snapshot"))
        if snapshot.get("forensics"):
            forensics_result = _as_record(snapshot.get("forensics"))
        if snapshot.get("osint"):
            osint_result = _as_record(snapshot.get("osint"))
        if snapshot.get("challenger"):
            challenger_feedback = _as_record(snapshot.get("challenger"))
            phase_value = challenger_feedback.get("phase")
            if isinstance(phase_value, str):
                analysis_phase = phase_value
            phase_round_value = challenger_feedback.get("phase_round")
            if isinstance(phase_round_value, int) and analysis_phase in phase_rounds:
                phase_rounds[analysis_phase] = max(phase_rounds[analysis_phase], phase_round_value)
            residual = challenger_feedback.get("residual_risks")
            if isinstance(residual, list):
                phase_residual_risks.extend(residual)
            quality = challenger_feedback.get("quality_score")
            if isinstance(quality, (int, float)) and analysis_phase in phase_quality_history:
                phase_quality_history[analysis_phase].append(float(quality))
        if snapshot.get("final_verdict"):
            final_snapshot = _as_record(snapshot.get("final_verdict"))
            graph = _as_record(final_snapshot.get("provenance_graph"))
            provenance_graph = graph or provenance_graph
        if osint_result and osint_result.get("provenance_graph"):
            provenance_graph = _as_record(osint_result.get("provenance_graph")) or provenance_graph
        if forensics_result and forensics_result.get("tool_results"):
            tool_results["forensics"] = forensics_result.get("tool_results")
        if osint_result and osint_result.get("tool_results"):
            tool_results["osint"] = osint_result.get("tool_results")

        board = _as_record(row.get("evidence_board"))
        evidence_board.extend(_as_list(board.get("evidence")))
        challenges.extend(_as_list(board.get("challenges")))
        timeline_events.extend(_as_list(board.get("timeline_events")))

    return {
        "task_id": task_id,
        "user_id": user_id,
        "input_files": input_files,
        "input_type": input_type,
        "priority_focus": priority_focus,
        "case_prompt": case_prompt,
        "evidence_files": evidence_files,
        "current_round": round_number,
        "max_rounds": min(max_rounds, 3),
        "convergence_threshold": 0.08,
        "analysis_phase": analysis_phase,
        "phase_rounds": phase_rounds,
        "phase_quality_history": phase_quality_history,
        "phase_residual_risks": phase_residual_risks,
        "forensics_result": forensics_result,
        "osint_result": osint_result,
        "challenger_feedback": challenger_feedback,
        "final_verdict": None,
        "provenance_graph": provenance_graph,
        "agent_weights": {},
        "previous_weights": {},
        "evidence_board": evidence_board,
        "confidence_history": [],
        "challenges": challenges,
        "logs": [],
        "is_converged": False,
        "termination_reason": None,
        "degradation_status": {},
        "tool_results": tool_results,
        "expert_messages": expert_messages,
        "consultation_resume": {
            "action": "resume_from_persistence",
            "resumed_at": utc_now_iso(),
            "expert_message_count": len(expert_messages),
        },
        "timeline_events": timeline_events,
    }


def build_report_row(
    task_id: str,
    final_verdict: dict[str, Any],
    *,
    generated_at: str | None = None,
    existing_share_token: str | None = None,
) -> dict[str, Any]:
    verdict = normalize_final_verdict(final_verdict)
    row = {
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
    row["report_hash"] = build_report_hash(row)
    return row


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
        "analysis_phase": updates.get("analysis_phase"),
        "phase_rounds": updates.get("phase_rounds"),
        "phase_quality_history": updates.get("phase_quality_history"),
        "provenance_graph": updates.get("provenance_graph"),
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

    def __init__(self, client=None):
        if client is None:
            from app.utils.supabase_client import supabase

            client = supabase
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

    def mark_task_waiting_consultation(
        self,
        task_id: str,
        *,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now_iso()
        payload: dict[str, Any] = {
            "status": "waiting_consultation",
            "updated_at": now,
            "metadata": {
                **(metadata or {}),
                "waiting_consultation": True,
                "consultation_reason": reason,
            },
        }
        self._safe_update("tasks", payload, task_id)

    def mark_task_failed(self, task_id: str, *, error_summary: str) -> None:
        now = utc_now_iso()
        payload = {
            "status": "failed",
            "result": {
                "verdict": "failed",
                "analysis_summary": error_summary,
                "error_summary": error_summary,
            },
            "completed_at": now,
            "updated_at": now,
        }
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
        existing_report = self._fetch_report(task_id)
        existing_token = existing_report.get("share_token") if existing_report else None
        report_row = build_report_row(task_id, final_verdict, existing_share_token=existing_token)
        if existing_report and existing_report.get("id"):
            self._safe_update_by_id("reports", report_row, existing_report["id"])
        else:
            self._safe_insert("reports", report_row)
        record_audit_event(
            action="report_generated",
            task_id=task_id,
            metadata={"report_hash": report_row.get("report_hash"), "verdict": report_row.get("verdict")},
            client=self.client,
        )

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

    def _fetch_report(self, task_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("reports").select("id,share_token").eq("task_id", task_id).execute()
            if resp.data:
                return resp.data[0]
        except Exception as exc:
            logger.warning("Failed to fetch report for %s: %s", task_id, exc)
        return None

    def _safe_insert(self, table_name: str, payload: dict[str, Any]) -> None:
        try:
            self.client.table(table_name).insert(payload).execute()
        except Exception as exc:
            logger.error("Failed to insert into %s: %s (payload keys: %s)", table_name, exc, list(payload.keys()))

    def _safe_insert_many(self, table_name: str, payload: list[dict[str, Any]]) -> None:
        try:
            self.client.table(table_name).insert(payload).execute()
        except Exception as exc:
            logger.error("Failed to insert %d rows into %s: %s", len(payload), table_name, exc)

    def _safe_update(self, table_name: str, payload: dict[str, Any], task_id: str) -> None:
        try:
            self.client.table(table_name).update(payload).eq("id", task_id).execute()
        except Exception as exc:
            logger.error("Failed to update %s for task %s: %s (payload keys: %s)", table_name, task_id, exc, list(payload.keys()))

    def _safe_update_by_id(self, table_name: str, payload: dict[str, Any], row_id: str) -> None:
        try:
            self.client.table(table_name).update(payload).eq("id", row_id).execute()
        except Exception as exc:
            logger.error("Failed to update %s row %s: %s (payload keys: %s)", table_name, row_id, exc, list(payload.keys()))

    def _safe_upsert(self, table_name: str, payload: dict[str, Any], *, on_conflict: str) -> None:
        try:
            self.client.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception as exc:
            logger.error("Failed to upsert into %s (on_conflict=%s): %s", table_name, on_conflict, exc)
