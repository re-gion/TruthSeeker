import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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
