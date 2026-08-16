"""回归测试：视频检材观察路径（原生视频内联 / 关键帧 / 边界说明）。

背景：kimi-k2.6 在 Moonshot 官方平台原生支持 video_url，但此前代码只把
图片传给多模态模型，视频仅以文本引用出现，取证 Agent 始终"看不见"视频，
逻辑质询连续打回。观察路径按提供商与体积选择内联视频或关键帧，
且只在取证阶段开启（observe_video），其他阶段保持文本引用。
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.tools import llm_client, video_observation


def _video_ref(**overrides) -> dict:
    ref = {
        "id": "video-1",
        "name": "case-video.mp4",
        "modality": "video",
        "mime_type": "video/mp4",
        "signed_url": "https://storage.example/case-video.mp4?token=x",
        "storage_path": "user/case-video.mp4",
    }
    ref.update(overrides)
    return ref


class _FakeLLM:
    def __init__(self, sink: list):
        self.sink = sink

    async def ainvoke(self, messages):
        self.sink.append(messages)

        class _Response:
            content = "ok"

        return _Response()


def _human_parts(captured: list) -> list:
    messages = captured[0]
    content = messages[-1].content
    assert isinstance(content, list), "多模态调用必须使用 content parts"
    return content


# ---------- _build_multimodal_parts ----------

def test_parts_inline_video_emits_video_url():
    parts = llm_client._build_multimodal_parts(
        "prompt", [_video_ref(video_inline_url="data:video/mp4;base64,AAA")]
    )
    assert any(
        part.get("type") == "video_url" and part["video_url"]["url"] == "data:video/mp4;base64,AAA"
        for part in parts
    )


def test_parts_keyframes_emit_images_and_note():
    frames = ["data:image/jpeg;base64,A", "data:image/jpeg;base64,B"]
    parts = llm_client._build_multimodal_parts("prompt", [_video_ref(video_keyframes=frames)])
    images = [part for part in parts if part.get("type") == "image_url"]
    assert [part["image_url"]["url"] for part in images] == frames
    notes = " ".join(part.get("text", "") for part in parts if part.get("type") == "text")
    assert "2 帧关键帧" in notes


def test_parts_unavailable_video_states_boundary():
    parts = llm_client._build_multimodal_parts(
        "prompt", [_video_ref(signed_url=None, storage_path=None)]
    )
    serialized = str(parts)
    assert "无法直接观察" in serialized
    assert "video_url" not in serialized


# ---------- _invoke_multimodal_llm 观察通道 ----------

@pytest.mark.asyncio
async def test_invoke_multimodal_attaches_inline_video_for_official(monkeypatch):
    captured: list = []
    monkeypatch.setattr(llm_client, "get_llm", lambda *args, **kwargs: _FakeLLM(captured))
    monkeypatch.setattr(
        llm_client, "resolve_kimi_runtime",
        lambda *args, **kwargs: {"provider": "official", "model": "kimi-k2.6"},
    )

    async def fake_fetch(reference):
        return b"VIDEOBYTES", "case-video.mp4"

    monkeypatch.setattr(video_observation, "fetch_video_bytes", fake_fetch)

    result = await llm_client._invoke_multimodal_llm(
        system_prompt="sys",
        human_text="case",
        sample_refs=[_video_ref()],
        fallback_text="fallback",
        observe_video=True,
    )
    assert result == "ok"
    parts = _human_parts(captured)
    video_parts = [part for part in parts if part.get("type") == "video_url"]
    assert len(video_parts) == 1
    assert video_parts[0]["video_url"]["url"].startswith("data:video/mp4;base64,")


@pytest.mark.asyncio
async def test_invoke_multimodal_uses_keyframes_for_non_official_provider(monkeypatch):
    captured: list = []
    monkeypatch.setattr(llm_client, "get_llm", lambda *args, **kwargs: _FakeLLM(captured))
    monkeypatch.setattr(
        llm_client, "resolve_kimi_runtime",
        lambda *args, **kwargs: {"provider": "siliconflow", "model": "Pro/moonshotai/Kimi-K2.6"},
    )

    async def fake_fetch(reference):
        return b"VIDEOBYTES", "case-video.mp4"

    async def fake_frames(video_bytes, hint, *, max_frames=6):
        return ["data:image/jpeg;base64,FRAME1"]

    monkeypatch.setattr(video_observation, "fetch_video_bytes", fake_fetch)
    monkeypatch.setattr(video_observation, "extract_keyframes", fake_frames)

    await llm_client._invoke_multimodal_llm(
        system_prompt="sys",
        human_text="case",
        sample_refs=[_video_ref()],
        fallback_text="fallback",
        observe_video=True,
    )
    parts = _human_parts(captured)
    assert not any(part.get("type") == "video_url" for part in parts)
    images = [part for part in parts if part.get("type") == "image_url"]
    assert [part["image_url"]["url"] for part in images] == ["data:image/jpeg;base64,FRAME1"]


@pytest.mark.asyncio
async def test_video_not_observed_when_flag_disabled(monkeypatch):
    """非取证阶段（observe_video=False）保持文本引用，不产生视频内容块。"""
    captured: list = []
    monkeypatch.setattr(llm_client, "get_llm", lambda *args, **kwargs: _FakeLLM(captured))
    monkeypatch.setattr(
        llm_client, "resolve_kimi_runtime",
        lambda *args, **kwargs: {"provider": "official", "model": "kimi-k2.6"},
    )

    await llm_client._invoke_multimodal_llm(
        system_prompt="sys",
        human_text="case",
        sample_refs=[_video_ref()],
        fallback_text="fallback",
    )
    parts = _human_parts(captured)
    assert not any(part.get("type") in {"video_url", "image_url"} for part in parts)
    text_blocks = " ".join(part.get("text", "") for part in parts if part.get("type") == "text")
    assert "样本引用" in text_blocks and "video" in text_blocks


@pytest.mark.asyncio
async def test_resolve_video_observation_oversize_falls_back_to_frames(monkeypatch):
    async def fake_fetch(reference):
        return b"x" * (video_observation.MAX_INLINE_VIDEO_BYTES + 1), "big.mp4"

    async def fake_frames(video_bytes, hint, *, max_frames=6):
        return ["data:image/jpeg;base64,F"]

    monkeypatch.setattr(video_observation, "fetch_video_bytes", fake_fetch)
    monkeypatch.setattr(video_observation, "extract_keyframes", fake_frames)

    ref = _video_ref()
    ok = await llm_client._resolve_video_observation(ref, "official")
    assert ok
    assert ref.get("video_keyframes") == ["data:image/jpeg;base64,F"]
    assert "video_inline_url" not in ref


# ---------- video_observation 模块 ----------

def test_video_data_uri_mime_mapping():
    assert video_observation.video_data_uri(b"abc", "x.mov").startswith("data:video/quicktime;base64,")
    assert video_observation.video_data_uri(b"abc", "x.webm").startswith("data:video/webm;base64,")
    assert video_observation.video_data_uri(b"abc", "x.unknown").startswith("data:video/mp4;base64,")


@pytest.mark.asyncio
async def test_fetch_video_bytes_skips_mock_reference():
    assert await video_observation.fetch_video_bytes("mock://case10") is None
    assert await video_observation.fetch_video_bytes("") is None


@pytest.mark.asyncio
async def test_extract_keyframes_uniform_sampling_and_caps(monkeypatch):
    calls: list[list[str]] = []

    async def fake_run(cmd, timeout):
        calls.append(list(cmd))
        if "ffprobe" in os.path.basename(cmd[0]):
            return 0, "12.0\n", ""
        out_pattern = cmd[-1]
        out_dir = os.path.dirname(out_pattern)
        for index in (1, 2):
            with open(os.path.join(out_dir, f"frame_{index:02d}.jpg"), "wb") as fh:
                fh.write(b"\xff\xd8fakejpeg")
        return 0, "", ""

    monkeypatch.setattr(video_observation, "_run_process", fake_run)
    monkeypatch.setattr(
        video_observation, "_resolve_binary",
        lambda configured, name: f"C:/fake/{name}.exe",
    )

    frames = await video_observation.extract_keyframes(b"video-bytes", "case.mp4")
    assert len(frames) == 2
    assert all(frame.startswith("data:image/jpeg;base64,") for frame in frames)

    ffmpeg_cmd = calls[-1]
    vf_value = ffmpeg_cmd[ffmpeg_cmd.index("-vf") + 1]
    # 12 秒抽 6 帧 → fps=0.5；帧数上限必须传给 ffmpeg
    assert "fps=0.5000" in vf_value
    assert "-frames:v" in ffmpeg_cmd
    assert ffmpeg_cmd[ffmpeg_cmd.index("-frames:v") + 1] == "6"


@pytest.mark.asyncio
async def test_extract_keyframes_without_ffmpeg_returns_empty(monkeypatch):
    monkeypatch.setattr(video_observation, "_resolve_binary", lambda configured, name: None)
    assert await video_observation.extract_keyframes(b"video-bytes", "case.mp4") == []
