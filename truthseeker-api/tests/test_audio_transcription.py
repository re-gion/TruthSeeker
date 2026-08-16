"""音频 ASR 语义转写工具回归：Groq Whisper 转写、视频音轨探测与结构化降级。

覆盖取证阶段新增 audio_transcription 工具的关键路径：
- 未配置 GROQ_API_KEY / 禁用时结构化降级，不虚构转写；
- 音频直传成功解析 text/language；
- 视频无音轨时跳过上传并返回正常结论（不算降级）；
- 视频有音轨时走 ffmpeg 抽取后上传；
- Groq 401/传输错误按降级处理；
- OSINT 上游已核验结论块纳入 ASR 转写摘要。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from app.agents.nodes import osint as osint_node_module
from app.agents.tools import audio_transcription as asr

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FakeAsyncClient:
    """按调用次数弹出结果的 httpx.AsyncClient 替身。"""

    def __init__(self, outcomes: list):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *args, **kwargs):
        self.calls.append({"url": url, "data": kwargs.get("data"), "files": kwargs.get("files")})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, httpx.Response):
            outcome.request = httpx.Request("POST", str(url))
        return outcome


def _runtime(**overrides) -> dict:
    base = {
        "enabled": True,
        "api_key": "gsk_test_key",
        "base_url": "https://api.groq.test/openai/v1",
        "model": "whisper-large-v3-turbo",
        "max_file_mb": 50.0,
        "timeout_seconds": 5.0,
    }
    base.update(overrides)
    return base


def _patch_runtime(monkeypatch, **overrides):
    runtime = _runtime(**overrides)
    monkeypatch.setattr(asr, "resolve_asr_runtime", lambda: runtime)
    return runtime


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    monkeypatch.setattr(asr, "ASR_RETRY_DELAYS", (0.01, 0.01))


async def test_missing_key_degrades_without_fabricated_text(monkeypatch):
    _patch_runtime(monkeypatch, api_key="")

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["status"] == "no_key"
    assert result["degraded"] is True
    assert result["text"] == ""
    assert result["fallback_reason"] == "missing_groq_api_key"


async def test_disabled_degrades(monkeypatch):
    _patch_runtime(monkeypatch, enabled=False)

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["degraded"] is True
    assert result["fallback_reason"] == "asr_disabled"


async def test_audio_success_parses_transcript(monkeypatch):
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"fake-audio-bytes", "案例7-音频-客服.mp3")),
    )
    client = _FakeAsyncClient([
        httpx.Response(200, json={"text": "农业银行账户安全提醒，请勿透露验证码。", "language": "zh", "duration": 3.2}),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence(
        "https://example.com/case7.mp3", "案例7-音频-客服.mp3", "audio"
    )

    assert result["status"] == "success"
    assert result["has_audio_track"] is True
    assert result["language"] == "zh"
    assert "农业银行" in result["text"]
    assert result["char_count"] == len(result["text"])
    assert result["preview"]
    # 上传文件名保留原检材名与受支持扩展名
    upload_files = client.calls[0]["files"]
    assert upload_files["file"][0] == "案例7-音频-客服.mp3"
    assert client.calls[0]["data"]["model"] == "whisper-large-v3-turbo"


async def test_video_without_audio_track_skips_upload(monkeypatch):
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"video-no-audio", "case.mp4")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        exe = str(cmd[0]).lower()
        if "ffprobe" in exe:
            return 0, "", ""  # 无音频流
        raise AssertionError("无音轨时不应调用 ffmpeg 抽取")

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/case.mp4", "case.mp4", "video")

    assert result["status"] == "success"
    assert result["has_audio_track"] is False
    assert result.get("degraded") is not True
    assert result["text"] == ""
    assert client.calls == []  # 未向 Groq 上传任何内容


async def test_video_with_audio_track_extracts_then_uploads(monkeypatch):
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"video-with-audio", "case.mp4")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        exe = str(cmd[0]).lower()
        if "ffprobe" in exe:
            return 0, "audio\n", ""
        # ffmpeg 抽取：最后一个参数是目标文件，模拟产出 mp3
        with open(cmd[-1], "wb") as fh:
            fh.write(b"extracted-mp3-bytes")
        return 0, "", ""

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([
        httpx.Response(200, json={"text": "提取的音轨内容", "language": "zh"}),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/case.mp4", "case.mp4", "video")

    assert result["status"] == "success"
    assert result["has_audio_track"] is True
    assert result["text"] == "提取的音轨内容"
    upload_name = client.calls[0]["files"]["file"][0]
    assert upload_name.endswith("_audiotrack.mp3")
    assert client.calls[0]["files"]["file"][1] == b"extracted-mp3-bytes"


async def test_groq_401_degrades_with_invalid_key_reason(monkeypatch):
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"fake-audio", "a.mp3")),
    )
    response = httpx.Response(401, json={"error": "Invalid API Key"})
    client = _FakeAsyncClient([response])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["status"] == "error"
    assert result["degraded"] is True
    assert result["fallback_reason"] == "invalid_groq_api_key"
    assert len(client.calls) == 1  # 401 不重试


async def test_transport_error_retried_then_degrades(monkeypatch):
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"fake-audio", "a.mp3")),
    )
    client = _FakeAsyncClient([httpx.ConnectError("tls reset")] * 3)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["degraded"] is True
    assert result["status"] == "error"
    assert "ConnectError" in result["fallback_reason"]
    assert len(client.calls) == 3  # 首次 + 2 次重试


async def test_file_too_large_degrades_before_upload(monkeypatch):
    _patch_runtime(monkeypatch, max_file_mb=0.000001)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"larger-than-limit", "big.mp3")),
    )
    client = _FakeAsyncClient([])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/big.mp3", "big.mp3", "audio")

    assert result["degraded"] is True
    assert result["fallback_reason"].startswith("file_too_large_for_groq")
    assert client.calls == []


def test_resolve_asr_runtime_reads_env_hot(monkeypatch):
    from app.config import resolve_asr_runtime, settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "AUDIO_ASR_ENABLED", True)
    monkeypatch.setattr(
        "app.config.dotenv_values",
        lambda path: {"GROQ_API_KEY": " gsk_hot_loaded ", "AUDIO_ASR_ENABLED": "true"},
    )

    runtime = resolve_asr_runtime()

    assert runtime["enabled"] is True
    assert runtime["api_key"] == "gsk_hot_loaded"
    assert runtime["model"] == "whisper-large-v3-turbo"

    monkeypatch.setattr(
        "app.config.dotenv_values",
        lambda path: {"AUDIO_ASR_ENABLED": "false"},
    )
    assert resolve_asr_runtime()["enabled"] is False


def test_forensics_summary_formats_asr_results():
    from app.agents.nodes.forensics import _summarize_tool_result

    success = _summarize_tool_result("audio_transcription", {
        "char_count": 42, "language": "zh", "preview": "农业银行账户安全提醒",
    })
    assert "ASR 转写 42 字" in success
    assert "农业银行" in success

    no_track = _summarize_tool_result("audio_transcription", {"has_audio_track": False})
    assert "未检测到音轨" in no_track

    degraded = _summarize_tool_result("audio_transcription", {
        "degraded": True, "analysis_available": False, "fallback_reason": "missing_groq_api_key",
    })
    assert "missing_groq_api_key" in degraded


def test_osint_upstream_conclusions_include_asr_summaries():
    state = {
        "forensics_result": {
            "aigc_probability": 0.98,
            "is_aigc": True,
            "confidence": 0.9,
            "tool_results": [
                {
                    "tool": "reality_defender",
                    "status": "success",
                    "summary": "aigc_probability=0.98, confidence=0.98",
                },
                {
                    "tool": "audio_transcription",
                    "status": "success",
                    "summary": "ASR 转写 42 字，语言=zh：农业银行账户安全提醒",
                },
                {
                    "tool": "audio_transcription",
                    "status": "degraded",  # 降级结果不进入上游引用
                    "summary": "ASR 音频转写未取得结果，降级原因=timeout",
                },
            ],
        }
    }

    conclusions = osint_node_module._upstream_verified_conclusions(state)

    assert conclusions is not None
    assert conclusions["audio_transcript_summaries"] == ["ASR 转写 42 字，语言=zh：农业银行账户安全提醒"]

    markdown = osint_node_module._upstream_citation_markdown("task-123", conclusions)
    assert "音频语义转写（ASR）" in markdown
    assert "农业银行" in markdown


def _async_value(value):
    async def _inner():
        return value
    return _inner()


async def test_groq_403_degrades_with_forbidden_reason(monkeypatch):
    """Groq 应用层 403（key 被拒/工作区模型权限限制）应给出可自解释的降级原因。"""
    _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"fake-audio", "a.mp3")),
    )
    response = httpx.Response(403, json={"error": {"message": "Forbidden"}})
    client = _FakeAsyncClient([response])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["status"] == "error"
    assert result["degraded"] is True
    assert result["fallback_reason"] == "groq_forbidden_api_key_rejected_or_model_permission_denied"
    assert len(client.calls) == 1  # 403 不重试


def test_resolve_binary_rejects_dirty_configured_value(monkeypatch):
    """.env 行内注释会把脏文本读进 FFMPEG_BINARY；无效配置必须回退 PATH。"""
    monkeypatch.setattr(asr.shutil, "which", lambda name: f"/fake/{name}")
    resolved = asr._resolve_binary("   # 留空则按 PATH 查找 ffmpeg", "ffmpeg")
    assert resolved == "/fake/ffmpeg"

    monkeypatch.setattr(asr.os.path, "isfile", lambda path: True)
    assert asr._resolve_binary("C:/ffmpeg/bin/ffmpeg.exe", "ffmpeg") == "C:/ffmpeg/bin/ffmpeg.exe"


async def test_run_process_returns_stdout_and_returncode():
    """_run_process 基本功能：能跑外部命令并回传 returncode/stdout。"""
    returncode, stdout, stderr = await asr._run_process(
        [sys.executable, "-c", "print('hello-run-process')"], timeout=20
    )
    assert returncode == 0
    assert "hello-run-process" in stdout
    assert isinstance(stderr, str)


@pytest.mark.skipif(sys.platform != "win32", reason="SelectorEventLoop 子进程缺陷是 Windows 专属")
def test_run_process_works_under_windows_selector_event_loop():
    """回归：uvicorn --reload/多 worker 在 Windows 会把事件循环固定为
    SelectorEventLoop（uvicorn.loops.asyncio.asyncio_loop_factory），旧的
    asyncio.create_subprocess_exec 实现会抛 NotImplementedError，导致 ASR
    音轨探测与视频关键帧抽取同时降级。改用线程池同步 subprocess 后，必须
    在 SelectorEventLoop 下同样可用。
    """
    import asyncio

    # Windows 上 asyncio.SelectorEventLoop 即 uvicorn 实际使用的无 subprocess
    # transport 实现的事件循环（等价于 WindowsSelectorEventLoopPolicy 产物）
    loop = asyncio.SelectorEventLoop()
    try:
        returncode, stdout, _stderr = loop.run_until_complete(
            asr._run_process([sys.executable, "-c", "print('selector-ok')"], timeout=20)
        )
    finally:
        loop.close()
    assert returncode == 0
    assert "selector-ok" in stdout


async def test_run_process_timeout_raises_asyncio_timeout_error():
    """超时语义保持：超时抛 asyncio.TimeoutError（与原实现一致）。"""
    import asyncio

    with pytest.raises(asyncio.TimeoutError):
        await asr._run_process([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3)
