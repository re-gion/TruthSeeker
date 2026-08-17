"""音频语义转写（ASR）工具 — 支持 Groq Whisper 与百度智能云短语音识别极速版。

取证阶段用它把音频检材转写成文本，支撑"音频语义内容与文本主题一致性"
的跨模态校验（此前无 ASR 时该缺口只能按残留风险归档）。

服务商通过 .env 的 AUDIO_ASR_PROVIDER 切换（配好对应 Key 即可，无需改代码）：
- groq（默认）：Groq OpenAI 兼容 /audio/transcriptions，支持常见音视频格式与长音频；
- baidu：百度智能云短语音识别极速版（dev_pid=80001 普通话输入法模型，国内接入）。
  百度单次识别上限 60 秒且只接受 pcm/wav/amr/m4a（16kHz 单声道），因此本地先用
  ffmpeg 归一化为 16kHz 单声道 wav 并按段切分，逐段上传后拼接全文；长音频最多
  转写前 BAIDU_MAX_SEGMENTS 段并在结果中注明。

流程：
1. 音频检材：下载后直接上传（groq）或 ffmpeg 归一化+分段后上传（baidu）；
2. 视频检材：先 ffprobe 判断是否存在音轨——无音轨直接记录结论并跳过上传
   （正常结果，不算降级）；有音轨再抽取/分段后上传。

外部失败（无 Key、网络异常、限流、格式不支持等）一律走结构化降级，
与 Reality Defender/Sightengine 的降级契约一致：不伪造转写内容。
"""
from __future__ import annotations

import asyncio
import base64
import glob
import logging
import os
import shutil
import subprocess
import tempfile
import time
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

# ---- 百度智能云短语音识别极速版 ----
# 单次识别时长硬上限 60 秒；分段长度留余量，避免边界值被服务端拒绝
BAIDU_SEGMENT_SECONDS = 55
# 长音频最多转写的分段数（约前 18 分钟），超出部分不转写并在结果 note 中注明
BAIDU_MAX_SEGMENTS = 20
# 无 ffmpeg 转码时允许原样直传的格式（百度仅接受 pcm/wav/amr/m4a）
_BAIDU_DIRECT_UPLOAD_EXTS = {".pcm", ".wav", ".amr", ".m4a"}
# 业务 err_no：服务端繁忙/限流/超时类，按传输层同款策略重试
_BAIDU_RETRYABLE_ERRNOS = {3303, 3304, 3307, 3313, 3315}
# 业务 err_no："无可识别语音"（数据为空/质量过差/长度过短），语义上等价于
# Groq 对静音返回空文本——按空转写成功返回，不降级
_BAIDU_EMPTY_AUDIO_ERRNOS = {2000, 3301, 3314}
# 业务 err_no → 可自解释的降级原因（未列出的错误码按 baidu_err_no_<code> 透出）
_BAIDU_ERROR_REASONS = {
    100: "baidu_invalid_parameter",
    110: "baidu_access_token_invalid",
    111: "baidu_access_token_expired",
    3300: "baidu_invalid_parameters",
    3302: "baidu_auth_failed_check_api_key_secret_key_or_quota",
    3305: "baidu_daily_quota_exceeded",
    3308: "baidu_audio_too_long_gt_60s",
    3309: "baidu_audio_cannot_be_converted_to_pcm",
    3310: "baidu_audio_too_large_or_len_exceeded",
    3311: "baidu_invalid_sample_rate",
    3312: "baidu_unsupported_audio_format",
    3316: "baidu_audio_pcm_conversion_failed",
}


class _BaiduTransientError(Exception):
    """百度服务端瞬时错误（后端繁忙/并发超限/解析超时等），可重试。"""


