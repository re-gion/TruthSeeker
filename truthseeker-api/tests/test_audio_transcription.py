"""音频 ASR 语义转写工具回归：Groq Whisper / 百度极速版转写、视频音轨探测与结构化降级。

覆盖取证阶段 audio_transcription 工具的关键路径：
- AUDIO_ASR_PROVIDER 在 groq / baidu 之间切换，两套 Key 各自独立校验；
- 未配置 Key / 禁用时结构化降级，不虚构转写；
- Groq：音频直传成功解析 text/language；视频无音轨跳过上传；有音轨抽取后上传；
  401/403/传输错误按降级处理；
- 百度：token 获取与缓存、JSON base64 上传参数（dev_pid=80001/rate=16000/channel=1）、
  ffmpeg 归一化+分段逐段识别拼接、分段数上限、空语音 err_no 视为空转写、
  鉴权失败/瞬时错误重试与降级；
- OSINT 上游已核验结论块纳入 ASR 转写摘要。
"""
from __future__ import annotations

import base64
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
        self.calls.append({
            "url": url,
            "data": kwargs.get("data"),
            "files": kwargs.get("files"),
            "json": kwargs.get("json"),
            "params": kwargs.get("params"),
        })
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, httpx.Response):
            outcome.request = httpx.Request("POST", str(url))
        return outcome


def _runtime(**overrides) -> dict:
    base = {
        "enabled": True,
        "provider": "groq",
        "api_key": "gsk_test_key",
        "base_url": "https://api.groq.test/openai/v1",
        "model": "whisper-large-v3-turbo",
        "max_file_mb": 50.0,
        "timeout_seconds": 5.0,
    }
    base.update(overrides)
    return base


def _baidu_runtime(**overrides) -> dict:
    """百度极速版 runtime：与 resolve_asr_runtime 返回结构一致的最小字段集。"""
    base = _runtime(
        provider="baidu",
        api_key="",  # Groq Key 置空，验证 provider 分发不看错 Key
        baidu_api_key="baidu_test_api_key",
        baidu_secret_key="baidu_test_secret_key",
        baidu_dev_pid=80001,
        baidu_base_url="https://vop.baidu.test/pro_api",
        baidu_token_url="https://aip.baidubce.test/oauth/2.0/token",
        baidu_cuid="truthseeker-test",
    )
    base.update(overrides)
    return base


def _patch_runtime(monkeypatch, **overrides):
    runtime = _runtime(**overrides)
    monkeypatch.setattr(asr, "resolve_asr_runtime", lambda: runtime)
    return runtime


def _patch_baidu_runtime(monkeypatch, **overrides):
    runtime = _baidu_runtime(**overrides)
    monkeypatch.setattr(asr, "resolve_asr_runtime", lambda: runtime)
    return runtime


def _baidu_token_response(token: str = "test-access-token") -> httpx.Response:
    return httpx.Response(200, json={"access_token": token, "expires_in": 2592000})


def _baidu_asr_response(*results: str, err_no: int = 0, err_msg: str = "success.") -> httpx.Response:
    payload: dict = {"err_no": err_no, "err_msg": err_msg, "sn": "test-sn"}
    if err_no == 0:
        payload["result"] = list(results)
    return httpx.Response(200, json=payload)


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    monkeypatch.setattr(asr, "ASR_RETRY_DELAYS", (0.01, 0.01))
    # 百度 access_token 进程级缓存必须在用例间隔离，否则上一个用例缓存的
    # token 会让后续用例跳过 token HTTP 调用，断言到的请求序列就错了
    monkeypatch.setattr(asr, "_baidu_token_cache", {})


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


# ---- 百度智能云短语音识别极速版（AUDIO_ASR_PROVIDER=baidu）----


@pytest.mark.parametrize("missing", ["baidu_api_key", "baidu_secret_key"])
async def test_baidu_missing_either_key_degrades(monkeypatch, missing):
    """API Key / Secret Key 缺一即按未配置 Key 降级，不虚构转写。"""
    _patch_baidu_runtime(monkeypatch, **{missing: ""})

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["status"] == "no_key"
    assert result["provider"] == "baidu"
    assert result["degraded"] is True
    assert result["text"] == ""
    assert result["fallback_reason"] == "missing_baidu_asr_api_key_or_secret_key"


