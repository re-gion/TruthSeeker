"""Deepfake Detection Tool - Reality Defender API with mock fallback

Reality Defender API 流程:
1. POST /api/files/aws-presigned → 获取签名URL + request_id
2. PUT <signedUrl> → 上传文件二进制数据
3. GET /api/media/users/{request_id} → 轮询获取检测结果
"""
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.agents.tools.fallback import shared_degradation
from app.config import settings

logger = logging.getLogger(__name__)


RD_BASE = "https://api.prd.realitydefender.xyz"

# 文件类型映射: input_type → (extension, supported_types)
FILE_TYPE_MAP = {
    "video": [".mp4", ".mov"],
    "audio": [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".alac"],
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "text": [".txt"],
}

# Per-type size limits (aligned with Reality Defender API docs)
SIZE_LIMITS = {
    "image": 50 * 1024 * 1024,   # 50 MB
    "audio": 20 * 1024 * 1024,   # 20 MB
    "video": 250 * 1024 * 1024,  # 250 MB
    "text": 5 * 1024 * 1024,     # 5 MB
}

# 默认文件扩展名
DEFAULT_EXTENSIONS = {
    "video": ".mp4",
    "audio": ".mp3",
    "image": ".jpg",
    "text": ".txt",
}


def _stable_float(seed: str, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
    return minimum + (maximum - minimum) * value


def _stable_int(seed: str, minimum: int, maximum: int) -> int:
    if maximum <= minimum:
        return minimum
    value = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    return minimum + value % (maximum - minimum + 1)


def _stable_sample(items: list[str], seed: str, count: int) -> list[str]:
    ranked = sorted(
        items,
        key=lambda item: hashlib.sha256(f"{seed}:{item}".encode("utf-8")).hexdigest(),
    )
    return ranked[:count]


def _get_api_key() -> str:
    """获取可用的 Reality Defender API Key"""
    return settings.REALITY_DEFENDER_API_KEY


async def _download_file(file_url: str) -> tuple[bytes, str]:
    """从 Supabase 签名 URL 下载文件，返回 (字节数据, 文件名)"""
    async with httpx.AsyncClient(timeout=settings.REALITY_DEFENDER_DOWNLOAD_TIMEOUT_SECONDS) as client:
        resp = await client.get(file_url, follow_redirects=True)
        resp.raise_for_status()

        # 尝试从 Content-Disposition 或 URL 路径提取文件名
        filename = "upload.mp4"
        cd = resp.headers.get("content-disposition", "")
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('"\'')
        elif "/" in file_url:
            filename = file_url.split("/")[-1].split("?")[0] or "upload.mp4"

        return resp.content, filename


async def _request_presigned_url(
    client: httpx.AsyncClient, api_key: str, filename: str
) -> tuple[str, str]:
    """步骤1: 请求预签名上传 URL

    Returns: (signed_url, request_id)
    """
    resp = await client.post(
        f"{RD_BASE}/api/files/aws-presigned",
        json={"fileName": filename},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    data = resp.json()

    response_data = data.get("response") or data
    if not isinstance(response_data, dict):
        raise ValueError(f"RD presigned response unexpected format: {data}")

    signed_url = response_data.get("signedUrl", "")
    # RD 响应格式变更: requestId 可能在顶层，也可能在 response 内部
    request_id = (
        data.get("requestId", data.get("request_id", ""))
        or response_data.get("requestId", response_data.get("request_id", ""))
    )

    if not signed_url:
        raise ValueError(f"RD presigned response missing signedUrl: {data}")

    if not request_id:
        logger.warning("RD presigned response missing requestId; full response: %s", data)

    return signed_url, request_id


async def _upload_to_presigned(
    client: httpx.AsyncClient, signed_url: str, file_data: bytes
) -> None:
    """步骤2: 上传文件到预签名 URL"""
    resp = await client.put(
        signed_url,
        content=file_data,
        timeout=settings.REALITY_DEFENDER_UPLOAD_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()


async def _poll_result(
    client: httpx.AsyncClient, api_key: str, request_id: str, max_attempts: int | None = None
) -> dict:
    """步骤3: 轮询检测结果

    使用固定间隔，默认总轮询预算小于 Forensics 外层工具超时。
    """
    max_attempts = max_attempts or settings.REALITY_DEFENDER_POLL_MAX_ATTEMPTS
    delay = settings.REALITY_DEFENDER_POLL_DELAY_SECONDS

    for attempt in range(max_attempts):
        await asyncio.sleep(delay)

        resp = await client.get(
            f"{RD_BASE}/api/media/users/{request_id}",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        )

        if resp.status_code == 404:
            # 还在处理中
            continue

        resp.raise_for_status()
        data = resp.json()

        response_data = data.get("response", data)

        # New format: resultsSummary present means analysis is complete
        if response_data.get("resultsSummary"):
            return response_data

        # Old format: check top-level status
        status = response_data.get("status", "").upper()
        if status in ("COMPLETE", "COMPLETED", "DONE"):
            return response_data
        elif status in ("FAILED", "ERROR"):
            raise RuntimeError(f"RD analysis failed: {response_data}")
        # PENDING / PROCESSING → 继续轮询

    raise TimeoutError(f"RD analysis timed out after {max_attempts} polls")


def _parse_rd_result(rd_data: dict) -> dict:
    """解析 Reality Defender 返回结果为标准化格式

    Supports both new format (resultsSummary) and old format (ensemble).
    New format: resultsSummary.status (AUTHENTIC/FAKE/SUSPICIOUS/NOT_APPLICABLE/UNABLE_TO_EVALUATE)
                resultsSummary.metadata.finalScore (0-100 scale)
    """
    # 收集各模型独立分数
    model_scores = []
    for m in rd_data.get("models", []):
        model_scores.append({
            "name": m.get("name", m.get("model", "unknown")),
            "score": float(m.get("score", 0.0)),
            "label": m.get("label", "unknown"),
        })

    # 帧级推理（视频）
    frame_inferences = []
    for fi in rd_data.get("frameInferences", rd_data.get("frame_inferences", [])):
        frame_inferences.append({
            "frame": fi.get("frame", fi.get("frameNumber", 0)),
            "timestamp": fi.get("timestamp", ""),
            "score": float(fi.get("score", 0.0)),
            "label": fi.get("label", "unknown"),
        })

    audio_score = rd_data.get("audioScore") or rd_data.get("audio_score")

    # --- 优先使用新格式 resultsSummary ---
    results_summary = rd_data.get("resultsSummary")
    if results_summary:
        status = results_summary.get("status", "").upper()
        metadata = results_summary.get("metadata", {})
        final_score_raw = metadata.get("finalScore")

        # API 返回 0-100，转为 0-1
        deepfake_probability = float(final_score_raw) / 100.0 if final_score_raw is not None else 0.0

        if status == "FAKE":
            is_deepfake = True
        elif status == "SUSPICIOUS":
            is_deepfake = True
        elif status == "NOT_APPLICABLE":
            reasons = metadata.get("reasons", [])
            reason_msg = "; ".join(r.get("message", "") for r in reasons) if reasons else ""
            logger.warning("[Reality Defender] NOT_APPLICABLE: %s", reason_msg)
            is_deepfake = False
            deepfake_probability = 0.0
        elif status == "UNABLE_TO_EVALUATE":
            error_info = results_summary.get("error", {})
            raise RuntimeError(f"RD unable to evaluate: {error_info.get('message', 'unknown')}")
        else:
            # AUTHENTIC
            is_deepfake = False
    else:
        # --- 回退旧格式 ensemble ---
        ensemble = rd_data.get("ensemble", {})
        if ensemble:
            deepfake_probability = float(ensemble.get("score", 0.0))
            is_deepfake = ensemble.get("label", "").upper() == "FAKE"
        elif model_scores:
            first = model_scores[0]
            deepfake_probability = float(first["score"])
            is_deepfake = first["label"].upper() == "FAKE"
        else:
            deepfake_probability = float(rd_data.get("score", 0.0))
            is_deepfake = rd_data.get("label", "").upper() == "FAKE"

    confidence = deepfake_probability if is_deepfake else (1.0 - deepfake_probability)

    return {
        "is_deepfake": is_deepfake,
        "confidence": confidence,
        "deepfake_probability": deepfake_probability,
        "model": "reality_defender",
        "models": model_scores,
        "frame_inferences": frame_inferences,
        "audio_score": audio_score,
        "indicators": [],
        "details": {
            "results_summary": results_summary,
            "ensemble": rd_data.get("ensemble", {}),
            "total_models": len(model_scores),
            "request_id": rd_data.get("requestId", rd_data.get("request_id", "")),
        },
        "raw_response": rd_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def analyze_with_reality_defender(file_url: str, media_type: str = "video") -> dict:
    """调用 Reality Defender API 进行 Deepfake 检测

    完整3步流程:
    1. 下载文件 → 请求预签名URL
    2. 上传文件到签名URL
    3. 轮询获取结果
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning(
            "[Reality Defender] API key not configured, using mock analysis for %s (%s)",
            file_url,
            media_type,
        )
        return await mock_deepfake_analysis(
            file_url,
            media_type,
            fallback_reason="missing_api_key",
            api_key_configured=False,
        )

    try:
        async with httpx.AsyncClient(timeout=settings.REALITY_DEFENDER_CLIENT_TIMEOUT_SECONDS) as client:
            # 步骤1: 下载源文件
            file_data, filename = await _download_file(file_url)

            # 校验文件大小（以 Reality Defender API 文档为准）
            size_limit = SIZE_LIMITS.get(media_type, 50 * 1024 * 1024)
            if len(file_data) > size_limit:
                raise ValueError(
                    f"文件大小 {len(file_data) / 1024 / 1024:.1f}MB "
                    f"超过 {media_type} 类型上限 {size_limit / 1024 / 1024:.0f}MB"
                )

            # 确保文件名有正确扩展名
            base, ext = os.path.splitext(filename)
            if not ext or ext.lower() not in [
                ".mp4", ".mov", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
                ".jpg", ".jpeg", ".png", ".gif", ".webp", ".txt",
            ]:
                ext = DEFAULT_EXTENSIONS.get(media_type, ".mp4")
                filename = f"upload{ext}"

            # 步骤2: 请求预签名 URL
            signed_url, request_id = await _request_presigned_url(client, api_key, filename)

            # 步骤3: 上传文件
            await _upload_to_presigned(client, signed_url, file_data)

            # 步骤4: 轮询结果
            if not request_id:
                raise ValueError("RD did not return request_id")

            rd_result = await _poll_result(client, api_key, request_id)

            # 解析结果
            shared_degradation.report_success("reality_defender")
            return _parse_rd_result(rd_result)

    except httpx.HTTPStatusError as e:
        logger.warning("[Reality Defender] HTTP Error %d: %s", e.response.status_code, e.response.text[:200])
        shared_degradation.report_failure("reality_defender", e)
        return await mock_deepfake_analysis(
            file_url,
            media_type,
            fallback_reason=f"http_{e.response.status_code}",
            api_key_configured=True,
        )
    except httpx.TimeoutException as e:
        logger.warning("[Reality Defender] 超时: %s", e)
        shared_degradation.report_failure("reality_defender", e)
        return await mock_deepfake_analysis(
            file_url,
            media_type,
            fallback_reason="timeout",
            api_key_configured=True,
        )
    except Exception as e:
        logger.error("[Reality Defender] 错误: %s: %s", type(e).__name__, e)
        shared_degradation.report_failure("reality_defender", e)
        return await mock_deepfake_analysis(
            file_url,
            media_type,
            fallback_reason=f"{type(e).__name__}: {e}",
            api_key_configured=True,
        )


async def mock_deepfake_analysis(
    file_url: str,
    media_type: str = "video",
    *,
    fallback_reason: str = "mock_mode",
    api_key_configured: bool = False,
) -> dict:
    """保守降级结果。

    外部 Reality Defender 不可用时，不输出“面部自然/帧间正常”等真实检测结论。
    这些字段只能说明没有拿到外部模型结论，不能反向证明图片或视频真实。
    """
    await asyncio.sleep(0.1)

    seed = f"{media_type}:{file_url}"
    fallback_prob = _stable_float(f"{seed}:fallback-probability", minimum=0.45, maximum=0.55)
    media_label = {
        "image": "图像",
        "video": "视频",
        "audio": "音频",
        "text": "文本",
    }.get(media_type, "媒体")
    indicators = [
        f"Reality Defender 未返回真实{media_label}检测结论",
        f"降级原因: {fallback_reason}",
        "当前结果仅用于流程占位，不能据此判定检材真实或无伪造痕迹",
    ]

    return {
        "is_deepfake": False,
        "confidence": 0.2,
        "deepfake_probability": fallback_prob,
        "model": "reality_defender_unavailable",
        "degraded": True,
        "analysis_available": False,
        "method": "local_fallback_no_external_verdict",
        "models": [],
        "frame_inferences": [],
        "audio_score": None,
        "details": {
            "indicators": indicators,
            "frames_analyzed": 0,
            "anomaly_score": None,
            "fallback_reason": fallback_reason,
            "api_key_configured": api_key_configured,
            "external_verdict_available": False,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def analyze_media(file_url: str, media_type: str = "video") -> dict:
    """主入口：优先调用真实 API，不可用时回退到模拟"""
    return await analyze_with_reality_defender(file_url, media_type)