# 百度 access_token 进程内缓存：{"token_url|api_key": (token, monotonic 过期时刻)}。
# 百度 token 有效期 30 天，这里提前 1 小时刷新；重启进程后重新获取。
_baidu_token_cache: dict[str, tuple[str, float]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _degraded_result(reason: str, *, provider: str, api_key_configured: bool, status: str = "unavailable") -> dict:
    """结构化降级：只说明未取得转写，不输出任何虚构文本。"""
    return {
        "status": status,
        "degraded": True,
        "analysis_available": False,
        "provider": provider,
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


def _baidu_error_reason(err_no: object, err_msg: object) -> str:
    """百度业务 err_no → 可自解释的降级原因 slug。"""
    reason = _BAIDU_ERROR_REASONS.get(err_no)  # type: ignore[arg-type]
    if reason:
        return reason
    msg = str(err_msg or "").strip()
    return f"baidu_err_no_{err_no}" + (f"({msg[:60]})" if msg else "")


async def _get_baidu_access_token(
    *, token_url: str, api_key: str, secret_key: str, timeout: float,
) -> str:
    """获取百度开放平台 access_token（client_credentials 模式），有效期内进程级缓存。

    凭证错误（400/401/403，如 invalid_client）抛 PermissionError，外层走结构化降级；
    传输层瞬时错误与 5xx/429 按与转写请求相同的策略有限重试。
    """
    cache_key = f"{token_url}|{api_key}"
    now = time.monotonic()
    cached = _baidu_token_cache.get(cache_key)
    if cached and cached[1] > now:
        return cached[0]

    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }
    last_exc: Exception | None = None
    for attempt in range(len(ASR_RETRY_DELAYS) + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
                resp = await client.post(token_url, params=params, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()
            token = str(data.get("access_token") or "").strip()
            if not token:
                err = data.get("error") or data.get("error_description") or "no_access_token_in_response"
                raise PermissionError(f"baidu_token_fetch_failed:{err}") from None
            try:
                expires_in = float(data.get("expires_in") or 2592000)
            except (TypeError, ValueError):
                expires_in = 2592000.0
            # 提前 1 小时刷新；expires_in 异常时至少保证 10 分钟缓存
            _baidu_token_cache[cache_key] = (token, now + max(min(expires_in, 2592000.0) - 3600.0, 600.0))
            return token
        except httpx.TransportError as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {400, 401, 403}:
                # 百度凭证错误（invalid_client 等）：API Key / Secret Key 不正确或应用未开通
                try:
                    body = exc.response.json()
                    detail = str(body.get("error_description") or body.get("error") or "")
                except Exception:
                    detail = ""
                raise PermissionError(
                    f"baidu_token_rejected_http_{status}" + (f":{detail[:80]}" if detail else "")
                ) from exc
            if status < 500 and status != 429:
                raise
            last_exc = exc
        if attempt < len(ASR_RETRY_DELAYS):
            logger.warning(
                "[ASR] 百度 access_token 获取异常（%s），%.1fs 后重试（%d/%d）",
                type(last_exc).__name__, ASR_RETRY_DELAYS[attempt],
                attempt + 1, len(ASR_RETRY_DELAYS),
            )
            await asyncio.sleep(ASR_RETRY_DELAYS[attempt])
    assert last_exc is not None
    raise last_exc


async def _post_baidu_transcription(
    *, base_url: str, token: str, dev_pid: int, cuid: str,
    audio_bytes: bytes, audio_format: str, timeout: float,
) -> str:
    """调用百度短语音识别极速版（JSON 方式上传），返回转写文本（可能为空串）。

    - err_no=0：拼接 result 数组返回；
    - 空语音类 err_no（2000/3301/3314）：返回空串，不视为错误；
    - 服务端繁忙/限流/超时类 err_no 与传输层瞬时错误同款策略重试；
    - 其余业务 err_no：抛 ValueError（携带可自解释原因），由外层结构化降级。
    """
    payload = {
        "format": audio_format,
        "rate": 16000,
        "dev_pid": dev_pid,
        "channel": 1,
        "token": token,
        "cuid": cuid,
        "len": len(audio_bytes),
        "speech": base64.b64encode(audio_bytes).decode("ascii"),
    }
    last_exc: Exception | None = None
    for attempt in range(len(ASR_RETRY_DELAYS) + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
                resp = await client.post(base_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            err_no = data.get("err_no")
            if err_no == 0:
                return "".join(str(item) for item in (data.get("result") or []))
            if err_no in _BAIDU_EMPTY_AUDIO_ERRNOS:
                return ""
            if err_no in _BAIDU_RETRYABLE_ERRNOS:
                raise _BaiduTransientError(f"baidu_transient_err_no_{err_no}")
            raise ValueError(_baidu_error_reason(err_no, data.get("err_msg")))
        except _BaiduTransientError as exc:
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403}:
                raise PermissionError("baidu_invalid_token_or_no_permission") from exc
            if status == 400:
                raise ValueError("baidu_rejected_request_http_400") from exc
            if status < 500 and status != 429:
                raise
            last_exc = exc
        if attempt < len(ASR_RETRY_DELAYS):
            logger.warning(
                "[ASR] 百度转写请求异常（%s），%.1fs 后重试（%d/%d）",
                type(last_exc).__name__, ASR_RETRY_DELAYS[attempt],
                attempt + 1, len(ASR_RETRY_DELAYS),
            )
            await asyncio.sleep(ASR_RETRY_DELAYS[attempt])
    assert last_exc is not None
    raise last_exc


async def _split_audio_segments(ffmpeg_bin: str, src: str, dst_dir: str) -> list[str]:
    """ffmpeg 归一化为 16kHz 单声道 16bit wav 并按 BAIDU_SEGMENT_SECONDS 切分。

    百度极速版单次识别限 60 秒且只接受 pcm/wav/amr/m4a，本地归一化+切分可让
    任意格式/任意时长的检材以多个 ≤60s 的分段提交。返回按序号排序的分段文件列表。
    """
    pattern = os.path.join(dst_dir, "segment_%04d.wav")
    returncode, _stdout, stderr = await _run_process(
        [
            ffmpeg_bin, "-v", "error", "-y",
            "-i", src,
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-f", "segment", "-segment_time", str(BAIDU_SEGMENT_SECONDS),
            "-reset_timestamps", "1",
            pattern,
        ],
        timeout=FFMPEG_EXTRACT_TIMEOUT_SECONDS,
    )
    if returncode != 0:
        raise RuntimeError(f"ffmpeg 音频分段失败: {stderr.strip()[:200]}")
    return sorted(glob.glob(os.path.join(dst_dir, "segment_*.wav")))


def _baidu_model_label(dev_pid: int) -> str:
    return f"baidu_short_speech_extreme_dev_pid{dev_pid}"


async def _transcribe_with_baidu(
    runtime: dict, *, file_data: bytes, hint: str, modality: str,
) -> dict:
    """百度极速版转写主流程：获取 token → ffmpeg 归一化+分段 → 逐段识别拼接全文。

    ffmpeg 可用时统一走"归一化 16kHz 单声道 wav + 分段"，顺带解决百度不支持
    mp3/flac 等格式的问题；ffmpeg 不可用时仅百度原生支持的格式可原样直传
    （此时无法绕开 60 秒单次上限，超长由服务端 err_no 拒绝后降级）。
    """
    provider = "baidu"
    dev_pid = int(runtime["baidu_dev_pid"])
    timeout = runtime["timeout_seconds"]
    model = _baidu_model_label(dev_pid)

    async def _recognize(audio_bytes: bytes, audio_format: str) -> str:
        # token 推迟到真正要识别时才取（并走进程级缓存）：无音轨视频等
        # 无需上传的场景不会触发百度请求，token 获取失败也不会误伤正常结论
        token = await _get_baidu_access_token(
            token_url=runtime["baidu_token_url"],
            api_key=runtime["baidu_api_key"],
            secret_key=runtime["baidu_secret_key"],
            timeout=timeout,
        )
        return await _post_baidu_transcription(
            base_url=runtime["baidu_base_url"],
            token=token,
            dev_pid=dev_pid,
            cuid=runtime["baidu_cuid"],
            audio_bytes=audio_bytes,
            audio_format=audio_format,
            timeout=timeout,
        )

    ffmpeg_bin = _resolve_binary(settings.FFMPEG_BINARY, "ffmpeg")
    ext = os.path.splitext(hint)[1].lower()

    if not ffmpeg_bin:
        # 无 ffmpeg：视频无法取音轨，音频仅百度支持的格式可直传
        if modality == "video":
            return _degraded_result("ffmpeg_not_installed", provider=provider, api_key_configured=True)
        if ext not in _BAIDU_DIRECT_UPLOAD_EXTS:
            return _degraded_result(
                f"ffmpeg_not_installed_and_format_unsupported_by_baidu({ext or 'unknown'})",
                provider=provider, api_key_configured=True,
            )
        max_bytes = runtime["max_file_mb"] * 1024 * 1024
        if len(file_data) > max_bytes:
            return _degraded_result(
                f"file_too_large_for_baidu({len(file_data) / 1024 / 1024:.1f}MB>{runtime['max_file_mb']:.0f}MB)",
                provider=provider, api_key_configured=True,
            )
        text = await _recognize(file_data, ext.lstrip("."))
        segments_used = segments_total = 1
    else:
        probe_bin = _resolve_binary(settings.FFPROBE_BINARY, "ffprobe")
        if modality == "video" and not probe_bin:
            return _degraded_result("ffprobe_not_installed", provider=provider, api_key_configured=True)

        tmp_dir = tempfile.mkdtemp(prefix="truthseeker_asr_baidu_")
        try:
            src_ext = ext or (".mp4" if modality == "video" else ".wav")
            src_path = os.path.join(tmp_dir, f"source{src_ext}")
            with open(src_path, "wb") as fh:
                fh.write(file_data)

            if modality == "video":
                if not await _video_has_audio_track(probe_bin, src_path):
                    logger.info("[ASR] 视频检材 %s 无音轨，跳过转写", hint)
                    return {
                        "status": "success",
                        "provider": provider,
                        "model": model,
                        "modality": modality,
                        "has_audio_track": False,
                        "text": "",
                        "char_count": 0,
                        "language": None,
                        "note": "视频检材未检测到音轨，无需 ASR 转写",
                        "timestamp": _now(),
                    }

            # -vn 对纯音频输入是无害空操作，因此音频/视频共用同一条归一化+分段命令
            segments = await _split_audio_segments(ffmpeg_bin, src_path, tmp_dir)
            if not segments:
                return _degraded_result("ffmpeg_produced_no_segments", provider=provider, api_key_configured=True)

            segments_total = len(segments)
            segments_used = min(segments_total, BAIDU_MAX_SEGMENTS)
            texts: list[str] = []
            for path in segments[:segments_used]:
                with open(path, "rb") as fh:
                    chunk = fh.read()
                texts.append(await _recognize(chunk, "wav"))
            text = "".join(texts)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ASR 外部返回可能混入 NUL，Postgres 无法存储（22P05），也无转写语义
    text = text.replace("\x00", "").strip()
    truncated = len(text) > MAX_TRANSCRIPT_CHARS
    text = text[:MAX_TRANSCRIPT_CHARS]
    result = {
        "status": "success",
        "provider": provider,
        "model": model,
        "modality": modality,
        "has_audio_track": True,
        # dev_pid=80001 为普通话输入法模型，语种固定
        "language": "zh",
        "duration": None,
        "segments_used": segments_used,
        "segments_total": segments_total,
        "text": text,
        "truncated": truncated,
        "char_count": len(text),
        "preview": text[:200],
        "timestamp": _now(),
    }
    if segments_total > segments_used:
        result["note"] = (
            f"百度极速版单次识别限 60 秒，长音频已分段转写，"
            f"仅取前 {segments_used} 段（约 {segments_used * BAIDU_SEGMENT_SECONDS} 秒）"
        )
    return result


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
    provider = str(runtime.get("provider") or "groq")
    if not runtime["enabled"]:
        return _degraded_result("asr_disabled", provider=provider, api_key_configured=False, status="unavailable")
    if provider == "baidu":
        if not (runtime["baidu_api_key"] and runtime["baidu_secret_key"]):
            logger.warning("[ASR] BAIDU_ASR_API_KEY/BAIDU_ASR_SECRET_KEY 未配置，音频语义转写降级")
            return _degraded_result(
                "missing_baidu_asr_api_key_or_secret_key",
                provider="baidu", api_key_configured=False, status="no_key",
            )
    else:
        if not runtime["api_key"]:
            logger.warning("[ASR] GROQ_API_KEY 未配置，音频语义转写降级")
            return _degraded_result("missing_groq_api_key", provider="groq", api_key_configured=False, status="no_key")

    tmp_dir: str | None = None
    try:
        file_data, downloaded_name = await download_evidence_bytes(file_url, timeout=60.0)
        hint = filename_hint or downloaded_name or ""
        if modality == "video" and len(file_data) > VIDEO_DOWNLOAD_MAX_BYTES:
            return _degraded_result(
                f"video_too_large_for_asr({len(file_data) // (1024 * 1024)}MB)",
                provider=provider, api_key_configured=True,
            )

        if provider == "baidu":
            return await _transcribe_with_baidu(runtime, file_data=file_data, hint=hint, modality=modality)

        # ---- Groq Whisper 路径 ----
        api_key = runtime["api_key"]
        upload_bytes = file_data
        upload_filename = _upload_name(hint, modality)

        if modality == "video":
            probe_bin = _resolve_binary(settings.FFPROBE_BINARY, "ffprobe")
            ffmpeg_bin = _resolve_binary(settings.FFMPEG_BINARY, "ffmpeg")
            if not probe_bin or not ffmpeg_bin:
                return _degraded_result("ffmpeg_not_installed", provider=provider, api_key_configured=True)

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
                provider=provider, api_key_configured=True,
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
        if provider == "baidu":
            logger.error(
                "[ASR] 百度智能云拒绝请求（%s）：请在百度云控制台检查应用是否勾选开通"
                "短语音识别极速版、BAIDU_ASR_API_KEY/BAIDU_ASR_SECRET_KEY 是否正确", exc,
            )
        else:
            logger.error(
                "[ASR] Groq 拒绝请求（%s）：请在 Groq Console 检查 API Key 是否有效、"
                "以及工作区模型权限是否限制了 whisper 系列模型", exc,
            )
        return _degraded_result(str(exc), provider=provider, api_key_configured=True, status="error")
    except ValueError as exc:
        # 业务拒绝通道（百度 err_no 映射、Groq 400 等），消息本身已是可自解释的
        # 降级原因 slug，不再叠加异常类型前缀
        logger.warning("[ASR] 音频转写被服务商拒绝 target=%s: %s", filename_hint or file_url, exc)
        return _degraded_result(str(exc), provider=provider, api_key_configured=True, status="error")
    except Exception as exc:
        # 带完整堆栈：此前 NotImplementedError 等异常只留下类型名，无法定位来源
        logger.warning(
            "[ASR] 音频转写失败 target=%s: %s: %s",
            filename_hint or file_url, type(exc).__name__, exc,
            exc_info=True,
        )
        return _degraded_result(
            f"{type(exc).__name__}: {exc}",
            provider=provider, api_key_configured=True,
            status="error",
        )
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
