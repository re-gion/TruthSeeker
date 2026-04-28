"""智能降级控制器 - 跟踪 API 可用性并提供降级回退策略"""

import logging

logger = logging.getLogger(__name__)


class DegradationManager:
    """Track API availability and provide fallback strategies.

    Each API is tracked independently. After _max_failures consecutive
    failures an API is marked as "failed" and callers should fall back
    to the most degraded strategy.
    """

    def __init__(self):
        self.api_status: dict[str, str] = {}      # "reality_defender": "ok"|"degraded"|"failed"
        self.failure_counts: dict[str, int] = {}
        self._max_failures = 3  # after 3 failures, mark as failed

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report_success(self, api_name: str):
        """Report that an API call succeeded, reset failure count."""
        self.failure_counts[api_name] = 0
        self.api_status[api_name] = "ok"
        logger.info("API [%s] reported success → status=ok", api_name)

    def report_failure(self, api_name: str, error: Exception):
        """Report that an API call failed, increment failure count."""
        count = self.failure_counts.get(api_name, 0) + 1
        self.failure_counts[api_name] = count
        logger.warning(
            "API [%s] reported failure (%s): %s — consecutive failures=%d",
            api_name,
            type(error).__name__,
            error,
            count,
        )
        if count >= self._max_failures:
            self.api_status[api_name] = "failed"
        elif count >= 1:
            self.api_status[api_name] = "degraded"

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def is_available(self, api_name: str) -> bool:
        """Check if an API is available (status != 'failed')."""
        return self.api_status.get(api_name, "ok") != "failed"

    def get_status(self, api_name: str) -> str:
        """Get current status of an API ('ok'|'degraded'|'failed')."""
        return self.api_status.get(api_name, "ok")

    def get_degradation_level(self, api_name: str) -> str:
        """Get degradation level: 'full'|'degraded'|'minimal'.

        - 'full'    → API is healthy, no degradation needed
        - 'degraded'→ API has intermittent failures, use fallback
        - 'minimal' → API is completely down, use minimal result
        """
        status = self.api_status.get(api_name, "ok")
        if status == "ok":
            return "full"
        if status == "degraded":
            return "degraded"
        return "minimal"

    def get_summary(self) -> dict:
        """Get a summary dict for state tracking."""
        return {
            "api_status": dict(self.api_status),
            "failure_counts": dict(self.failure_counts),
        }


# ======================================================================
# Fallback analysis functions
# ======================================================================

async def fallback_metadata_analysis(file_url: str, file_type: str) -> dict:
    """Degraded forensics analysis using only metadata heuristics.

    Uses extract_media_metadata from threat_intel to check for anomalies.
    Confidence capped at 0.5.
    """
    from app.agents.tools.threat_intel import extract_media_metadata

    try:
        metadata = await extract_media_metadata(file_url, file_type)
    except Exception as exc:
        logger.error("fallback_metadata_analysis failed: %s", exc)
        metadata = {
            "format": "unknown",
            "manipulation_indicators": ["元数据提取失败"],
            "exif_anomalies": [],
            "has_exif": False,
            "compression_artifacts": False,
        }

    manipulation_indicators = metadata.get("manipulation_indicators", [])
    exif_anomalies = metadata.get("exif_anomalies", [])
    has_exif = metadata.get("has_exif", False)
    compression_artifacts = metadata.get("compression_artifacts", False)

    # Heuristic scoring based on metadata anomalies
    anomaly_count = len(manipulation_indicators) + len(exif_anomalies)
    if anomaly_count >= 3:
        deepfake_probability = 0.45
        is_deepfake = True
    elif anomaly_count >= 1:
        deepfake_probability = 0.25
        is_deepfake = False
    else:
        deepfake_probability = 0.05
        is_deepfake = False

    # Confidence is capped at 0.5
    confidence = min(0.5, 0.3 + anomaly_count * 0.1)

    return {
        "is_deepfake": is_deepfake,
        "deepfake_probability": deepfake_probability,
        "confidence": confidence,
        "model": "metadata_heuristic",
        "degraded": True,
        "degradation_level": "degraded",
        "details": {
            "method": "metadata_heuristic",
            "metadata": metadata,
            "anomaly_count": anomaly_count,
            "manipulation_indicators": manipulation_indicators,
            "exif_anomalies": exif_anomalies,
            "has_exif": has_exif,
            "compression_artifacts": compression_artifacts,
        },
        "models": [],
        "frame_inferences": [],
        "audio_score": None,
        "indicators": manipulation_indicators + exif_anomalies,
    }


async def fallback_osint_analysis(file_url: str, file_type: str) -> dict:
    """Degraded OSINT analysis using only local metadata.

    Confidence capped at 0.4.
    """
    from app.agents.tools.threat_intel import extract_media_metadata

    try:
        metadata = await extract_media_metadata(file_url, file_type)
    except Exception as exc:
        logger.error("fallback_osint_analysis failed: %s", exc)
        metadata = {
            "format": "unknown",
            "manipulation_indicators": [],
            "exif_anomalies": [],
        }

    manipulation_indicators = metadata.get("manipulation_indicators", [])
    exif_anomalies = metadata.get("exif_anomalies", [])

    indicators_found = len(manipulation_indicators) + len(exif_anomalies)
    threat_score = min(0.35, indicators_found * 0.1)

    return {
        "threat_score": threat_score,
        "confidence": min(0.4, 0.2 + indicators_found * 0.05),
        "degraded": True,
        "degradation_level": "degraded",
        "indicators": manipulation_indicators + exif_anomalies,
        "domain_info": {"method": "metadata_heuristic"},
        "virustotal": None,
        "details": {
            "method": "metadata_heuristic",
            "metadata": metadata,
        },
    }


def minimal_forensics_result(input_type: str = "unknown") -> dict:
    """Minimal result when all APIs fail. Confidence = 0.2."""
    return {
        "is_deepfake": False,
        "deepfake_probability": 0.0,
        "confidence": 0.2,
        "model": "minimal_fallback",
        "degraded": True,
        "degradation_level": "minimal",
        "details": {
            "method": "minimal_fallback",
            "reason": "所有鉴伪 API 不可用，无法进行深度分析",
        },
        "models": [],
        "frame_inferences": [],
        "audio_score": None,
        "indicators": ["所有鉴伪 API 不可用，无法进行深度分析"],
    }


def minimal_osint_result(input_type: str = "unknown") -> dict:
    """Minimal OSINT result when all APIs fail. Confidence = 0.2."""
    return {
        "threat_score": 0.0,
        "confidence": 0.2,
        "degraded": True,
        "degradation_level": "minimal",
        "indicators": ["所有 OSINT API 不可用，无法进行威胁情报分析"],
        "domain_info": {"method": "minimal_fallback"},
        "virustotal": None,
        "details": {
            "method": "minimal_fallback",
            "reason": "所有 OSINT API 不可用，无法进行威胁情报分析",
        },
    }


# ======================================================================
# 全局共享实例 — 所有 Agent 节点应使用此实例以共享降级状态
# ======================================================================

shared_degradation = DegradationManager()
