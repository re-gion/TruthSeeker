"""Dashboard overview API - public aggregated metrics for the data screen."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()
supabase = None


def _get_supabase():
    global supabase
    if supabase is None:
        from app.utils.supabase_client import supabase as active_supabase

        supabase = active_supabase
    return supabase

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

HIGH_RISK_VERDICT_ALIASES = (
    "fake",
    "forged",
    "deepfake",
    "deep fake",
    "synthetic",
    "manipulated",
    "suspicious",
    "high risk",
    "高风险",
    "伪造",
    "疑似",
    "可疑",
)

STATUS_LABELS = {
    "pending": "待处理",
    "queued": "待处理",
    "analyzing": "分析中",
    "processing": "分析中",
    "running": "分析中",
    "completed": "已完成",
    "complete": "已完成",
    "done": "已完成",
    "failed": "失败",
    "error": "失败",
    "cancelled": "已取消",
}

INPUT_TYPE_LABELS = {
    "video": "视频内容",
    "audio": "音频内容",
    "image": "图像内容",
    "text": "文本内容",
}

EVIDENCE_CATEGORY_LABELS = {
    "visual": "视觉证据",
    "image": "视觉证据",
    "video": "视觉证据",
    "frame": "视觉证据",
    "face": "视觉证据",
    "audio": "音频证据",
    "voice": "音频证据",
    "voiceprint": "音频证据",
    "text": "文本证据",
    "metadata": "文本证据",
    "ocr": "文本证据",
    "transcript": "文本证据",
    "caption": "文本证据",
    "osint": "开源情报",
    "source": "开源情报",
    "trace": "开源情报",
    "reverse": "开源情报",
    "provenance": "开源情报",
}

EVIDENCE_SOURCE_LABELS = {
    "frameforensics": "帧级取证",
    "faceswaptrace": "换脸痕迹",
    "reversesearch": "反向检索",
    "voiceprint": "声纹比对",
    "metadata": "元数据校验",
}


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _read_record(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = __import__("json").loads(value)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _read_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = __import__("json").loads(value)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _read_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _normalize_token(value: Any) -> str:
    return _read_string(value).lower().replace(" ", "").replace("_", "").replace("-", "")


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _to_datetime(value: Any) -> datetime | None:
    text = _read_string(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _format_zoned_date(date: datetime) -> str:
    return date.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d")


def _format_day_label(date: datetime) -> str:
    return date.astimezone(SHANGHAI_TZ).strftime("%m-%d")


def _is_completed_status(status: Any) -> bool:
    return _normalize_token(status) in {
        "completed",
        "complete",
        "done",
        "finished",
        "resolved",
        "success",
        "succeeded",
    }


def _is_high_risk_verdict_alias(value: Any) -> bool:
    normalized = _normalize_token(value)
    return bool(normalized) and any(_normalize_token(alias) == normalized for alias in HIGH_RISK_VERDICT_ALIASES)


def _display_status(status: Any) -> str:
    normalized = _normalize_token(status)
    return STATUS_LABELS.get(normalized) or _read_string(status) or "未分类"


def _display_input_type(input_type: Any) -> str:
    normalized = _normalize_token(input_type)
    return INPUT_TYPE_LABELS.get(normalized) or "未分类"


def _extract_result_candidate(value: Any, keys: list[str]) -> str:
    record = _read_record(value)
    if not record:
        return ""

    for key in keys:
        direct = _read_string(record.get(key))
        if direct:
            return direct

        nested = _read_record(record.get(key))
        if not nested:
            continue
        for nested_key in ("label", "value", "name", "type", "category"):
            nested_value = _read_string(nested.get(nested_key))
            if nested_value:
                return nested_value

    return ""


def _extract_verdict_label(value: Any) -> str:
    return (
        _extract_result_candidate(value, ["verdict", "verdict_label", "label", "result", "status", "type"])
        or _read_string(value)
    )


def _extract_threat_label(value: Any) -> str:
    return _extract_result_candidate(value, ["threat_type", "category", "type", "verdict_cn", "verdict"])


def _calculate_task_response_ms(task: dict[str, Any]) -> int | None:
    if not _is_completed_status(task.get("status")):
        return None

    direct_value = _to_number(task.get("response_ms") or task.get("responseTimeMs") or task.get("duration_ms"))
    if direct_value is not None and direct_value > 0:
        return round(direct_value)

    started_at = _to_datetime(task.get("started_at"))
    completed_at = _to_datetime(task.get("completed_at"))
    if not started_at or not completed_at:
        return None

    diff_ms = (completed_at - started_at).total_seconds() * 1000
    return round(diff_ms) if diff_ms > 0 else None


def _build_threat_snapshots(tasks: list[dict[str, Any]], reports: list[dict[str, Any]]) -> list[dict[str, str]]:
    snapshots: dict[str, dict[str, str]] = {}

    for task in tasks:
        task_id = _read_string(task.get("id"))
        if not task_id:
            continue
        result_payload = task.get("result") or task.get("verdict")
        verdict_label = _extract_verdict_label(result_payload)
        threat_label = _extract_threat_label(result_payload) or _display_input_type(task.get("input_type"))
        snapshots[task_id] = {
            "task_id": task_id,
            "verdict_label": verdict_label,
            "threat_label": threat_label,
        }

    for report in reports:
        task_id = _read_string(report.get("task_id"))
        if not task_id or task_id in snapshots:
            continue
        verdict_payload = report.get("verdict_payload") or report.get("verdict")
        verdict_label = _extract_verdict_label(verdict_payload)
        threat_label = _extract_threat_label(verdict_payload) or verdict_label or "未分类"
        snapshots[task_id] = {
            "task_id": task_id,
            "verdict_label": verdict_label,
            "threat_label": threat_label,
        }

    return list(snapshots.values())


def _build_distribution_items(labels: list[str]) -> list[dict[str, float | int | str]]:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}

    for index, label in enumerate(labels):
        normalized = _read_string(label) or "未分类"
        counts[normalized] = counts.get(normalized, 0) + 1
        first_seen.setdefault(normalized, index)

    total = sum(counts.values())
    ordered = sorted(counts.items(), key=lambda item: (-item[1], first_seen.get(item[0], 0)))
    return [
        {
            "label": label,
            "value": value,
            "share": (value / total) if total else 0,
        }
        for label, value in ordered
    ]


def _create_recent_days(generated_at: datetime, days: int = 7) -> list[datetime]:
    anchor = generated_at.astimezone(timezone.utc)
    return [anchor - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _build_trend_series(tasks: list[dict[str, Any]], generated_at_iso: str) -> list[dict[str, Any]]:
    generated_at = _to_datetime(generated_at_iso) or datetime.now(timezone.utc)
    days = _create_recent_days(generated_at)
    completed_counts = {_format_zoned_date(day): 0 for day in days}
    response_buckets = {_format_zoned_date(day): {"total": 0, "count": 0} for day in days}

    for task in tasks:
        completed_at = _to_datetime(task.get("completed_at"))
        if completed_at and _is_completed_status(task.get("status")):
            key = _format_zoned_date(completed_at)
            if key in completed_counts:
                completed_counts[key] += 1

        response_ms = _calculate_task_response_ms(task)
        if response_ms is None or not completed_at:
            continue
        response_key = _format_zoned_date(completed_at)
        bucket = response_buckets.get(response_key)
        if not bucket:
            continue
        bucket["total"] += response_ms
        bucket["count"] += 1

    return [
        {
            "id": "daily-completions",
            "title": "近7日完成任务量",
            "unit": "件",
            "points": [
                {"label": _format_day_label(day), "value": completed_counts[_format_zoned_date(day)]}
                for day in days
            ],
        },
        {
            "id": "response-time",
            "title": "近7日平均响应时间",
            "unit": "ms",
            "points": [
                {
                    "label": _format_day_label(day),
                    "value": round(response_buckets[_format_zoned_date(day)]["total"] / response_buckets[_format_zoned_date(day)]["count"])
                    if response_buckets[_format_zoned_date(day)]["count"]
                    else 0,
                }
                for day in days
            ],
        },
    ]


def _map_evidence_category(value: Any) -> str:
    normalized = _normalize_token(value)
    if not normalized:
        return "其他证据"
    for token, label in EVIDENCE_CATEGORY_LABELS.items():
        if token in normalized:
            return label
    return _read_string(value) or "其他证据"


def _map_evidence_source_label(source: Any, category_label: str) -> str:
    normalized = _normalize_token(source)
    if not normalized:
        return category_label
    for token, label in EVIDENCE_SOURCE_LABELS.items():
        if token == normalized:
            return label
    return _read_string(source) or category_label


def _display_verdict_outcome(value: Any) -> str:
    verdict = _extract_verdict_label(value)
    normalized = _normalize_token(verdict)
    if _is_high_risk_verdict_alias(verdict):
        return "高风险结论"
    if normalized in {"authentic", "real", "benign", "true", "真实", "可信"}:
        return "真实结论"
    return verdict or "待判定"


def _build_evidence_mix(reports: list[dict[str, Any]]) -> list[dict[str, float | int | str]]:
    labels: list[str] = []
    for report in reports:
        evidence_items = _read_list(report.get("key_evidence"))
        if not evidence_items:
            verdict_payload = _read_record(report.get("verdict_payload")) or {}
            evidence_items = _read_list(verdict_payload.get("key_evidence"))
        for entry in evidence_items:
            if not _is_record(entry):
                continue
            labels.append(_map_evidence_category(entry.get("type") or entry.get("source")))
    return _build_distribution_items(labels) if labels else []


def _build_flow_sankey(tasks: list[dict[str, Any]], reports: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not reports:
        return {"nodes": [], "links": []}

    input_labels = {
        _read_string(task.get("id")): _display_input_type(task.get("input_type"))
        for task in tasks
        if _read_string(task.get("id"))
    }
    node_order: dict[str, None] = {}
    link_counts: dict[tuple[str, str], int] = {}

    for report in reports:
        task_id = _read_string(report.get("task_id"))
        input_label = input_labels.get(task_id, "未知输入")
        verdict_label = _display_verdict_outcome(report.get("verdict_payload") or report.get("verdict"))
        evidence_items = _read_list(report.get("key_evidence"))
        if not evidence_items:
            verdict_payload = _read_record(report.get("verdict_payload")) or {}
            evidence_items = _read_list(verdict_payload.get("key_evidence"))

        for entry in evidence_items:
            if not _is_record(entry):
                continue
            category_label = _map_evidence_category(entry.get("type") or entry.get("source"))
            middle_label = _map_evidence_source_label(entry.get("source"), category_label)

            node_order.setdefault(input_label, None)
            node_order.setdefault(middle_label, None)
            node_order.setdefault(verdict_label, None)

            link_counts[(input_label, middle_label)] = link_counts.get((input_label, middle_label), 0) + 1
            link_counts[(middle_label, verdict_label)] = link_counts.get((middle_label, verdict_label), 0) + 1

    return {
        "nodes": [{"name": name} for name in node_order],
        "links": [
            {"source": source, "target": target, "value": value}
            for (source, target), value in link_counts.items()
        ],
    }


def _build_capability_metrics(
    reports: list[dict[str, Any]],
    consultation_invites: list[dict[str, Any]],
    consultation_sessions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    report_task_ids = {
        _read_string(report.get("task_id"))
        for report in reports
        if _read_string(report.get("task_id"))
    }
    consultation_task_ids = {
        _read_string(session.get("task_id"))
        for session in consultation_sessions
        if _read_string(session.get("task_id"))
    }
    consultation_task_ids.update({
        _read_string(invite.get("task_id"))
        for invite in consultation_invites
        if _read_string(invite.get("task_id"))
    })
    return [
        {
            "id": "reports-generated",
            "label": "已生成报告",
            "value": len(reports),
            "helper": "已入库的鉴定报告总量",
        },
        {
            "id": "consultation-triggered",
            "label": "会诊触发任务",
            "value": len(consultation_task_ids),
            "helper": "触发专家会诊的唯一任务数",
        },
        {
            "id": "reports-covered",
            "label": "报告覆盖任务",
            "value": len(report_task_ids),
            "helper": "已形成报告闭环的唯一任务数",
        },
    ]


def _select_rows(table: str, columns: str, warnings: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    try:
        response = _get_supabase().table(table).select(columns).execute()
    except Exception as exc:
        logger.warning("dashboard table read failed for %s: %s", table, exc)
        if warnings is not None:
            warnings.append({
                "table": table,
                "message": f"{table} 数据源读取失败，当前指标可能不完整",
            })
        return []
    if not getattr(response, "data", None):
        return []
    return [row for row in response.data if isinstance(row, dict)]


@router.get("/overview")
async def get_dashboard_overview(request: Request):
    generated_at = datetime.now(timezone.utc)
    generated_at_iso = generated_at.isoformat()
    data_warnings: list[dict[str, str]] = []
    user_id = getattr(request.state, "user_id", None)

    tasks = _select_rows(
        "tasks",
        "id,user_id,status,input_type,result,started_at,completed_at,created_at",
        data_warnings,
    )
    if user_id and user_id != "anonymous":
        tasks = [task for task in tasks if task.get("user_id") == user_id]

    task_ids = {_read_string(task.get("id")) for task in tasks if _read_string(task.get("id"))}

    reports = _select_rows(
        "reports",
        "task_id,verdict,generated_at,key_evidence,verdict_payload",
        data_warnings,
    )
    reports = [report for report in reports if _read_string(report.get("task_id")) in task_ids]

    consultation_invites = _select_rows(
        "consultation_invites",
        "task_id,status,created_at,expires_at",
        data_warnings,
    )
    consultation_invites = [
        invite for invite in consultation_invites
        if _read_string(invite.get("task_id")) in task_ids
    ]
    consultation_sessions = _select_rows(
        "consultation_sessions",
        "task_id,status,created_at,closed_at",
        data_warnings,
    )
    consultation_sessions = [
        session for session in consultation_sessions
        if _read_string(session.get("task_id")) in task_ids
    ]

    threat_snapshots = _build_threat_snapshots(tasks, reports)
    shanghai_today = _format_zoned_date(generated_at)
    high_risk_tasks = sum(1 for snapshot in threat_snapshots if _is_high_risk_verdict_alias(snapshot["verdict_label"]))
    completed_today = sum(
        1
        for task in tasks
        if _is_completed_status(task.get("status"))
        and _to_datetime(task.get("completed_at"))
        and _format_zoned_date(_to_datetime(task.get("completed_at"))) == shanghai_today
    )
    response_samples = [
        response_ms
        for response_ms in (_calculate_task_response_ms(task) for task in tasks)
        if isinstance(response_ms, int) and response_ms > 0
    ]

    return {
        "generated_at": generated_at_iso,
        "kpis": {
            "total_tasks": len(tasks),
            "high_risk_tasks": high_risk_tasks,
            "average_response_ms": round(sum(response_samples) / len(response_samples)) if response_samples else 0,
            "completed_today": completed_today,
        },
        "trend_series": _build_trend_series(tasks, generated_at_iso),
        "threat_mix": _build_distribution_items([snapshot["threat_label"] for snapshot in threat_snapshots]),
        "status_breakdown": _build_distribution_items([_display_status(task.get("status")) for task in tasks]),
        "evidence_mix": _build_evidence_mix(reports),
        "flow_sankey": _build_flow_sankey(tasks, reports),
        "capability_metrics": _build_capability_metrics(reports, consultation_invites, consultation_sessions),
        "data_warnings": data_warnings,
    }
