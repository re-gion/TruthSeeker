"""Public case library helpers."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.services.analysis_persistence import normalize_final_verdict

logger = logging.getLogger(__name__)

CASE_LIBRARY_STATUSES = {"published", "draft", "hidden"}
CASE_LIBRARY_CATEGORIES = {
    "text_generation",
    "image_forgery",
    "image_text_mixed",
    "audio_forgery",
    "video_forgery",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
SIGNED_URL_TOKEN_RE = re.compile(r"([?&](?:token|signature|expires|apikey|access_token)=)[^)\]\s&]+", re.IGNORECASE)
STORAGE_PATH_RE = re.compile(r"\b[a-zA-Z0-9_-]{6,}/tmp[a-zA-Z0-9_.-]+\b")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_case_prompt(case_prompt: str | None) -> str:
    return re.sub(r"\s+", " ", (case_prompt or "").strip())


def build_case_fingerprint(files: list[dict[str, Any]] | None, case_prompt: str | None) -> str:
    """Build global duplicate key from file hashes and normalized case prompt."""
    file_hashes = sorted(
        str(item.get("sha256") or "").strip().lower()
        for item in (files or [])
        if isinstance(item, dict) and str(item.get("sha256") or "").strip()
    )
    payload = {
        "file_hashes": file_hashes,
        "case_prompt": normalize_case_prompt(case_prompt),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def redact_public_text(value: str | None) -> str:
    text = value or ""
    text = EMAIL_RE.sub("[邮箱]", text)
    text = PHONE_RE.sub("[手机号]", text)
    text = ID_CARD_RE.sub("[身份证号]", text)
    text = SIGNED_URL_TOKEN_RE.sub(r"\1[已脱敏]", text)
    text = STORAGE_PATH_RE.sub("[存储路径]", text)
    return text


def redact_public_markdown(markdown: str | None) -> str:
    return redact_public_text(markdown or "")


def _metadata(task: dict[str, Any]) -> dict[str, Any]:
    value = task.get("metadata") or {}
    return value if isinstance(value, dict) else {}


def _task_files(task: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = _metadata(task)
    raw_files = metadata.get("files") or (task.get("storage_paths") or {}).get("files") or []
    return [dict(item) for item in raw_files if isinstance(item, dict)]


def wants_public_case(task: dict[str, Any] | None) -> bool:
    if not task:
        return False
    metadata = _metadata(task)
    return bool(metadata.get("share_to_casebase"))


def _derive_media_category(files: list[dict[str, Any]], input_type: str | None = None) -> str:
    modalities = {
        str(item.get("modality") or "").lower()
        for item in files
        if isinstance(item, dict) and item.get("modality")
    }
    if len(modalities) > 1:
        if "text" in modalities and ("image" in modalities or "video" in modalities or "audio" in modalities):
            return "image_text_mixed"
        return "image_text_mixed"
    if "audio" in modalities:
        return "audio_forgery"
    if "video" in modalities:
        return "video_forgery"
    if "image" in modalities:
        return "image_forgery"
    if "text" in modalities:
        return "text_generation"
    if input_type == "audio":
        return "audio_forgery"
    if input_type == "video":
        return "video_forgery"
    if input_type == "image":
        return "image_forgery"
    return "text_generation"


def _difficulty(confidence: Any) -> str:
    try:
        score = float(confidence)
    except (TypeError, ValueError):
        return "Medium"
    if score >= 0.85:
        return "High"
    if score >= 0.65:
        return "Medium"
    return "Low"


def _safe_file_name(name: Any, index: int) -> str:
    raw = redact_public_text(str(name or f"检材 {index}")).strip()
    if not raw:
        return f"检材 {index}"
    return raw[:120]


def _public_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(files, 1):
        result.append(
            {
                "id": item.get("id") or f"file-{index}",
                "name": _safe_file_name(item.get("name"), index),
                "mime_type": item.get("mime_type"),
                "modality": item.get("modality"),
                "size_bytes": item.get("size_bytes"),
                "storage_path": item.get("storage_path"),
                "sha256": item.get("sha256"),
            }
        )
    return result


def _summary_from_report(report: dict[str, Any], verdict: dict[str, Any]) -> str:
    summary = report.get("summary") or verdict.get("analysis_summary") or verdict.get("llm_ruling") or ""
    return redact_public_text(str(summary)).strip()[:360]


def build_markdown_from_report_row(report: dict[str, Any]) -> str:
    verdict = normalize_final_verdict(report.get("verdict_payload") or {})
    lines = [
        "# 公开案例研判报告",
        "",
        f"- 裁决结果：{report.get('verdict') or verdict.get('verdict') or 'inconclusive'}",
    ]
    confidence = report.get("confidence_overall") or verdict.get("confidence_overall")
    if confidence is not None:
        lines.append(f"- 综合置信度：{float(confidence) * 100:.1f}%")
    summary = report.get("summary") or verdict.get("analysis_summary")
    if summary:
        lines.extend(["", "## 摘要", str(summary)])
    key_evidence = report.get("key_evidence") or verdict.get("key_evidence") or []
    if key_evidence:
        lines.extend(["", "## 关键证据"])
        for item in key_evidence:
            lines.append(f"- {item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)}")
    recommendations = report.get("recommendations") or verdict.get("recommendations") or []
    if recommendations:
        lines.extend(["", "## 处置建议"])
        for item in recommendations:
            lines.append(f"- {item}")
    return redact_public_markdown("\n".join(lines))


def build_case_library_entry(task: dict[str, Any], report: dict[str, Any], report_markdown: str) -> dict[str, Any]:
    files = _task_files(task)
    case_prompt = task.get("description") or _metadata(task).get("case_prompt") or ""
    verdict = normalize_final_verdict(report.get("verdict_payload") or {})
    confidence = report.get("confidence_overall", verdict.get("confidence_overall"))
    title = redact_public_text(str(task.get("title") or "未命名公开案例")).strip()[:120] or "未命名公开案例"
    public_files = _public_files(files)

    return {
        "task_id": task.get("id"),
        "user_id": task.get("user_id"),
        "status": "published",
        "title": title,
        "media_category": _derive_media_category(files, task.get("input_type")),
        "summary": _summary_from_report(report, verdict),
        "verdict": report.get("verdict") or verdict.get("verdict") or "inconclusive",
        "confidence_overall": confidence,
        "difficulty": _difficulty(confidence),
        "public_files": public_files,
        "report_markdown": redact_public_markdown(report_markdown),
        "content_fingerprint": build_case_fingerprint(files, case_prompt),
        "published_at": utc_now_iso(),
    }


def find_duplicate_case(client: Any, files: list[dict[str, Any]] | None, case_prompt: str | None) -> dict[str, Any] | None:
    fingerprint = build_case_fingerprint(files, case_prompt)
    if not fingerprint:
        return None
    try:
        resp = (
            client.table("case_library_entries")
            .select("*")
            .eq("status", "published")
            .eq("content_fingerprint", fingerprint)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.warning("Failed to check duplicate public case: %s", exc)
        return None


def public_case_duplicate_metadata(client: Any, files: list[dict[str, Any]] | None, case_prompt: str | None) -> dict[str, Any]:
    duplicate = find_duplicate_case(client, files, case_prompt)
    return {
        "casebase_duplicate": bool(duplicate),
        "casebase_duplicate_case_id": duplicate.get("id") if duplicate else None,
        "casebase_fingerprint": build_case_fingerprint(files, case_prompt),
    }


def ensure_case_library_entry(
    client: Any,
    task: dict[str, Any] | None,
    report: dict[str, Any] | None,
    report_markdown: str | None = None,
) -> dict[str, Any]:
    """Create public case entry once, returning duplicate/skipped/created status."""
    if not wants_public_case(task):
        return {"status": "skipped", "reason": "not_requested", "entry": None}
    if not report:
        return {"status": "skipped", "reason": "missing_report", "entry": None}

    task = task or {}
    report = report or {}
    files = _task_files(task)
    case_prompt = task.get("description") or _metadata(task).get("case_prompt") or ""
    duplicate = find_duplicate_case(client, files, case_prompt)
    if duplicate:
        return {"status": "duplicate", "entry": duplicate}

    markdown = report_markdown if report_markdown is not None else build_markdown_from_report_row(report)
    entry = build_case_library_entry(task, report, markdown)
    try:
        resp = client.table("case_library_entries").insert(entry).execute()
        created = resp.data[0] if resp.data else entry
        return {"status": "created", "entry": created}
    except Exception as exc:
        logger.error("Failed to create public case entry for task %s: %s", task.get("id"), exc)
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "entry": None}


def sanitize_case_for_response(row: dict[str, Any], *, include_report: bool = False) -> dict[str, Any]:
    public_files = []
    for item in row.get("public_files") or []:
        if not isinstance(item, dict):
            continue
        public_files.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "mime_type": item.get("mime_type"),
                "modality": item.get("modality"),
                "size_bytes": item.get("size_bytes"),
                "storage_path": None,
            }
        )
    payload = {
        "id": row.get("id"),
        "source_kind": row.get("source_kind") or "public",
        "task_id": row.get("task_id"),
        "title": row.get("title"),
        "media_category": row.get("media_category"),
        "summary": row.get("summary"),
        "verdict": row.get("verdict"),
        "confidence_overall": row.get("confidence_overall"),
        "difficulty": row.get("difficulty"),
        "public_files": public_files,
        "published_at": row.get("published_at"),
    }
    if include_report:
        payload["report_markdown"] = row.get("report_markdown") or ""
    return payload


def find_public_file(row: dict[str, Any], file_id: str) -> dict[str, Any] | None:
    for item in row.get("public_files") or []:
        if isinstance(item, dict) and str(item.get("id")) == str(file_id):
            return item
    return None
