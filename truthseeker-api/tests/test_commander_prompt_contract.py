import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _bloated_forensics() -> dict:
    return {
        "llm_analysis": "取证分析叙述。" * 400,
        "confidence": 0.62,
        "aigc_probability": 0.19,
        "media_aigc_probability": 0.19,
        "text_aigc_probability": 0.1,
        "is_aigc": False,
        "degraded": True,
        "audio_transcripts": [
            {
                "target": "video.mp4",
                "has_audio_track": True,
                "language": "zh",
                "char_count": 5000,
                "truncated": True,
                "text": "转写内容" * 1500,
            }
        ],
        "text_samples": [{"name": "a.txt", "content": "文本检材" * 1200}],
        "tool_results": [
            {
                "tool": "reality_defender",
                "target": "video.mp4",
                "status": "success",
                "degraded": False,
                "summary": "aigc_probability=0.19, confidence=0.62",
                "result": {
                    "raw": "x" * 120_000,
                    "frame_inferences": [{"index": i, "score": 0.5} for i in range(2000)],
                },
            }
        ],
        "case_rag": {
            "status": "success",
            "summary": "命中类案",
            "matches": [
                {"title": f"案例{i}", "summary": "s" * 60, "chunk_text": "c" * 5000}
                for i in range(5)
            ],
        },
        "experience_rag": {"status": "success", "summary": "无命中", "matches": []},
        "skill_execution": {"skill_name": "forensics-analysis", "limitations": ["k" * 3000]},
    }


def _bloated_osint() -> dict:
    return {
        "llm_analysis": "情报溯源叙述。" * 400,
        "confidence": 0.8,
        "threat_score": 0.35,
        "social_engineering_score": 0.2,
        "is_malicious": False,
        "is_suspicious": True,
        "degraded": False,
        "threat_indicators": [f"indicator-{i}" for i in range(20)],
        "model_claims": [{"id": f"claim-{i}", "label": "l" * 200} for i in range(20)],
        "search_results": [
            {"title": f"result-{i}", "url": f"https://example.com/{i}", "summary": "r" * 280, "text": "t" * 3000}
            for i in range(15)
        ],
        "domain_provenance_summary": [
            {
                "domain": "example.com",
                "status": "success",
                "summary": "WHOIS 可用",
                "whois": {"raw": "w" * 20_000, "registrar": "reg"},
                "dns": {"records": "d" * 5000},
                "geo": {"country": "US"},
            }
        ],
        "tool_results": [
            {"tool": "exa_search", "target": "q", "status": "success", "degraded": False,
             "summary": "Exa status=success", "result": {"results": "e" * 50_000}}
        ],
        "provenance_graph": {
            "nodes": [{"id": f"n{i}", "payload": "p" * 300} for i in range(300)],
            "edges": [{"id": f"e{i}", "payload": "q" * 300} for i in range(300)],
            "citations": [{"id": f"c{i}", "payload": "r" * 300} for i in range(300)],
            "quality": {"citation_coverage": 0.9},
        },
        "case_rag": {"status": "success", "summary": "无", "matches": []},
        "experience_rag": {"status": "success", "summary": "无", "matches": []},
        "upstream_verified_conclusions": [{"label": "图像AIGC", "value": "概率19%"}],
    }


def _bloated_challenger() -> dict:
    return {
        "round": 2,
        "phase": "forensics",
        "phase_round": 2,
        "confidence": 0.75,
        "quality_score": 0.7,
        "quality_delta": 0.05,
        "issue_count": 2,
        "high_severity_count": 0,
        "medium_severity_count": 1,
        "requires_more_evidence": False,
        "target_agent": None,
        "next_action": "release",
        "action_reason": "置信度达标" * 100,
        "max_rounds_release": False,
        "issues_found": [
            {"type": "evidence_gap", "severity": "medium", "agent": "forensics",
             "description": "质询问题描述" + "d" * 2000}
        ],
        "llm_cross_validation": "跨视角互证叙述。" * 1000,
        "residual_risks": ["残留风险" * 100] * 12,
        "consultation_sessions": [{"session": "consultation-session-payload", "blob": "s" * 10_000}],
        "collaboration_sessions": [{"session": "consultation-session-payload", "blob": "s" * 10_000}],
        "consultation_trigger_history": [{"trigger-history": "h" * 2000}],
        "collaboration_trigger_history": [{"trigger-history": "h" * 2000}],
        "consultation_resume_payload": {"blob": "p" * 5000},
        "suppressed_issues": [{"description": "sup" * 500}],
        "challenger_experience_rag": {"matches": [{"chunk_text": "m" * 4000}]},
        "experience_rag": {"matches": [{"chunk_text": "m" * 4000}]},
        "skill_execution": {"limitations": ["k" * 3000]},
    }


