"""Internal AI-generated text detection tool for agent tool matrices."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.agents.tools.text_detection import analyze_text
from app.config import settings

logger = logging.getLogger(__name__)

MAX_INTERNAL_TEXT_AIGC_CHARS = 50_000
TEXT_AIGC_TOOL_NAME = "ai_text_detector"
INTERNAL_TEXT_AIGC_PROVIDER = "internal_text_detector"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_score(value: Any, fallback: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


async def detect_ai_generated_text(text: str, *, target: str = "uploaded_text") -> dict[str, Any]:
    """Run the built-in text detector and normalize it as an agent tool result."""
    started_at = _now()
    normalized_text = (text or "").strip()
    if not settings.TEXT_AIGC_DETECTOR_ENABLED:
        return {
            "tool": TEXT_AIGC_TOOL_NAME,
            "provider": INTERNAL_TEXT_AIGC_PROVIDER,
            "target": target,
            "status": "disabled",
            "degraded": True,
            "analysis_available": False,
            "external_analysis_available": False,
            "summary": "内部文本 AIGC 检测未启用",
            "started_at": started_at,
            "completed_at": _now(),
        }
    if not normalized_text:
        return {
            "tool": TEXT_AIGC_TOOL_NAME,
            "provider": INTERNAL_TEXT_AIGC_PROVIDER,
            "target": target,
            "status": "skipped",
            "degraded": False,
            "analysis_available": False,
            "external_analysis_available": False,
            "summary": "文本为空，跳过内部文本 AIGC 检测",
            "started_at": started_at,
            "completed_at": _now(),
        }

    try:
        internal = await analyze_text(normalized_text[:MAX_INTERNAL_TEXT_AIGC_CHARS])
    except Exception as exc:
        logger.warning("Internal text AIGC detector failed for %s: %s", target, exc)
        return {
            "tool": TEXT_AIGC_TOOL_NAME,
            "provider": INTERNAL_TEXT_AIGC_PROVIDER,
            "target": target,
            "status": "failed",
            "degraded": True,
            "analysis_available": False,
            "external_analysis_available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "summary": "内部文本 AIGC 检测失败，需人工复核文本生成方式",
            "started_at": started_at,
            "completed_at": _now(),
        }

    ai_probability = _clamp_score(internal.get("ai_probability"), 0.5)
    confidence = _clamp_score(internal.get("confidence"), 0.5)
    is_ai_generated = bool(internal.get("is_ai_generated", ai_probability >= settings.TEXT_AIGC_AI_THRESHOLD))
    degraded = bool(internal.get("degraded"))
    return {
        "tool": TEXT_AIGC_TOOL_NAME,
        "provider": INTERNAL_TEXT_AIGC_PROVIDER,
        "target": target,
        "status": "success",
        "degraded": degraded,
        "analysis_available": True,
        "external_analysis_available": False,
        "method": "internal_text_claim_extract",
        "is_ai_generated": is_ai_generated,
        "ai_probability": ai_probability,
        "confidence": round(confidence, 4),
        "manipulation_score": _clamp_score(internal.get("manipulation_score"), 0.0),
        "social_engineering_score": _clamp_score((internal.get("social_engineering") or {}).get("score"), 0.0),
        "local_ai_score": _clamp_score(internal.get("local_ai_score"), 0.0),
        "detection_signals": internal.get("detection_signals") or [],
        "key_claims": internal.get("key_claims") or [],
        "anomalies": internal.get("anomalies") or [],
        "structural_analysis": internal.get("structural_analysis") or {},
        "social_engineering": internal.get("social_engineering") or {},
        "extracted_urls": internal.get("extracted_urls") or [],
        "internal_text_analysis": internal,
        "summary": f"内部文本检测: AI 生成概率 {ai_probability:.1%}，置信度 {confidence:.1%}",
        "started_at": started_at,
        "completed_at": _now(),
    }
