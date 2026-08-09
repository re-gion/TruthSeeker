import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_osint_tool_summary_keeps_claim_extract_social_only():
    from app.agents.nodes.osint import _summarize_tool

    summary = _summarize_tool(
        "text_claim_extract",
        {"key_claims": ["登录异常"], "ai_probability": 0.3},
    )

    assert "关键声明 1 条" in summary
    assert "社工风险" in summary
    assert "AI" not in summary
    assert "30.0%" not in summary
    assert "ai_probability=0.30" not in summary


def test_text_claim_extract_result_strips_aigc_probability_fields():
    from app.agents.nodes.osint import _sanitize_text_claim_extract_result

    sanitized = _sanitize_text_claim_extract_result(
        {
            "ai_probability": 0.91,
            "is_ai_generated": True,
            "local_ai_score": 0.8,
            "key_claims": ["24 小时内完成验证"],
            "social_engineering": {"score": 0.52},
            "manipulation_score": 0.52,
            "anomalies": ["要求核验身份"],
            "extracted_urls": ["http://example.test"],
        }
    )

    assert "ai_probability" not in sanitized
    assert "is_ai_generated" not in sanitized
    assert "local_ai_score" not in sanitized
    assert sanitized["key_claims"] == ["24 小时内完成验证"]
    assert sanitized["social_engineering"]["score"] == 0.52


def test_temporal_fact_table_marks_april_before_june_as_not_future():
    from app.agents.tools.llm_client import _build_temporal_fact_table

    facts = _build_temporal_fact_table(
        {
            "timestamp": "2026-06-04T02:13:26+00:00",
            "text_samples": [
                {
                    "name": "案例3-文本-客服通知.txt",
                    "content": "登录时间：2026-04-22 19:42",
                }
            ],
        }
    )

    assert "确定性时间校验" in facts
    assert "分析时间（北京时间）: 2026-06-04 10:13:26" in facts
    assert "2026-04-22 19:42" in facts
    assert "早于分析时间" in facts
    assert "不是未来日期" in facts
    assert "不得称为未来日期" in facts


@pytest.mark.asyncio
async def test_forensics_output_cannot_call_april_a_future_time_in_august(monkeypatch):
    from app.agents.tools import llm_client

    async def wrong_model_output(**_kwargs):
        return (
            "### 自主检材观察\n内容\n"
            "### 外部检测结果解读\n内容\n"
            "### 融合判断\n内容\n"
            "### 限制与复核建议\n"
            "**时间戳不可验证**：图片内嵌时间‘2026-04-22 19:42’为将来时"
            "（相对于分析时间 2026-08-06 北京时间 10:35）。"
        )

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", wrong_model_output)

    result = await llm_client.forensics_interpret(
        {
            "timestamp": "2026-08-06T02:35:00+00:00",
        },
        "image",
    )

    assert "为将来时" not in result
    assert "，是未来日期" not in result
    assert "为未来日期" not in result
    assert "早于分析时间" in result


def test_temporal_guard_preserves_a_real_future_date_in_another_clause():
    from app.agents.tools.llm_client import enforce_temporal_consistency

    result = enforce_temporal_consistency(
        "图片内嵌时间 2026-04-22 19:42 不是未来日期；"
        "公告时间 2026-09-01 09:00 属于未来。",
        {"timestamp": "2026-08-06T02:35:00+00:00"},
    )

    assert "2026-04-22 19:42 不是未来日期" in result
    assert "公告时间 2026-09-01 09:00 属于未来" in result


def test_temporal_guard_does_not_rewrite_not_in_future_wording():
    from app.agents.tools.llm_client import enforce_temporal_consistency

    source = "图片内嵌时间 2026-04-22 19:42 不属于未来。"
    result = enforce_temporal_consistency(
        source,
        {"timestamp": "2026-08-06T02:35:00+00:00"},
    )

    assert result == source