@pytest.mark.asyncio
async def test_commander_prompt_matches_the_four_structured_verdict_classes(monkeypatch):
    from app.agents.tools import llm_client

    captured: dict[str, str] = {}

    async def capture_prompt(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return "裁决报告"

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture_prompt)

    result = await llm_client.commander_ruling(
        forensics={},
        osint={},
        challenger_feedback={},
        agent_weights={"forensics": 0.45, "osint": 0.30, "challenger": 0.25},
    )

    assert result == "裁决报告"
    assert "最终裁决结论（伪造/可疑/真实/无法判定）" in captured["system_prompt"]
    assert "不得自行输出第二个综合置信度数值" in captured["system_prompt"]
    assert "不得引用 forensics_score 充当综合置信度" in captured["system_prompt"]


@pytest.mark.asyncio
async def test_commander_prompt_stays_bounded_on_bloated_agent_results(monkeypatch):
    """完整 Agent 结果序列化可达数十万字符（22P05 事故案例为 56 万），
    Commander 提示词必须走有界摘要，保留裁决叙述所需的关键内容。"""
    from app.agents.tools import llm_client

    captured: dict[str, str] = {}

    async def capture_prompt(**kwargs):
        captured["human_text"] = kwargs["human_text"]
        return "裁决报告"

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture_prompt)

    forensics = _bloated_forensics()
    osint = _bloated_osint()
    challenger = _bloated_challenger()

    raw_size = len(json.dumps([forensics, osint, challenger], ensure_ascii=False, default=str))
    assert raw_size > 300_000, "测试前置：原始结果序列化必须确实巨大"

    await llm_client.commander_ruling(
        forensics=forensics,
        osint=osint,
        challenger_feedback=challenger,
        agent_weights={"forensics": 0.25, "osint": 0.15, "challenger": 0.60},
        case_prompt="视频文本检材复核",
    )

    human_text = captured["human_text"]
    assert len(human_text) < 80_000

    # 裁决叙述所需的关键内容必须保留
    assert "取证分析叙述" in human_text
    assert "情报溯源叙述" in human_text
    assert "质询问题描述" in human_text
    assert "转写内容" in human_text
    assert "aigc_probability=0.19" in human_text
    assert "跨视角互证叙述" in human_text
    assert "example.com" in human_text
    assert "图像AIGC" in human_text

    # 膨胀源不得进入提示词：原始工具大对象、图谱完整 JSON、协同会话历史
    assert "x" * 1000 not in human_text
    assert "p" * 200 not in human_text
    assert "consultation-session-payload" not in human_text
    assert "trigger-history" not in human_text


def test_challenger_summary_drops_sessions_and_caps_text():
    from app.agents.tools import llm_client

    summary = llm_client._summarize_challenger_for_commander(_bloated_challenger())
    serialized = json.dumps(summary, ensure_ascii=False)

    assert "consultation-session-payload" not in serialized
    assert "trigger-history" not in serialized
    assert summary["phase"] == "forensics"
    assert summary["confidence"] == 0.75
    assert summary["issues_found"][0]["description"].startswith("质询问题描述")
    assert len(summary["issues_found"][0]["description"]) <= 600 + len("质询问题描述")
    assert len(summary["llm_cross_validation"]) <= 3000
    assert len(summary["residual_risks"]) <= 8
    assert len(summary["action_reason"]) <= 300
