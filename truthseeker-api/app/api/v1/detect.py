"""SSE 检测端点 - 多文件任务闭环 + LangGraph 暂停/恢复。"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.agents.graph import compiled_graph
from app.agents.state import TruthSeekerState
from app.services.analysis_persistence import (
    AnalysisPersistenceService,
    build_resume_state_from_rows,
    normalize_final_verdict,
)
from app.services.audit_log import record_audit_event
from app.services.case_library import ensure_case_library_entry, wants_public_case
from app.services.case_rag import index_case_record
from app.services.consultation_workflow import latest_human_consultation_messages
from app.services.evidence_files import (
    UploadedEvidenceFile,
    build_input_files,
    derive_input_type,
    normalize_uploaded_files,
    require_evidence_files,
)
from app.agents.tools.llm_client import get_llm
from app.utils.supabase_client import supabase

try:
    from langgraph.types import Command
except ImportError:  # pragma: no cover - LangGraph minor-version compatibility
    Command = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 20
SESSION_TABLE = "collaboration_sessions"
MESSAGE_TABLE = "collaboration_messages"
LEGACY_SESSION_TABLE = "consultation_sessions"
LEGACY_MESSAGE_TABLE = "consultation_messages"


class DetectRequest(BaseModel):
    """API 请求验证模型（非 LangGraph State）。"""

    task_id: Optional[str] = None
    input_type: str = "video"
    file_url: Optional[str] = None
    file_urls: Optional[dict[str, Any]] = None
    files: list[dict[str, Any]] = Field(default_factory=list)
    case_prompt: Optional[str] = None
    priority_focus: str = "balanced"
    max_rounds: int = Field(5, ge=1, le=5)
    resume: bool = False


def _sse(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True).replace("\n", "\\n")
    return f"data: {payload}\n\n"


AUDIT_ACTION_LABELS = {
    "detect_start": "检测流程启动",
    "detect_completed": "检测流程完成",
    "detect_reused_completed": "复用已完成研判",
    "detect_reuse_failed": "复用已完成研判失败",
    "detect_failed": "检测流程失败",
    "detect_cancelled": "检测流程取消",
    "consultation_resume": "人机协同恢复",
    "collaboration_resume": "人机协同恢复",
}


def audit_timeline_event(
    action: str,
    *,
    agent: str | None = None,
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Convert a persisted audit action into a frontend timeline event."""
    safe_metadata = metadata or {}
    label = AUDIT_ACTION_LABELS.get(action)
    if not label and action.startswith("node_complete."):
        label = f"节点完成：{action.split('.', 1)[1]}"
    label = label or action
    details = []
    for key in ("input_type", "file_count", "round", "verdict", "has_final_verdict"):
        if key in safe_metadata and safe_metadata[key] is not None:
            details.append(f"{key}={safe_metadata[key]}")
    content = label if not details else f"{label}（{', '.join(details)}）"
    return {
        "agent": agent or "system",
        "type": "audit",
        "event_type": "audit",
        "source_kind": "audit",
        "from_phase": agent or "system",
        "target_agent": agent or "system",
        "action": action,
        "content": content,
        "summary": content,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


async def _heartbeat_sender(queue: asyncio.Queue[str], stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
        except asyncio.TimeoutError:
            await queue.put(":keepalive\n\n")


def _safe_metadata(task: dict[str, Any] | None) -> dict[str, Any]:
    value = (task or {}).get("metadata") or {}
    return value if isinstance(value, dict) else {}


def _safe_storage_paths(task: dict[str, Any] | None) -> dict[str, Any]:
    value = (task or {}).get("storage_paths") or {}
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _task_status(task: dict[str, Any] | None) -> str:
    return str((task or {}).get("status") or "").lower()


def _active_detection_run_id(task: dict[str, Any] | None) -> str | None:
    metadata = _safe_metadata(task)
    value = metadata.get("active_detection_run_id")
    return str(value) if value else None


def _latest_detection_run_id(task: dict[str, Any] | None) -> str | None:
    metadata = _safe_metadata(task)
    value = metadata.get("last_detection_run_id") or metadata.get("active_detection_run_id")
    return str(value) if value else None


def _is_active_analyzing_task(task: dict[str, Any] | None) -> bool:
    return _task_status(task) == "analyzing" and bool(_active_detection_run_id(task))


def _next_detection_run_metadata(
    task: dict[str, Any] | None,
    *,
    detection_run_id: str,
    case_prompt: str,
    evidence_files: list[UploadedEvidenceFile],
    started_at: str,
) -> dict[str, Any]:
    metadata = _safe_metadata(task)
    return {
        **metadata,
        "case_prompt": case_prompt,
        "files": _task_storage_files(evidence_files),
        "active_detection_run_id": detection_run_id,
        "last_detection_run_id": detection_run_id,
        "active_detection_started_at": started_at,
        "detection_run_count": _safe_int(metadata.get("detection_run_count")) + 1,
    }


def _resume_detection_run_metadata(
    task: dict[str, Any] | None,
    *,
    detection_run_id: str,
    case_prompt: str,
    evidence_files: list[UploadedEvidenceFile],
    started_at: str,
) -> dict[str, Any]:
    metadata = _safe_metadata(task)
    return {
        **metadata,
        "case_prompt": case_prompt,
        "files": _task_storage_files(evidence_files),
        "active_detection_run_id": detection_run_id,
        "last_detection_run_id": detection_run_id,
        "active_detection_started_at": metadata.get("active_detection_started_at") or started_at,
        "detection_run_count": _safe_int(metadata.get("detection_run_count"), 1),
        "waiting_collaboration": False,
        "waiting_collaboration_approval": False,
        "waiting_consultation": False,
        "waiting_consultation_approval": False,
    }


def _stamp_updates_with_detection_run_id(
    updates: dict[str, Any],
    detection_run_id: str,
) -> dict[str, Any]:
    if not isinstance(updates, dict):
        return updates
    stamped = {**updates, "detection_run_id": detection_run_id}
    final_verdict = stamped.get("final_verdict")
    if isinstance(final_verdict, dict):
        stamped["final_verdict"] = {
            **final_verdict,
            "detection_run_id": detection_run_id,
        }
    return stamped


def _fetch_task(task_id: str) -> dict[str, Any] | None:
    resp = supabase.table("tasks").select("*").eq("id", task_id).execute()
    return resp.data[0] if resp.data else None


def _fetch_report(task_id: str) -> dict[str, Any] | None:
    resp = supabase.table("reports").select("*").eq("task_id", task_id).execute()
    return resp.data[0] if resp.data else None


def _recover_persisted_final_verdict(task_id: str, task: dict[str, Any] | None) -> dict[str, Any] | None:
    """Recover a Commander verdict persisted by an earlier SSE stream.

    A post-Commander consultation interrupt can split one logical detection
    across two HTTP streams. The resumed stream may finish from Challenger and
    therefore not emit another final_verdict update.
    """
    try:
        report = _fetch_report(task_id)
    except Exception as exc:
        logger.warning("Failed to recover report verdict for %s: %s", task_id, exc)
        report = None
    report_payload = report.get("verdict_payload") if isinstance(report, dict) else None
    if isinstance(report_payload, dict) and report_payload.get("verdict"):
        return normalize_final_verdict(report_payload)

    try:
        fresh_task = task or _fetch_task(task_id)
    except Exception as exc:
        logger.warning("Failed to recover task verdict for %s: %s", task_id, exc)
        fresh_task = task
    task_result = fresh_task.get("result") if isinstance(fresh_task, dict) else None
    if isinstance(task_result, dict) and task_result.get("verdict") and task_result.get("verdict") != "failed":
        return normalize_final_verdict(task_result)

    for row in reversed(_fetch_analysis_state_rows(task_id)):
        snapshot = row.get("result_snapshot") if isinstance(row, dict) else None
        final_verdict = snapshot.get("final_verdict") if isinstance(snapshot, dict) else None
        if isinstance(final_verdict, dict) and final_verdict.get("verdict"):
            return normalize_final_verdict(final_verdict)

    return None


def _is_completed_task(task: dict[str, Any] | None) -> bool:
    return isinstance(task, dict) and _task_status(task) == "completed"


async def _reuse_completed_task_stream(
    task_id: str,
    task: dict[str, Any] | None,
    user_id: str,
) -> AsyncGenerator[str, None]:
    final_verdict = _recover_persisted_final_verdict(task_id, task)
    if not final_verdict:
        record_audit_event(
            action="detect_reuse_failed",
            task_id=task_id,
            user_id=user_id,
            metadata={"reason": "missing_persisted_final_verdict"},
        )
        yield _sse({
            "type": "task_failed",
            "task_id": task_id,
            "message": "已完成任务缺少持久化最终裁决，无法安全复用",
        })
        yield _sse({
            "type": "error",
            "task_id": task_id,
            "message": "已完成任务缺少持久化最终裁决，无法安全复用",
        })
        return

    record_audit_event(
        action="detect_reused_completed",
        task_id=task_id,
        user_id=user_id,
        metadata={
            "verdict": final_verdict.get("verdict"),
            "detection_run_id": final_verdict.get("detection_run_id") or _latest_detection_run_id(task),
        },
    )
    yield _sse({
        "type": "final_verdict",
        "task_id": task_id,
        "verdict": final_verdict,
        "reused": True,
    })
    yield _sse({
        "type": "case_import_skipped",
        "task_id": task_id,
        "reason": "already_completed",
        "reused": True,
    })
    yield _sse({
        "type": "complete",
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reused": True,
    })


def _insert_report(task_id: str, final_verdict_data: dict[str, Any]) -> dict[str, Any]:
    from app.services.analysis_persistence import build_report_row

    report_row = build_report_row(task_id, final_verdict_data)
    resp = supabase.table("reports").insert(report_row).execute()
    return resp.data[0] if resp.data else report_row


async def _run_case_import_phase(
    queue: asyncio.Queue[str],
    task_id: str,
    task: dict[str, Any] | None,
    final_verdict_data: dict[str, Any],
    user_id: str,
) -> None:
    try:
        fresh_task = _fetch_task(task_id) or task
    except Exception as exc:
        logger.warning("Failed to refresh task for case import %s, using loaded task: %s", task_id, exc)
        fresh_task = task
    if not wants_public_case(fresh_task):
        await queue.put(_sse({"type": "case_import_skipped", "task_id": task_id, "reason": "not_requested"}))
        return

    await queue.put(_sse({"type": "case_import_start", "task_id": task_id}))
    try:
        report_row = _fetch_report(task_id) or _insert_report(task_id, final_verdict_data)
        try:
            llm = get_llm()
        except Exception as exc:
            logger.warning("Kimi unavailable for public case import %s, using fallback title/summary: %s", task_id, exc)
            llm = None

        import_result = await ensure_case_library_entry(
            supabase,
            fresh_task,
            report_row,
            llm=llm,
        )
        import_status = import_result.get("status", "error")
        if import_status == "created" and import_result.get("entry"):
            try:
                await index_case_record(supabase, import_result["entry"], source_kind="public")
            except Exception as exc:
                logger.warning("Public case RAG indexing skipped for %s: %s", task_id, exc)
        await queue.put(_sse({"type": f"case_import_{import_status}", "task_id": task_id}))
        record_audit_event(
            action=f"case_import_{import_status}",
            task_id=task_id,
            user_id=user_id,
            metadata={
                "import_status": import_status,
                "detection_run_id": final_verdict_data.get("detection_run_id"),
            },
        )
    except Exception as exc:
        logger.error("Case import failed for task %s: %s", task_id, exc)
        await queue.put(_sse({"type": "case_import_error", "task_id": task_id}))


def _assert_task_owner(task: dict[str, Any] | None, user_id: str | None) -> None:
    if not task:
        return
    task_user_id = task.get("user_id")
    if task_user_id and user_id and user_id != "anonymous" and task_user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该检测任务")


def _task_storage_files(files: list[UploadedEvidenceFile]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "mime_type": item.get("mime_type"),
            "size_bytes": item.get("size_bytes"),
            "modality": item.get("modality"),
            "storage_path": item.get("storage_path"),
            "sha256": item.get("sha256"),
            "detected_encoding": item.get("detected_encoding") or item.get("charset"),
            "charset": item.get("charset") or item.get("detected_encoding"),
        }
        for item in files
    ]


def _ensure_signed_urls(files: list[UploadedEvidenceFile]) -> list[UploadedEvidenceFile]:
    signed_files: list[UploadedEvidenceFile] = []
    bucket = supabase.storage.from_("media")
    for item in files:
        normalized = dict(item)
        storage_path = normalized.get("storage_path")
        if storage_path and not normalized.get("file_url"):
            try:
                signed = bucket.create_signed_url(storage_path, 86400)
                file_url = signed.get("signedURL") or signed.get("signedUrl")
                if file_url:
                    normalized["file_url"] = file_url
            except Exception as exc:
                logger.warning("Failed to sign storage path %s: %s", storage_path, exc)
                record_audit_event(
                    action="signed_url.failed",
                    task_id="",
                    metadata={"storage_path": storage_path, "error": f"{type(exc).__name__}: {exc}"},
                )
        signed_files.append(normalized)  # type: ignore[arg-type]
    return signed_files


def _resolve_evidence_files(request: DetectRequest, task: dict[str, Any] | None) -> list[UploadedEvidenceFile]:
    metadata = _safe_metadata(task)
    storage_paths = _safe_storage_paths(task)
    raw_files = (
        request.files
        or metadata.get("files")
        or storage_paths.get("files")
        or []
    )
    files = normalize_uploaded_files(raw_files)
    if not require_evidence_files(files):
        if request.file_url:
            files = normalize_uploaded_files([
                {
                    "name": "legacy-upload",
                    "mime_type": f"{request.input_type.split('_')[0]}/unknown" if request.input_type.split('_')[0] != "text" else "text/plain",
                    "size_bytes": 0,
                    "modality": request.input_type.split('_')[0],
                    "storage_path": request.file_url,
                    "file_url": request.file_url,
                }
            ])
        else:
            raise HTTPException(status_code=400, detail="检测任务缺少待检测文件")
    return _ensure_signed_urls(files)


def _resolve_case_prompt(request: DetectRequest, task: dict[str, Any] | None) -> str:
    metadata = _safe_metadata(task)
    return (
        request.case_prompt
        or metadata.get("case_prompt")
        or (task or {}).get("description")
        or ""
    )


def _fetch_consultation_messages(task_id: str) -> list[dict[str, Any]]:
    for table_name in (MESSAGE_TABLE, LEGACY_MESSAGE_TABLE):
        try:
            resp = (
                supabase.table(table_name)
                .select("*")
                .eq("task_id", task_id)
                .order("created_at", desc=False)
                .execute()
            )
            if resp.data:
                return resp.data
        except Exception as exc:
            logger.warning("Failed to fetch %s for %s: %s", table_name, task_id, exc)
    return []


def _fetch_consultation_sessions(task_id: str) -> list[dict[str, Any]]:
    for table_name in (SESSION_TABLE, LEGACY_SESSION_TABLE):
        try:
            resp = (
                supabase.table(table_name)
                .select("*")
                .eq("task_id", task_id)
                .order("created_at", desc=False)
                .execute()
            )
            if resp.data:
                return resp.data
        except Exception as exc:
            logger.warning("Failed to fetch %s for %s: %s", table_name, task_id, exc)
    return []


def _latest_consultation_session(task_id: str) -> dict[str, Any] | None:
    sessions = _fetch_consultation_sessions(task_id)
    return sessions[-1] if sessions else None


def _create_consultation_session(
    task_id: str,
    interrupt_payload: dict[str, Any],
    *,
    status: str,
) -> dict[str, Any] | None:
    context = interrupt_payload.get("context") if isinstance(interrupt_payload.get("context"), dict) else {}
    record = {
        "task_id": task_id,
        "status": status,
        "reason": interrupt_payload.get("reason"),
        "triggered_by_agent": interrupt_payload.get("target_agent") or interrupt_payload.get("phase"),
        "trigger_phase": interrupt_payload.get("phase"),
        "trigger_round": interrupt_payload.get("round"),
        "repeat_index": interrupt_payload.get("repeat_index", 1),
        "context_payload": context,
        "summary_payload": {},
        "created_by": interrupt_payload.get("target_agent") or "challenger",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = supabase.table(SESSION_TABLE).insert(record).execute()
        return resp.data[0] if resp.data else record
    except Exception as exc:
        logger.warning("Failed to create consultation session for %s: %s", task_id, exc)
        return record


def _resume_payload_from_consultations(task_id: str, user_id: str) -> dict[str, Any]:
    sessions = _fetch_consultation_sessions(task_id)
    expert_messages = latest_human_consultation_messages(
        _fetch_consultation_messages(task_id),
        sessions,
    )
    latest = sessions[-1] if sessions else None
    action = "resume"
    confirmed_summary = None
    if latest:
        status = latest.get("status")
        if status == "skipped":
            action = "skip_consultation"
        elif status == "summary_confirmed":
            action = "resume_after_consultation"
            summary = latest.get("summary_payload")
            if isinstance(summary, dict):
                confirmed_summary = summary
    return {
        "action": action,
        "resumed_by": user_id,
        "expert_messages": expert_messages,
        "consultation_sessions": sessions,
        "collaboration_sessions": sessions,
        "latest_consultation_session": latest,
        "latest_collaboration_session": latest,
        "confirmed_consultation_summary": confirmed_summary,
        "confirmed_collaboration_summary": confirmed_summary,
        "resumed_at": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_analysis_state_rows(task_id: str) -> list[dict[str, Any]]:
    try:
        resp = (
            supabase.table("analysis_states")
            .select("*")
            .eq("task_id", task_id)
            .order("created_at", desc=False)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.warning("Failed to fetch analysis states for %s: %s", task_id, exc)
        return []


def _extract_interrupt_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple)) and value:
        first = value[0]
        if isinstance(first, dict):
            return first
        if hasattr(first, "value") and isinstance(first.value, dict):
            return first.value
    if hasattr(value, "value") and isinstance(value.value, dict):
        return value.value
    return {"type": "collaboration_required", "reason": "检测流程请求人机协同"}


async def sse_event_generator(request: DetectRequest, user_id: str) -> AsyncGenerator[str, None]:
    task_id = request.task_id or str(uuid.uuid4())
    task = _fetch_task(task_id) if request.task_id else None
    _assert_task_owner(task, user_id)
    if request.task_id and not request.resume and _is_completed_task(task):
        async for event in _reuse_completed_task_stream(task_id, task, user_id):
            yield event
        return

    evidence_files = _resolve_evidence_files(request, task)
    case_prompt = _resolve_case_prompt(request, task)
    input_type = derive_input_type(evidence_files)
    input_files = build_input_files(evidence_files)
    detection_run_id = (
        _latest_detection_run_id(task)
        if request.resume
        else str(uuid.uuid4())
    ) or str(uuid.uuid4())
    detection_started_at = datetime.now(timezone.utc).isoformat()

    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_heartbeat = asyncio.Event()
    persistence = AnalysisPersistenceService()
    config = {"configurable": {"thread_id": task_id}}

    initial_state: TruthSeekerState = {
        "task_id": task_id,
        "user_id": user_id,
        "input_files": input_files,
        "input_type": input_type,
        "priority_focus": request.priority_focus,
        "case_prompt": case_prompt,
        "evidence_files": evidence_files,
        "current_round": 1,
        "max_rounds": min(request.max_rounds, settings.MAX_ROUNDS),
        "convergence_threshold": settings.CONVERGENCE_THRESHOLD,
        "analysis_phase": "forensics",
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [], "osint": [], "commander": []},
        "phase_residual_risks": [],
        "forensics_result": None,
        "osint_result": None,
        "challenger_feedback": None,
        "final_verdict": None,
        "provenance_graph": None,
        "agent_weights": {},
        "previous_weights": {},
        "evidence_board": [],
        "confidence_history": [],
        "challenges": [],
        "logs": [],
        "is_converged": False,
        "termination_reason": None,
        "degradation_status": {},
        "tool_results": {},
        "expert_messages": [],
        "collaboration_resume": None,
        "collaboration_sessions": [],
        "collaboration_trigger_history": [],
        "active_collaboration_session": None,
        "pending_collaboration_approval": None,
        "confirmed_collaboration_summary": None,
        "consultation_resume": None,
        "consultation_sessions": [],
        "consultation_trigger_history": [],
        "active_consultation_session": None,
        "pending_consultation_approval": None,
        "confirmed_consultation_summary": None,
        "timeline_events": [],
        "detection_run_id": detection_run_id,
    }

    hb_task = asyncio.create_task(_heartbeat_sender(queue, stop_heartbeat))
    final_verdict_data: dict[str, Any] | None = None
    interrupted = False

    async def run_graph() -> None:
        nonlocal final_verdict_data, interrupted

        async def recover_resume_from_persistence(original_error: Exception) -> bool:
            nonlocal final_verdict_data
            if not request.resume:
                return False

            rows = _fetch_analysis_state_rows(task_id)
            if not rows:
                return False

            logger.warning(
                "LangGraph checkpoint resume failed for %s, rebuilding persisted state: %s",
                task_id,
                original_error,
            )
            from app.agents.nodes.commander import commander_node

            sessions = _fetch_consultation_sessions(task_id)
            expert_messages = latest_human_consultation_messages(
                _fetch_consultation_messages(task_id),
                sessions,
            )
            latest_session = sessions[-1] if sessions else None
            confirmed_summary = None
            if isinstance(latest_session, dict):
                summary_payload = latest_session.get("summary_payload")
                if latest_session.get("status") == "summary_confirmed" and isinstance(summary_payload, dict):
                    confirmed_summary = summary_payload
            resume_state = build_resume_state_from_rows(
                task_id=task_id,
                user_id=user_id,
                input_files=input_files,
                input_type=input_type,
                priority_focus=request.priority_focus,
                case_prompt=case_prompt,
                evidence_files=evidence_files,
                max_rounds=request.max_rounds,
                expert_messages=expert_messages,
                rows=rows,
                persisted_consultation_sessions=sessions,
                persisted_consultation_summary=confirmed_summary,
            )
            resume_state["detection_run_id"] = detection_run_id
            updates = await commander_node(resume_state)  # type: ignore[arg-type]
            updates = _stamp_updates_with_detection_run_id(updates, detection_run_id)

            await queue.put(_sse({
                "type": "collaboration_resumed",
                "task_id": task_id,
                "mode": "persistence_recovery",
                "detection_run_id": detection_run_id,
            }))

            for log_entry in updates.get("logs", []):
                await queue.put(_sse({"type": "agent_log", "node": "commander", "log": log_entry}))

            if updates.get("timeline_events"):
                await queue.put(_sse({"type": "timeline_update", "events": updates["timeline_events"]}))
            if updates.get("agent_weights"):
                await queue.put(_sse({"type": "weights_update", "weights": updates["agent_weights"]}))
            if not updates.get("final_verdict"):
                return False

            final_verdict_data = normalize_final_verdict(updates["final_verdict"])
            await queue.put(_sse({
                "type": "final_verdict",
                "verdict": final_verdict_data,
                "detection_run_id": detection_run_id,
            }))

            persistence.persist_update(task_id, "commander", updates)
            persistence.mark_task_completed(task_id, final_verdict_data)
            record_audit_event(
                action="collaboration_resume",
                task_id=task_id,
                user_id=user_id,
                metadata={
                    "mode": "persistence_recovery",
                    "expert_message_count": len(expert_messages),
                    "detection_run_id": detection_run_id,
                },
            )
            await queue.put(_sse({
                "type": "timeline_update",
                "events": [audit_timeline_event(
                    "collaboration_resume",
                    metadata={
                        "mode": "persistence_recovery",
                        "expert_message_count": len(expert_messages),
                        "detection_run_id": detection_run_id,
                    },
                )],
            }))
            await _run_case_import_phase(queue, task_id, task, final_verdict_data, user_id)
            await queue.put(_sse({
                "type": "complete",
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
            return True

        try:
            if request.resume:
                if Command is None:
                    raise RuntimeError("当前 LangGraph 版本不支持 Command resume")
                resume_payload = _resume_payload_from_consultations(task_id, user_id)
                expert_messages = resume_payload["expert_messages"]
                graph_input = Command(
                    resume=resume_payload,
                    update={
                        "collaboration_resume": resume_payload,
                        "consultation_resume": resume_payload,
                        "expert_messages": expert_messages,
                        "collaboration_sessions": resume_payload.get("collaboration_sessions") or resume_payload.get("consultation_sessions") or [],
                        "consultation_sessions": resume_payload.get("consultation_sessions") or [],
                        "confirmed_collaboration_summary": resume_payload.get("confirmed_collaboration_summary") or resume_payload.get("confirmed_consultation_summary"),
                        "confirmed_consultation_summary": resume_payload.get("confirmed_consultation_summary"),
                        "detection_run_id": detection_run_id,
                    },
                )
                persistence.mark_task_started(
                    task_id,
                    input_files={"files": _task_storage_files(evidence_files)},
                    priority_focus=request.priority_focus,
                    metadata=_resume_detection_run_metadata(
                        task,
                        detection_run_id=detection_run_id,
                        case_prompt=case_prompt,
                        evidence_files=evidence_files,
                        started_at=detection_started_at,
                    ),
                )
                record_audit_event(
                    action="collaboration_resume",
                    task_id=task_id,
                    user_id=user_id,
                    metadata={
                        "expert_message_count": len(expert_messages),
                        "detection_run_id": detection_run_id,
                    },
                )
                latest_session = resume_payload.get("latest_consultation_session")
                if isinstance(latest_session, dict) and resume_payload.get("action") == "skip_consultation":
                    await queue.put(_sse({
                        "type": "collaboration_skipped",
                        "task_id": task_id,
                        "reason": "用户跳过本次重复人机协同",
                        "session": latest_session,
                        "payload": {"session": latest_session, "summary": latest_session.get("summary_payload")},
                    }))
                elif isinstance(latest_session, dict) and resume_payload.get("action") == "resume_after_consultation":
                    await queue.put(_sse({
                        "type": "collaboration_summary_confirmed",
                        "task_id": task_id,
                        "session": latest_session,
                        "summary": resume_payload.get("confirmed_consultation_summary"),
                        "payload": {
                            "session": latest_session,
                            "summary": resume_payload.get("confirmed_consultation_summary"),
                        },
                    }))
                await queue.put(_sse({"type": "collaboration_resumed", "task_id": task_id}))
                await queue.put(_sse({
                    "type": "timeline_update",
                    "events": [audit_timeline_event(
                        "collaboration_resume",
                        metadata={
                            "expert_message_count": len(expert_messages),
                            "detection_run_id": detection_run_id,
                        },
                    )],
                }))
            else:
                graph_input = initial_state
                await queue.put(_sse({
                    "type": "start",
                    "task_id": task_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "max_rounds": initial_state["max_rounds"],
                    "input_type": input_type,
                    "detection_run_id": detection_run_id,
                }))
                persistence.mark_task_started(
                    task_id,
                    input_files={"files": _task_storage_files(evidence_files)},
                    priority_focus=request.priority_focus,
                    metadata=_next_detection_run_metadata(
                        task,
                        detection_run_id=detection_run_id,
                        case_prompt=case_prompt,
                        evidence_files=evidence_files,
                        started_at=detection_started_at,
                    ),
                )
                record_audit_event(
                    action="detect_start",
                    task_id=task_id,
                    user_id=user_id,
                    metadata={
                        "input_type": input_type,
                        "file_count": len(evidence_files),
                        "detection_run_id": detection_run_id,
                    },
                )
                await queue.put(_sse({
                    "type": "timeline_update",
                    "events": [audit_timeline_event(
                        "detect_start",
                        metadata={
                            "input_type": input_type,
                            "file_count": len(evidence_files),
                            "detection_run_id": detection_run_id,
                        },
                    )],
                }))

            async for chunk in compiled_graph.astream(graph_input, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = _extract_interrupt_payload(chunk["__interrupt__"])
                    reason = str(interrupt_payload.get("reason") or "连续低置信触发人机协同")
                    raw_event_type = str(interrupt_payload.get("type") or "collaboration_required")
                    event_type = {
                        "consultation_required": "collaboration_required",
                        "consultation_approval_required": "collaboration_approval_required",
                    }.get(raw_event_type, raw_event_type)
                    waiting_status = (
                        "waiting_collaboration_approval"
                        if event_type == "collaboration_approval_required"
                        else "waiting_collaboration"
                    )
                    session_status = (
                        "waiting_user_approval"
                        if event_type == "collaboration_approval_required"
                        else "active"
                    )
                    session = _create_consultation_session(task_id, interrupt_payload, status=session_status)
                    interrupted = True
                    metadata = {
                        **_safe_metadata(task),
                        "case_prompt": case_prompt,
                        "files": _task_storage_files(evidence_files),
                        "active_detection_run_id": detection_run_id,
                        "last_detection_run_id": detection_run_id,
                        "active_detection_started_at": detection_started_at,
                        "detection_run_count": _safe_int(_safe_metadata(task).get("detection_run_count"), 1),
                        "waiting_collaboration": waiting_status == "waiting_collaboration",
                        "waiting_collaboration_approval": waiting_status == "waiting_collaboration_approval",
                        "waiting_consultation": waiting_status == "waiting_collaboration",
                        "waiting_consultation_approval": waiting_status == "waiting_collaboration_approval",
                        "collaboration_session_id": (session or {}).get("id"),
                        "consultation_session_id": (session or {}).get("id"),
                    }
                    if waiting_status == "waiting_collaboration":
                        persistence.mark_task_waiting_collaboration(task_id, reason=reason, metadata=metadata)
                    else:
                        persistence.mark_task_waiting_collaboration(task_id, reason=reason, metadata=metadata)
                        supabase.table("tasks").update({
                            "status": "waiting_collaboration_approval",
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": metadata,
                        }).eq("id", task_id).execute()
                    record_audit_event(
                        action=event_type,
                        task_id=task_id,
                        user_id=user_id,
                        agent="challenger",
                        metadata={
                            "session_id": (session or {}).get("id"),
                            "reason": reason,
                            "detection_run_id": detection_run_id,
                        },
                    )
                    await queue.put(_sse({
                        "type": event_type,
                        "task_id": task_id,
                        "reason": reason,
                        "payload": interrupt_payload,
                        "session": session,
                    }))
                    if event_type == "collaboration_required":
                        await queue.put(_sse({
                            "type": "collaboration_started",
                            "task_id": task_id,
                            "reason": reason,
                            "payload": {**interrupt_payload, "session": session},
                            "session": session,
                        }))
                    return

                for node_name, updates in chunk.items():
                    updates = _stamp_updates_with_detection_run_id(updates, detection_run_id)
                    await queue.put(_sse({"type": "node_start", "node": node_name}))

                    for log_entry in updates.get("logs", []):
                        await queue.put(_sse({"type": "agent_log", "node": node_name, "log": log_entry}))

                    evidence_list = updates.get("evidence_board", [])
                    if evidence_list:
                        await queue.put(_sse({"type": "evidence_update", "evidence": evidence_list, "node": node_name}))

                    challenges = updates.get("challenges", [])
                    if challenges:
                        await queue.put(_sse({"type": "challenges_update", "challenges": challenges}))

                    if updates.get("forensics_result"):
                        await queue.put(_sse({"type": "forensics_result", "result": updates["forensics_result"]}))

                    if updates.get("osint_result"):
                        await queue.put(_sse({"type": "osint_result", "result": updates["osint_result"]}))

                    if updates.get("challenger_feedback"):
                        await queue.put(_sse({"type": "challenger_feedback", "feedback": updates["challenger_feedback"]}))

                    if updates.get("timeline_events"):
                        await queue.put(_sse({"type": "timeline_update", "events": updates["timeline_events"]}))

                    if updates.get("agent_weights"):
                        await queue.put(_sse({"type": "weights_update", "weights": updates["agent_weights"]}))

                    if "current_round" in updates:
                        await queue.put(_sse({"type": "round_update", "round": updates["current_round"]}))

                    if updates.get("final_verdict"):
                        final_verdict_data = normalize_final_verdict(updates["final_verdict"])
                        await queue.put(_sse({
                            "type": "final_verdict",
                            "verdict": final_verdict_data,
                            "detection_run_id": detection_run_id,
                        }))

                    persistence.persist_update(task_id, node_name, updates)
                    await queue.put(_sse({"type": "node_complete", "node": node_name}))
                    node_audit_metadata = {
                        "round": updates.get("current_round"),
                        "has_final_verdict": bool(updates.get("final_verdict")),
                        "detection_run_id": detection_run_id,
                    }
                    record_audit_event(
                        action=f"node_complete.{node_name}",
                        task_id=task_id,
                        user_id=user_id,
                        agent=node_name,
                        metadata=node_audit_metadata,
                    )
                    await queue.put(_sse({
                        "type": "timeline_update",
                        "events": [audit_timeline_event(
                            f"node_complete.{node_name}",
                            agent=node_name,
                            metadata=node_audit_metadata,
                        )],
                    }))

            completion_verdict_data = final_verdict_data
            if completion_verdict_data is None and request.resume:
                completion_verdict_data = _recover_persisted_final_verdict(task_id, task)
            if completion_verdict_data:
                if final_verdict_data is None:
                    final_verdict_data = completion_verdict_data
                    await queue.put(_sse({
                        "type": "final_verdict",
                        "verdict": final_verdict_data,
                        "detection_run_id": detection_run_id,
                    }))
                persistence.mark_task_completed(task_id, final_verdict_data)
                record_audit_event(
                    action="detect_completed",
                    task_id=task_id,
                    user_id=user_id,
                    metadata={
                        "verdict": final_verdict_data.get("verdict"),
                        "detection_run_id": detection_run_id,
                    },
                )
                await queue.put(_sse({
                    "type": "timeline_update",
                    "events": [audit_timeline_event(
                        "detect_completed",
                        metadata={
                            "verdict": final_verdict_data.get("verdict"),
                            "detection_run_id": detection_run_id,
                        },
                    )],
                }))
                await _run_case_import_phase(queue, task_id, task, final_verdict_data, user_id)
                await queue.put(_sse({
                    "type": "complete",
                    "task_id": task_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            elif not interrupted:
                persistence.mark_task_failed(task_id, error_summary="检测流程未生成最终裁决")
                record_audit_event(
                    action="detect_failed",
                    task_id=task_id,
                    user_id=user_id,
                    metadata={"detection_run_id": detection_run_id},
                )
                await queue.put(_sse({
                    "type": "timeline_update",
                    "events": [audit_timeline_event(
                        "detect_failed",
                        metadata={"detection_run_id": detection_run_id},
                    )],
                }))
                await queue.put(_sse({
                    "type": "task_failed",
                    "task_id": task_id,
                    "message": "检测流程未生成最终裁决",
                }))
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled for task %s (client disconnected)", task_id)
            record_audit_event(
                action="detect_cancelled",
                task_id=task_id,
                user_id=user_id,
                metadata={
                    "reason": "client_disconnect",
                    "detection_run_id": detection_run_id,
                },
            )
            raise
        except Exception as exc:
            logger.error("SSE stream error for task %s: %s", task_id, exc)
            if await recover_resume_from_persistence(exc):
                return
            persistence.mark_task_failed(task_id, error_summary="检测过程发生异常，请稍后重试")
            record_audit_event(
                action="detect_failed",
                task_id=task_id,
                user_id=user_id,
                metadata={
                    "error_type": type(exc).__name__,
                    "detection_run_id": detection_run_id,
                },
            )
            await queue.put(_sse({
                "type": "timeline_update",
                "events": [audit_timeline_event(
                    "detect_failed",
                    metadata={
                        "error_type": type(exc).__name__,
                        "detection_run_id": detection_run_id,
                    },
                )],
            }))
            await queue.put(_sse({
                "type": "task_failed",
                "task_id": task_id,
                "message": "检测过程发生异常，请稍后重试",
            }))
            await queue.put(_sse({
                "type": "error",
                "task_id": task_id,
                "message": "检测过程发生异常，请稍后重试",
            }))
        finally:
            stop_heartbeat.set()

    graph_task = asyncio.create_task(run_graph())

    try:
        while not graph_task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        stop_heartbeat.set()
        graph_task.cancel()
        hb_task.cancel()
        await asyncio.gather(graph_task, hb_task, return_exceptions=True)


@router.post("/stream")
async def detect_stream(request: DetectRequest, raw_request: Request):
    """SSE 流式检测端点。"""
    user_id = getattr(raw_request.state, "user_id", None) or "anonymous"
    if request.task_id:
        task = _fetch_task(request.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="检测任务不存在")
        _assert_task_owner(task, user_id)
        if not request.resume and _is_active_analyzing_task(task):
            raise HTTPException(
                status_code=409,
                detail="任务已有正在运行的检测流，为避免重复研判已拒绝本次启动",
            )

    return StreamingResponse(
        sse_event_generator(request, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
