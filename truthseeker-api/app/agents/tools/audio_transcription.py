"""音频语义转写（ASR）工具 — Groq OpenAI 兼容 Whisper 接口。

取证阶段用它把音频检材转写成文本，支撑"音频语义内容与文本主题一致性"
的跨模态校验（此前无 ASR 时该缺口只能按残留风险归档）。

流程：
1. 音频检材：下载后直接上传 Groq /audio/transcriptions；
2. 视频检材：先 ffprobe 判断是否存在音轨——无音轨直接记录结论并跳过上传
   （正常结果，不算降级）；有音轨则 ffmpeg 抽取为 mp3 再上传。

外部失败（无 Key、网络异常、限流、格式不支持等）一律走结构化降级，
与 Reality Defender/Sightengine 的降级契约一致：不伪造转写内容。
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

import httpx

from app.config import resolve_asr_runtime, settings
from app.services.evidence_access import download_evidence_bytes

logger = logging.getLogger(__name__)

# 传输层瞬时错误重试间隔（参考 RD 的重试策略）
ASR_RETRY_DELAYS = (0.8, 1.6)
# 转写文本进入上下文/报告的最大长度，超长截断并标注
MAX_TRANSCRIPT_CHARS = 8000
# 视频检材下载上限（避免为转写拉取超大视频）
VIDEO_DOWNLOAD_MAX_BYTES = 300 * 1024 * 1024
FFPROBE_TIMEOUT_SECONDS = 30.0
FFMPEG_EXTRACT_TIMEOUT_SECONDS = 120.0
# ffmpeg 未加入 PATH 时的本机常见安装目录（见 lessons.md）
_FFMPEG_FALLBACK_DIR = r"C:\Users\user\ffmpeg\bin"

# Groq Whisper 支持的上传格式（含视频容器，whisper 会解音轨）
_SUPPORTED_UPLOAD_EXTS = {
    ".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _degraded_result(reason: str, *, api_key_configured: bool, status: str = "unavailable") -> dict:
    """结构化降级：只说明未取得转写，不输出任何虚构文本。"""
    return {
        "status": status,
        "degraded": True,
        "analysis_available": False,
        "provider": "groq",
        "model": None,
        "has_audio_track": None,
        "text": "",
        "char_count": 0,
        "fallback_reason": reason,
        "api_key_configured": api_key_configured,
        "timestamp": _now(),
    }


def _resolve_binary(configured: str, name: str) -> str | None:
    """按 配置值 → PATH → 常见安装目录 顺序定位 ffmpeg/ffprobe 可执行文件。

    配置值必须指向真实存在的文件才生效：dotenv 不支持行内注释，
    .env 里 `FFMPEG_BINARY=  # 说明` 会把注释文本读成路径，直接拿去
    启动子进程必然失败，这里过滤掉这类脏配置并回退到 PATH 查找。
    """
    configured = (configured or "").strip()
    if configured:
        if os.path.isfile(configured):
            return configured
        logger.warning("[ASR] %s_BINARY 配置值不是有效文件路径，回退 PATH 查找: %r", name.upper(), configured[:80])
    found = shutil.which(name)
    if found:
        return found
    candidate = os.path.join(_FFMPEG_FALLBACK_DIR, f"{name}.exe")
    if os.path.isfile(candidate):
        return candidate
    return None


async def _run_process(cmd: list[str], timeout: float) -> tuple[int, str, str]:
    """在线程池里用同步 subprocess 运行外部命令。

    不用 asyncio.create_subprocess_exec：它依赖事件循环的子进程 transport，
    Windows 的 SelectorEventLoop 不实现该能力（直接抛 NotImplementedError）。
    而 uvicorn 在 --reload / 多 worker 时会把事件循环固定为 SelectorEventLoop
    （uvicorn.loops.asyncio.asyncio_loop_factory），导致 ASR 音轨探测与视频
    关键帧抽取全部失败。同步 subprocess.run 不依赖事件循环类型，放到线程池
    执行即可避免阻塞；超时/异常语义与原实现保持一致（见 lessons.md）。
    """

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    try:
        completed = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired as exc:
        # subprocess.run 超时会自行终止子进程，这里转成原实现的超时异常类型
        raise asyncio.TimeoutError(str(exc)) from exc
    return (
        completed.returncode or 0,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
    )


async def _video_has_audio_track(probe_bin: str, path: str) -> bool:
    """ffprobe 检测媒体文件是否包含音频流。"""
    returncode, stdout, stderr = await _run_process(
        [
            probe_bin, "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            path,
        ],
        timeout=FFPROBE_TIMEOUT_SECONDS,
    )
    if returncode != 0:
        raise RuntimeError(f"ffprobe 检测音轨失败: {stderr.strip()[:200]}")
    return bool(stdout.strip())


async def _extract_audio_track(ffmpeg_bin: str, src: str, dst: str) -> None:
    """ffmpeg 抽取单声道 16kHz mp3 音轨，显著减小上传体积。"""
    returncode, _stdout, stderr = await _run_process(
        [
            ffmpeg_bin, "-v", "error", "-y",
            "-i", src,
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "libmp3lame", "-q:a", "4",
            dst,
        ],
        timeout=FFMPEG_EXTRACT_TIMEOUT_SECONDS,
    )
    if returncode != 0:
        raise RuntimeError(f"ffmpeg 抽取音轨失败: {stderr.strip()[:200]}")


def _upload_name(filename_hint: str, modality: str, actual_ext: str = "") -> str:
    """构造带受支持扩展名的上传文件名。"""
    base = os.path.splitext(os.path.basename(filename_hint or ""))[0] or "evidence"
    ext = (actual_ext or os.path.splitext(filename_hint or "")[1]).lower()
    if ext not in _SUPPORTED_UPLOAD_EXTS:
        ext = ".mp4" if modality == "video" else ".mp3"
    return f"{base}{ext}"


async def _post_transcription(
    *, base_url: str, api_key: str, model: str,
    audio_bytes: bytes, filename: str, timeout: float,
) -> dict:
    """调用 Groq /audio/transcriptions，传输层瞬时错误/429/5xx 有限重试。"""
    url = f"{base_url}/audio/transcriptions"
    last_exc: Exception | None = None
    for attempt in range(len(ASR_RETRY_DELAYS) + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    data={"model": model, "response_format": "json"},
                    files={"file": (filename, audio_bytes)},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.TransportError as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise PermissionError("invalid_groq_api_key") from exc
            if status == 403:
                # Groq 应用层 403：key 被拒绝或工作区模型权限限制（/models 也会 403）。
                # 与区域封锁不同，响应体是 {"error":{"message":"Forbidden"}}。
                raise PermissionError(
                    "groq_forbidden_api_key_rejected_or_model_permission_denied"
                ) from exc
            if status in {413, 400}:
                raise ValueError(f"groq_rejected_upload_http_{status}") from exc
            if status < 500 and status != 429:
                raise
            last_exc = exc
        if attempt < len(ASR_RETRY_DELAYS):
            logger.warning(
                "[ASR] Groq 转写请求异常（%s），%.1fs 后重试（%d/%d）",
                type(last_exc).__name__, ASR_RETRY_DELAYS[attempt],
                attempt + 1, len(ASR_RETRY_DELAYS),
            )
            await asyncio.sleep(ASR_RETRY_DELAYS[attempt])
    assert last_exc is not None
    raise last_exc


async def transcribe_audio_evidence(
    file_url: str,
    filename_hint: str = "",
    modality: str = "audio",
) -> dict:
    """对单个音频/视频检材做 ASR 转写。

    返回 success 时携带 text/language/char_count；视频无音轨返回
    has_audio_track=False 的正常结论；任何失败返回结构化降级结果。
    """
    runtime = resolve_asr_runtime()
    if not runtime["enabled"]:
        return _degraded_result("asr_disabled", api_key_configured=False, status="unavailable")
    api_key = runtime["api_key"]
    if not api_key:
        logger.warning("[ASR] GROQ_API_KEY 未配置，音频语义转写降级")
        return _degraded_result("missing_groq_api_key", api_key_configured=False, status="no_key")

    tmp_dir: str | None = None
    try:
        file_data, downloaded_name = await download_evidence_bytes(file_url, timeout=60.0)
        hint = filename_hint or downloaded_name or ""
        if modality == "video" and len(file_data) > VIDEO_DOWNLOAD_MAX_BYTES:
            return _degraded_result(
                f"video_too_large_for_asr({len(file_data) // (1024 * 1024)}MB)",
                api_key_configured=True,
            )

        upload_bytes = file_data
        upload_filename = _upload_name(hint, modality)

        if modality == "video":
            probe_bin = _resolve_binary(settings.FFPROBE_BINARY, "ffprobe")
            ffmpeg_bin = _resolve_binary(settings.FFMPEG_BINARY, "ffmpeg")
            if not probe_bin or not ffmpeg_bin:
                return _degraded_result("ffmpeg_not_installed", api_key_configured=True)

            tmp_dir = tempfile.mkdtemp(prefix="truthseeker_asr_")
            src_ext = os.path.splitext(hint)[1].lower() or ".mp4"
            src_path = os.path.join(tmp_dir, f"source{src_ext}")
            with open(src_path, "wb") as fh:
                fh.write(file_data)

            if not await _video_has_audio_track(probe_bin, src_path):
                logger.info("[ASR] 视频检材 %s 无音轨，跳过转写", hint or file_url)
                return {
                    "status": "success",
                    "provider": "groq",
                    "model": runtime["model"],
                    "modality": modality,
                    "has_audio_track": False,
                    "text": "",
                    "char_count": 0,
                    "language": None,
                    "note": "视频检材未检测到音轨，无需 ASR 转写",
                    "timestamp": _now(),
                }

            dst_path = os.path.join(tmp_dir, "audio_track.mp3")
            await _extract_audio_track(ffmpeg_bin, src_path, dst_path)
            with open(dst_path, "rb") as fh:
                upload_bytes = fh.read()
            upload_filename = f"{os.path.splitext(os.path.basename(hint or 'video'))[0] or 'video'}_audiotrack.mp3"

        max_bytes = runtime["max_file_mb"] * 1024 * 1024
        if len(upload_bytes) > max_bytes:
            return _degraded_result(
                f"file_too_large_for_groq({len(upload_bytes) / 1024 / 1024:.1f}MB>{runtime['max_file_mb']:.0f}MB)",
                api_key_configured=True,
            )

        data = await _post_transcription(
            base_url=runtime["base_url"],
            api_key=api_key,
            model=runtime["model"],
            audio_bytes=upload_bytes,
            filename=upload_filename,
            timeout=runtime["timeout_seconds"],
        )
        # ASR 外部返回可能混入 NUL，Postgres 无法存储（22P05），也无转写语义
        text = str(data.get("text") or "").replace("\x00", "").strip()
        truncated = len(text) > MAX_TRANSCRIPT_CHARS
        text = text[:MAX_TRANSCRIPT_CHARS]
        return {
            "status": "success",
            "provider": "groq",
            "model": runtime["model"],
            "modality": modality,
            "has_audio_track": True,
            "language": data.get("language"),
            "duration": data.get("duration"),
            "text": text,
            "truncated": truncated,
            "char_count": len(text),
            "preview": text[:200],
            "timestamp": _now(),
        }
    except PermissionError as exc:
        logger.error(
            "[ASR] Groq 拒绝请求（%s）：请在 Groq Console 检查 API Key 是否有效、"
            "以及工作区模型权限是否限制了 whisper 系列模型", exc,
        )
        return _degraded_result(str(exc), api_key_configured=True, status="error")
    except Exception as exc:
        # 带完整堆栈：此前 NotImplementedError 等异常只留下类型名，无法定位来源
        logger.warning(
            "[ASR] 音频转写失败 target=%s: %s: %s",
            filename_hint or file_url, type(exc).__name__, exc,
            exc_info=True,
        )
        return _degraded_result(
            f"{type(exc).__name__}: {exc}",
            api_key_configured=True,
            status="error",
        )
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