async def test_baidu_provider_does_not_require_groq_key(monkeypatch):
    """provider=baidu 时 Groq Key 为空不影响转写（两套 Key 相互独立）。"""
    runtime = _patch_baidu_runtime(monkeypatch)
    assert runtime["api_key"] == ""  # _baidu_runtime 已把 Groq Key 置空

    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"x", "a.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("不需要 Groq Key"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.wav", "a.wav", "audio")

    assert result["status"] == "success"
    assert result["provider"] == "baidu"


async def test_baidu_audio_success_request_shape(monkeypatch):
    """成功路径：ffmpeg 归一化+分段后上传；校验 token 请求与识别请求的完整参数形态。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"fake-audio", "案例7-音频-客服.mp3")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        exe = str(cmd[0]).lower()
        assert "ffmpeg" in exe, "音频直转不应调用 ffprobe"
        # 最后一个参数是输出 pattern，模拟产出单段 wav
        with open(cmd[-1].replace("%04d", "0000"), "wb") as fh:
            fh.write(b"segment-wav-bytes")
        return 0, "", ""

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("农业银行账户安全提醒，请勿透露验证码。"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence(
        "https://example.com/case7.mp3", "案例7-音频-客服.mp3", "audio"
    )

    assert result["status"] == "success"
    assert result["provider"] == "baidu"
    assert result["model"] == "baidu_short_speech_extreme_dev_pid80001"
    assert result["language"] == "zh"
    assert result["has_audio_track"] is True
    assert "农业银行" in result["text"]
    assert result["segments_used"] == 1 and result["segments_total"] == 1
    assert "note" not in result

    token_call, asr_call = client.calls
    assert token_call["url"] == "https://aip.baidubce.test/oauth/2.0/token"
    assert token_call["params"]["grant_type"] == "client_credentials"
    assert token_call["params"]["client_id"] == "baidu_test_api_key"
    assert token_call["params"]["client_secret"] == "baidu_test_secret_key"

    payload = asr_call["json"]
    assert asr_call["url"] == "https://vop.baidu.test/pro_api"
    assert payload["dev_pid"] == 80001
    assert payload["rate"] == 16000
    assert payload["channel"] == 1
    assert payload["format"] == "wav"
    assert payload["token"] == "test-access-token"
    assert payload["cuid"] == "truthseeker-test"
    assert payload["len"] == len(b"segment-wav-bytes")
    assert base64.b64decode(payload["speech"]) == b"segment-wav-bytes"


async def test_baidu_long_audio_concatenates_segments(monkeypatch):
    """长音频按段识别并拼接全文，分段按 ffmpeg 输出顺序提交。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"long-audio", "通话录音.mp3")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        for i in range(3):
            with open(cmd[-1].replace("%04d", f"{i:04d}"), "wb") as fh:
                fh.write(f"seg{i}".encode())
        return 0, "", ""

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("你好，这里是客服。"),
        _baidu_asr_response("请不要透露验证码。"),
        _baidu_asr_response("再见。"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/call.mp3", "通话录音.mp3", "audio")

    assert result["status"] == "success"
    assert result["text"] == "你好，这里是客服。请不要透露验证码。再见。"
    assert result["segments_used"] == 3 and result["segments_total"] == 3
    assert "note" not in result
    # 分段字节按序提交（第一调为 token 请求，无 json 体）
    payloads = [c["json"] for c in client.calls if c["json"]]
    assert [base64.b64decode(p["speech"]) for p in payloads] == [b"seg0", b"seg1", b"seg2"]


async def test_baidu_segments_capped_with_note(monkeypatch):
    """超出 BAIDU_MAX_SEGMENTS 的超长音频只转写前 N 段，并在结果中如实注明。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(asr, "BAIDU_MAX_SEGMENTS", 2)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"very-long", "long.mp3")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        for i in range(3):
            with open(cmd[-1].replace("%04d", f"{i:04d}"), "wb") as fh:
                fh.write(f"seg{i}".encode())
        return 0, "", ""

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("第一段。"),
        _baidu_asr_response("第二段。"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/long.mp3", "long.mp3", "audio")

    assert result["status"] == "success"
    assert result["text"] == "第一段。第二段。"
    assert result["segments_used"] == 2 and result["segments_total"] == 3
    assert "仅取前 2 段" in result["note"]
    assert len([c for c in client.calls if c["json"]]) == 2  # 第三段未上传


async def test_baidu_token_cached_across_evidence(monkeypatch):
    """token 进程级缓存：第二个检材不再请求 token 端点。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"x", "a.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        with open(cmd[-1].replace("%04d", "0000"), "wb") as fh:
            fh.write(b"seg")
        return 0, "", ""

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("第一次"),
        _baidu_asr_response("第二次"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    first = await asr.transcribe_audio_evidence("https://example.com/a.wav", "a.wav", "audio")
    second = await asr.transcribe_audio_evidence("https://example.com/b.wav", "b.wav", "audio")

    assert first["text"] == "第一次" and second["text"] == "第二次"
    token_calls = [c for c in client.calls if c["url"].endswith("/oauth/2.0/token")]
    assert len(token_calls) == 1


async def test_baidu_empty_audio_err_no_is_empty_success(monkeypatch):
    """空语音类 err_no（2000/3301/3314）等价于静音：返回空转写成功而非降级。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"silence", "s.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response(err_no=3301, err_msg="audio quality error."),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/s.wav", "s.wav", "audio")

    assert result["status"] == "success"
    assert result.get("degraded") is not True
    assert result["text"] == "" and result["char_count"] == 0


async def test_baidu_auth_failed_err_no_degrades(monkeypatch):
    """err_no=3302（鉴权失败）映射为可自解释的降级原因。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"x", "a.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response(err_no=3302, err_msg="authorization failed"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.wav", "a.wav", "audio")

    assert result["status"] == "error"
    assert result["degraded"] is True
    assert result["fallback_reason"] == "baidu_auth_failed_check_api_key_secret_key_or_quota"


async def test_baidu_transient_err_no_retried_then_success(monkeypatch):
    """服务端瞬时错误码（如 3303 后端繁忙）按重试策略重试后成功。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"x", "a.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response(err_no=3303, err_msg="server busy"),
        _baidu_asr_response("重试成功"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.wav", "a.wav", "audio")

    assert result["status"] == "success"
    assert result["text"] == "重试成功"
    assert len([c for c in client.calls if c["json"]]) == 2  # 首次失败 + 重试成功


async def test_baidu_audio_too_long_err_no_degrades_without_ffmpeg(monkeypatch):
    """无 ffmpeg 直传时超 60s 音频由服务端拒绝（err_no=3308），降级原因可自解释。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"long-wav", "long.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response(err_no=3308, err_msg="audio too long"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/long.wav", "long.wav", "audio")

    assert result["status"] == "error"
    assert result["fallback_reason"] == "baidu_audio_too_long_gt_60s"


