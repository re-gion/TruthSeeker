"""视频分解检测回归：音轨 → Reality Defender，画面关键帧 → Sightengine。

背景：RD 免费套餐拒绝视频整段上传（403 free-tier-restriction），
视频检材按能力边界分解——音频维度抽音轨送 RD，画面维度抽关键帧逐帧送
Sightengine genai，聚合帧间最大 AI 生成概率参与取证评分。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.tools import deepfake_api, video_observation


def _sightengine_result(prob: float) -> dict:
    return {
        "aigc_probability": prob,
        "is_ai_generated": prob >= 0.5,
        "confidence": prob if prob >= 0.5 else 1.0 - prob,
        "analysis_available": True,
    }


# ---------- analyze_video_keyframes ----------

@pytest.mark.asyncio
async def test_video_keyframes_aggregate_max_probability(monkeypatch):
    async def fake_download(url, timeout=120.0, range_header=None):
        return b"video-bytes", "案例10-视频-经理.mp4"

    async def fake_frames(video_bytes, hint, *, max_frames=3):
        return [b"frame1", b"frame2", b"frame3"]

    seen: list[str] = []

    async def fake_detect(filename, file_data):
        seen.append(filename)
        frame_no = int(filename.split("#frame")[1].split(".")[0])
        return _sightengine_result({1: 0.12, 2: 0.87, 3: 0.30}[frame_no])

    monkeypatch.setattr(deepfake_api, "download_evidence_bytes", fake_download)
    monkeypatch.setattr(video_observation, "extract_keyframe_images", fake_frames)
    monkeypatch.setattr(deepfake_api, "_sightengine_detect", fake_detect)
    monkeypatch.setattr(deepfake_api, "_get_sightengine_credentials", lambda: ("u", "s"))

    result = await deepfake_api.analyze_video_keyframes("mock://video", "案例10-视频-经理.mp4")

    assert result["analysis_available"] is True
    assert result["frames_analyzed"] == 3
    assert result["aigc_probability"] == pytest.approx(0.87)
    assert result["is_aigc"] is True
    assert result["confidence"] == pytest.approx(0.87)
    assert result["detection_scope"] == "video_keyframe_aigc"
    assert len(seen) == 3
    # 聚合结果不得携带 Sightengine 原始响应，避免工具矩阵膨胀
    assert "raw_response" not in result


@pytest.mark.asyncio
async def test_video_keyframes_degrade_when_extraction_unavailable(monkeypatch):
    async def fake_download(url, timeout=120.0, range_header=None):
        return b"video-bytes", "case.mp4"

    async def fake_frames(video_bytes, hint, *, max_frames=3):
        return []

    monkeypatch.setattr(deepfake_api, "download_evidence_bytes", fake_download)
    monkeypatch.setattr(video_observation, "extract_keyframe_images", fake_frames)

    result = await deepfake_api.analyze_video_keyframes("mock://video", "case.mp4")

    assert result["degraded"] is True
    assert result["analysis_available"] is False
    assert "keyframe_extraction_unavailable" in result["details"]["fallback_reason"]


@pytest.mark.asyncio
async def test_video_keyframes_degrade_when_all_frames_fail(monkeypatch):
    async def fake_download(url, timeout=120.0, range_header=None):
        return b"video-bytes", "case.mp4"

    async def fake_frames(video_bytes, hint, *, max_frames=3):
        return [b"frame1"]

    async def fake_detect(filename, file_data):
        raise PermissionError("missing_sightengine_credentials")

    monkeypatch.setattr(deepfake_api, "download_evidence_bytes", fake_download)
    monkeypatch.setattr(video_observation, "extract_keyframe_images", fake_frames)
    monkeypatch.setattr(deepfake_api, "_sightengine_detect", fake_detect)
    monkeypatch.setattr(deepfake_api, "_get_sightengine_credentials", lambda: ("u", "s"))

    result = await deepfake_api.analyze_video_keyframes("mock://video", "case.mp4")

    assert result["degraded"] is True
    assert "sightengine_all_frames_failed" in result["details"]["fallback_reason"]


# ---------- analyze_video_audio_track ----------

@pytest.mark.asyncio
async def test_video_audio_track_no_audio_is_normal_success(monkeypatch):
    async def fake_download(url, timeout=120.0, range_header=None):
        return b"video-bytes", "case.mp4"

    async def fake_audio(video_bytes, hint):
        return None

    monkeypatch.setattr(deepfake_api, "download_evidence_bytes", fake_download)
    monkeypatch.setattr(video_observation, "extract_audio_track_bytes", fake_audio)

    result = await deepfake_api.analyze_video_audio_track("mock://video", "case.mp4")

    assert result["status"] == "success"
    assert result["degraded"] is False
    assert result["analysis_available"] is False
    assert result["has_audio_track"] is False


@pytest.mark.asyncio
async def test_video_audio_track_sends_audio_to_rd(monkeypatch):
    async def fake_download(url, timeout=120.0, range_header=None):
        return b"video-bytes", "案例10-视频-经理.mp4"

    async def fake_audio(video_bytes, hint):
        return b"mp3-audio-bytes"

    captured: dict = {}

    async def fake_rd_bytes(seed_reference, filename, file_data, media_type):
        captured.update(seed=seed_reference, filename=filename, data=file_data, media_type=media_type)
        return {"is_aigc": False, "aigc_probability": 0.1, "confidence": 0.9, "analysis_available": True}

    monkeypatch.setattr(deepfake_api, "download_evidence_bytes", fake_download)
    monkeypatch.setattr(video_observation, "extract_audio_track_bytes", fake_audio)
    monkeypatch.setattr(deepfake_api, "_rd_analyze_bytes", fake_rd_bytes)

    result = await deepfake_api.analyze_video_audio_track("mock://video", "案例10-视频-经理.mp4")

    assert result["analysis_available"] is True
    assert captured["media_type"] == "audio"
    assert captured["filename"].endswith("_audiotrack.mp3")
    assert captured["data"] == b"mp3-audio-bytes"


# ---------- forensics 分发 ----------

@pytest.mark.asyncio
async def test_forensics_dispatches_video_to_keyframes_and_audio_track(monkeypatch):
    from app.agents.nodes import forensics

    async def fake_keyframes(url, hint, **kwargs):
        return {
            "status": "success",
            "analysis_available": True,
            "is_aigc": True,
            "aigc_probability": 0.87,
            "confidence": 0.87,
            "frames_analyzed": 3,
            "frames_total": 3,
        }

    async def fake_audio_track(url, hint):
        return {
            "status": "success",
            "degraded": False,
            "analysis_available": False,
            "has_audio_track": False,
            "is_aigc": False,
            "aigc_probability": 0.0,
            "confidence": 0.0,
            "note": "视频检材未检测到音轨，无需 RD 音频检测",
        }

    async def fake_interpret(raw_api_result, input_type, case_prompt="", sample_refs=None,
                            text_contents=None, *, skill_context="", llm_status=None):
        if llm_status is not None:
            llm_status.update({"status": "success", "mode": "multimodal"})
        return "### 自主检材观察\n观察内容"

    async def empty_search(**kwargs):
        tool = "experience_rag_search" if kwargs.get("agent") == "forensics" and "user_id" in kwargs else "case_rag_search"
        return {"tool": tool, "status": "success", "matches": [], "degraded": False, "summary": "无命中"}

    async def fake_scan(url):
        return {
            "status": "success",
            "scan_available": True,
            "hash": "0" * 64,
            "malicious": 0,
            "suspicious": 0,
            "threat_score": 0.0,
        }

    monkeypatch.setattr(forensics, "analyze_video_keyframes", fake_keyframes)
    monkeypatch.setattr(forensics, "analyze_video_audio_track", fake_audio_track)
    monkeypatch.setattr(forensics, "scan_file_hash", fake_scan)
    monkeypatch.setattr(forensics, "forensics_interpret", fake_interpret)
    monkeypatch.setattr(forensics, "case_rag_search", empty_search)
    monkeypatch.setattr(forensics, "experience_rag_search", empty_search)
    monkeypatch.setattr(forensics, "record_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(forensics, "resolve_kimi_runtime", lambda: {"model": "test-model"})
    monkeypatch.setattr(forensics, "resolve_asr_runtime", lambda: {"enabled": False, "api_key": ""})

    state = {
        "task_id": "task-video-split",
        "user_id": "u1",
        "input_type": "text_video",
        "case_prompt": "",
        "priority_focus": "balanced",
        "evidence_files": [
            {
                "id": "video-1",
                "name": "案例10-视频-经理.mp4",
                "modality": "video",
                "mime_type": "video/mp4",
                "file_url": "https://storage.example/v.mp4",
                "storage_path": "u1/v.mp4",
            },
        ],
        "current_round": 1,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "analysis_phase": "forensics",
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "phase_quality_history": {},
        "phase_residual_risks": [],
        "forensics_result": None,
        "osint_result": None,
        "challenger_feedback": None,
        "evidence_board": [],
        "confidence_history": [],
        "tool_results": {},
        "logs": [],
        "timeline_events": [],
    }

    result = await forensics.forensics_node(state)
    tools = {item["tool"] for item in result["forensics_result"]["tool_results"]}

    # 视频必须分解为关键帧检测 + 音轨 RD 检测两个工具，而不是整段送 RD
    assert "video_keyframe_aigc" in tools
    assert "reality_defender" in tools
    # 关键帧概率必须进入 media_aigc_probability
    assert result["forensics_result"]["media_aigc_probability"] == pytest.approx(0.87)
    summary = result["forensics_result"]["tool_summary"]
    assert summary["degraded"] == 0
    # 无音轨是正常结论，不计入降级
    assert result["degradation_status"]["reality_defender"] == "ok"
