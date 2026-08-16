"""视频检材观察：原生视频内联 + ffmpeg 关键帧抽取兜底。

kimi-k2.6（Moonshot 官方平台）原生支持视频理解，但只有 official 端点确认
支持 video_url；SiliconFlow 视频输入未确认，Kimi coding 端点连图片都不支持。
因此取证阶段的多模态观察按以下优先级进行：

1. official 提供商且视频不超过内联上限 → base64 data URI 走 video_url；
2. 其他提供商 / 视频过大 / 内联准备失败 → ffmpeg 均匀抽取关键帧，按图片传入；
3. 两条路都不可用 → 保持文本引用说明（模型明确可见输入边界）。

关键帧抽取与 audio_transcription 共用同一套 ffmpeg/ffprobe 解析与降级约定。
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import tempfile

from app.agents.tools.audio_transcription import _resolve_binary, _run_process
from app.config import settings
from app.services.evidence_access import download_evidence_bytes

logger = logging.getLogger(__name__)

# 官方平台请求 Body 上限 100MB，base64 膨胀约 4/3，留出提示词其余部分的空间
MAX_INLINE_VIDEO_BYTES = 40 * 1024 * 1024
# 与 ASR 一致：不为观察拉取超大视频
MAX_VIDEO_DOWNLOAD_BYTES = 300 * 1024 * 1024
MAX_KEYFRAMES = 6
PROBE_TIMEOUT_SECONDS = 30.0
EXTRACT_TIMEOUT_SECONDS = 180.0
# 帧宽度上限（Kimi 建议 ≤1920x1080；压低到 1280 控制视觉 token 消耗）
_FRAME_FILTER_SCALE = "scale='min(1280,iw)':-2"

_VIDEO_MIME_BY_EXT = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
}


def video_mime(filename_hint: str) -> str:
    ext = os.path.splitext(filename_hint or "")[1].lower()
    return _VIDEO_MIME_BY_EXT.get(ext, "video/mp4")


def video_data_uri(video_bytes: bytes, filename_hint: str) -> str:
    encoded = base64.b64encode(video_bytes).decode("utf-8")
    return f"data:{video_mime(filename_hint)};base64,{encoded}"


async def fetch_video_bytes(reference: str) -> tuple[bytes, str] | None:
    """下载视频检材字节；支持 signed URL 与 Supabase storage path。"""
    if not reference or reference.startswith("mock://"):
        return None
    try:
        data, name = await download_evidence_bytes(reference, timeout=120.0)
    except Exception as exc:
        logger.warning("[video] 视频检材下载失败 reference=%s: %s", reference[:80], exc)
        return None
    if len(data) > MAX_VIDEO_DOWNLOAD_BYTES:
        logger.warning(
            "[video] 视频 %.1fMB 超过观察下载上限 %dMB，跳过视频观察",
            len(data) / 1024 / 1024, MAX_VIDEO_DOWNLOAD_BYTES // 1024 // 1024,
        )
        return None
    return data, name


async def _probe_duration_seconds(probe_bin: str, path: str) -> float | None:
    try:
        returncode, stdout, _stderr = await _run_process(
            [
                probe_bin, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                path,
            ],
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("[video] ffprobe 时长探测失败: %s", exc)
        return None
    if returncode != 0:
        return None
    try:
        duration = float(stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None
    return duration if duration > 0 else None


async def extract_keyframe_images(
    video_bytes: bytes,
    filename_hint: str = "",
    *,
    max_frames: int = MAX_KEYFRAMES,
) -> list[bytes]:
    """均匀抽取关键帧并返回 JPEG 字节列表；失败返回空列表。"""
    probe_bin = _resolve_binary(settings.FFPROBE_BINARY, "ffprobe")
    ffmpeg_bin = _resolve_binary(settings.FFMPEG_BINARY, "ffmpeg")
    if not probe_bin or not ffmpeg_bin:
        logger.warning("[video] ffmpeg/ffprobe 不可用，无法抽取关键帧")
        return []

    tmp_dir: str | None = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="truthseeker_frames_")
        src_ext = os.path.splitext(filename_hint)[1].lower() or ".mp4"
        src_path = os.path.join(tmp_dir, f"source{src_ext}")
        with open(src_path, "wb") as fh:
            fh.write(video_bytes)

        duration = await _probe_duration_seconds(probe_bin, src_path)
        # 未知时长时按 0.5fps 抽取，仍用 -frames:v 控制帧数上限
        fps = min(max_frames / duration, 2.0) if duration else 0.5

        returncode, _stdout, stderr = await _run_process(
            [
                ffmpeg_bin, "-v", "error", "-y",
                "-i", src_path,
                "-vf", f"fps={fps:.4f},{_FRAME_FILTER_SCALE}",
                "-frames:v", str(max_frames),
                "-q:v", "4",
                os.path.join(tmp_dir, "frame_%02d.jpg"),
            ],
            timeout=EXTRACT_TIMEOUT_SECONDS,
        )
        if returncode != 0:
            logger.warning("[video] ffmpeg 关键帧抽取失败: %s", stderr.strip()[:200])
            return []

        frames: list[bytes] = []
        for name in sorted(os.listdir(tmp_dir)):
            if not name.startswith("frame_") or not name.endswith(".jpg"):
                continue
            with open(os.path.join(tmp_dir, name), "rb") as fh:
                payload = fh.read()
            if payload:
                frames.append(payload)
        return frames
    except asyncio.TimeoutError:
        logger.warning("[video] 关键帧抽取超时")
        return []
    except Exception as exc:
        logger.warning("[video] 关键帧抽取异常: %s: %s", type(exc).__name__, exc)
        return []
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def extract_keyframes(
    video_bytes: bytes,
    filename_hint: str = "",
    *,
    max_frames: int = MAX_KEYFRAMES,
) -> list[str]:
    """均匀抽取关键帧并返回 JPEG base64 data URI 列表（LLM 观察用）。"""
    frames = await extract_keyframe_images(video_bytes, filename_hint, max_frames=max_frames)
    return [f"data:image/jpeg;base64,{base64.b64encode(frame).decode('utf-8')}" for frame in frames]


async def extract_audio_track_bytes(
    video_bytes: bytes,
    filename_hint: str = "",
) -> bytes | None:
    """抽取视频音轨为 mp3 字节；无音轨、ffmpeg 不可用或失败返回 None。"""
    from app.agents.tools.audio_transcription import (
        _extract_audio_track,
        _video_has_audio_track,
    )

    probe_bin = _resolve_binary(settings.FFPROBE_BINARY, "ffprobe")
    ffmpeg_bin = _resolve_binary(settings.FFMPEG_BINARY, "ffmpeg")
    if not probe_bin or not ffmpeg_bin:
        logger.warning("[video] ffmpeg/ffprobe 不可用，无法抽取音轨")
        return None

    tmp_dir: str | None = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="truthseeker_audio_")
        src_ext = os.path.splitext(filename_hint)[1].lower() or ".mp4"
        src_path = os.path.join(tmp_dir, f"source{src_ext}")
        with open(src_path, "wb") as fh:
            fh.write(video_bytes)

        if not await _video_has_audio_track(probe_bin, src_path):
            return None

        dst_path = os.path.join(tmp_dir, "audio_track.mp3")
        await _extract_audio_track(ffmpeg_bin, src_path, dst_path)
        with open(dst_path, "rb") as fh:
            return fh.read()
    except Exception as exc:
        logger.warning("[video] 音轨抽取异常: %s: %s", type(exc).__name__, exc)
        return None
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