async def test_baidu_token_rejected_invalid_credentials_degrades(monkeypatch):
    """token 端点 400（invalid_client）→ 凭证错误降级，不继续调用识别接口。"""
    _patch_baidu_runtime(monkeypatch, baidu_api_key="bad_key")
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"x", "a.wav")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        httpx.Response(400, json={"error": "invalid_client", "error_description": "API Key or Secret Key invalid"}),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.wav", "a.wav", "audio")

    assert result["status"] == "error"
    assert result["degraded"] is True
    assert result["fallback_reason"].startswith("baidu_token_rejected_http_400")
    # 百度返回的 error_description 会拼入降级原因，便于定位是哪类凭证问题
    assert "API Key or Secret Key invalid" in result["fallback_reason"]
    assert len(client.calls) == 1  # 凭证错误后不再调用识别接口


async def test_baidu_video_without_audio_track_makes_no_baidu_request(monkeypatch):
    """视频无音轨：记录正常结论，且不发起任何百度请求（token 也不取）。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"video-no-audio", "case.mp4")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    async def fake_run_process(cmd, timeout):
        if "ffprobe" in str(cmd[0]).lower():
            return 0, "", ""
        raise AssertionError("无音轨时不应调用 ffmpeg")

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/case.mp4", "case.mp4", "video")

    assert result["status"] == "success"
    assert result["provider"] == "baidu"
    assert result["has_audio_track"] is False
    assert result.get("degraded") is not True
    assert client.calls == []


async def test_baidu_video_with_audio_track_segments_and_uploads(monkeypatch):
    """视频有音轨：ffmpeg 直接从视频归一化+分段（-vn），逐段上传。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"video-with-audio", "case.mp4")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: f"/fake/{name}")

    seen_cmds: list[list[str]] = []

    async def fake_run_process(cmd, timeout):
        seen_cmds.append(list(cmd))
        if "ffprobe" in str(cmd[0]).lower():
            return 0, "audio\n", ""
        with open(cmd[-1].replace("%04d", "0000"), "wb") as fh:
            fh.write(b"video-track-segment")
        return 0, "", ""

    monkeypatch.setattr(asr, "_run_process", fake_run_process)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("视频音轨内容"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/case.mp4", "case.mp4", "video")

    assert result["status"] == "success"
    assert result["modality"] == "video"
    assert result["has_audio_track"] is True
    assert result["text"] == "视频音轨内容"
    # 分段命令携带 -vn，直接消费视频文件
    segment_cmd = next(c for c in seen_cmds if "segment" in c)
    assert "-vn" in segment_cmd


async def test_baidu_no_ffmpeg_direct_upload_supported_format(monkeypatch):
    """ffmpeg 不可用时，百度原生支持的格式（wav）原样直传。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"raw-wav-bytes", "录音.WAV")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([
        _baidu_token_response(),
        _baidu_asr_response("直传内容"),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.wav", "录音.WAV", "audio")

    assert result["status"] == "success"
    assert result["text"] == "直传内容"
    payload = client.calls[1]["json"]
    assert payload["format"] == "wav"  # 扩展名大写已归一
    assert payload["len"] == len(b"raw-wav-bytes")
    assert base64.b64decode(payload["speech"]) == b"raw-wav-bytes"


async def test_baidu_no_ffmpeg_unsupported_format_degrades(monkeypatch):
    """ffmpeg 不可用且格式百度不支持（如 mp3）：降级且不发起任何百度请求。"""
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"mp3-bytes", "a.mp3")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/a.mp3", "a.mp3", "audio")

    assert result["degraded"] is True
    assert result["fallback_reason"].startswith("ffmpeg_not_installed_and_format_unsupported_by_baidu")
    assert client.calls == []


async def test_baidu_no_ffmpeg_video_degrades(monkeypatch):
    _patch_baidu_runtime(monkeypatch)
    monkeypatch.setattr(
        asr, "download_evidence_bytes",
        lambda url, timeout=60.0: _async_value((b"video", "v.mp4")),
    )
    monkeypatch.setattr(asr, "_resolve_binary", lambda configured, name: None)
    client = _FakeAsyncClient([])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    result = await asr.transcribe_audio_evidence("https://example.com/v.mp4", "v.mp4", "video")

    assert result["degraded"] is True
    assert result["fallback_reason"] == "ffmpeg_not_installed"


def test_resolve_asr_runtime_provider_switch_hot(monkeypatch):
    """AUDIO_ASR_PROVIDER 与百度 Key 支持 .env 热加载；非法值有确定性回退。"""
    from app.config import resolve_asr_runtime, settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "BAIDU_ASR_API_KEY", "")
    monkeypatch.setattr(settings, "BAIDU_ASR_SECRET_KEY", "")
    monkeypatch.setattr(settings, "AUDIO_ASR_ENABLED", True)
    monkeypatch.setattr(settings, "AUDIO_ASR_PROVIDER", "groq")
    # 隔离真实 .env 热加载：resolve_asr_runtime 每次都重读 .env，若本机 .env 配了
    # 其他 provider/Key 会覆盖上面的 settings 值，导致该断言依赖运行环境。
    # 第一段语义是“无 dotenv 覆盖时回落到 settings”，故让热加载读到空配置。
    monkeypatch.setattr("app.config.dotenv_values", lambda path: {})

    runtime = resolve_asr_runtime()
    assert runtime["provider"] == "groq"

    monkeypatch.setattr(
        "app.config.dotenv_values",
        lambda path: {
            "AUDIO_ASR_PROVIDER": "baidu",
            "BAIDU_ASR_API_KEY": " ak_hot ",
            "BAIDU_ASR_SECRET_KEY": " sk_hot ",
            "BAIDU_ASR_DEV_PID": "17000",
            "AUDIO_ASR_ENABLED": "true",
        },
    )
    runtime = resolve_asr_runtime()
    assert runtime["provider"] == "baidu"
    assert runtime["baidu_api_key"] == "ak_hot"
    assert runtime["baidu_secret_key"] == "sk_hot"
    assert runtime["baidu_dev_pid"] == 17000

    # 未知 provider 回退 groq；非法 dev_pid 回退 80001
    monkeypatch.setattr(
        "app.config.dotenv_values",
        lambda path: {"AUDIO_ASR_PROVIDER": "azure", "BAIDU_ASR_DEV_PID": "not-a-number"},
    )
    runtime = resolve_asr_runtime()
    assert runtime["provider"] == "groq"
    assert runtime["baidu_dev_pid"] == 80001
