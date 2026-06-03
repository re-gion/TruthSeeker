import pytest

from app.services.consultation_workflow import (
    build_moderator_summary,
    build_consultation_context,
    evaluate_consultation_trigger,
    latest_human_consultation_messages,
)


def _challenge(
    *,
    target_agent="forensics",
    confidence=0.72,
    high=True,
    quality_delta=0.02,
    round_number=1,
):
    return {
        "round": round_number,
        "target_agent": target_agent,
        "phase": target_agent,
        "confidence": confidence,
        "quality_delta": quality_delta,
        "high_severity_count": 1 if high else 0,
        "issues": [
            {"severity": "high" if high else "medium", "description": "证据链无法闭合"}
        ],
    }


def test_three_round_low_confidence_stable_high_challenge_triggers_consultation():
    result = evaluate_consultation_trigger(
        [
            _challenge(confidence=0.74, quality_delta=None, round_number=1),
            _challenge(confidence=0.71, quality_delta=0.03, round_number=2),
            _challenge(confidence=0.69, quality_delta=0.02, round_number=3),
        ],
        existing_sessions=[],
    )

    assert result["should_pause"] is True
    assert result["event_type"] == "consultation_required"
    assert result["target_agent"] == "forensics"
    assert result["repeat_index"] == 1


def test_three_round_trigger_requires_same_target_and_adjacent_delta():
    mixed_target = evaluate_consultation_trigger(
        [
            _challenge(target_agent="forensics", round_number=1),
            _challenge(target_agent="osint", round_number=2),
            _challenge(target_agent="forensics", round_number=3),
        ],
        existing_sessions=[],
    )
    noisy_delta = evaluate_consultation_trigger(
        [
            _challenge(confidence=0.62, quality_delta=None, round_number=1),
            _challenge(confidence=0.77, quality_delta=0.15, round_number=2),
            _challenge(confidence=0.70, quality_delta=0.07, round_number=3),
        ],
        existing_sessions=[],
    )

    assert mixed_target["should_pause"] is False
    assert noisy_delta["should_pause"] is False


def test_consultation_trigger_is_scoped_to_current_phase():
    result = evaluate_consultation_trigger(
        [
            _challenge(target_agent="forensics", round_number=1),
            _challenge(target_agent="forensics", round_number=2),
            _challenge(target_agent="forensics", round_number=3) | {"phase": "osint"},
        ],
        existing_sessions=[],
    )

    assert result["should_pause"] is False


def test_repeated_deadlock_requires_user_approval_before_consultation():
    result = evaluate_consultation_trigger(
        [
            _challenge(confidence=0.74, quality_delta=None, round_number=1),
            _challenge(confidence=0.71, quality_delta=0.03, round_number=2),
            _challenge(confidence=0.69, quality_delta=0.02, round_number=3),
        ],
        existing_sessions=[{"id": "session-1", "status": "summary_confirmed"}],
    )

    assert result["should_pause"] is True
    assert result["event_type"] == "consultation_approval_required"
    assert result["requires_user_approval"] is True
    assert result["repeat_index"] == 2


def test_moderator_summary_uses_confirmed_user_text_when_present():
    summary = build_moderator_summary(
        messages=[
            {"role": "expert", "message": "建议核验原始发布时间"},
            {"role": "user", "message": "我认为需要优先查证来源账号"},
        ],
        user_confirmed_summary="用户确认：来源账号是破局关键。",
    )

    assert summary["confirmed_summary"] == "用户确认：来源账号是破局关键。"
    assert summary["message_count"] == 2
    assert summary["key_quotes"][0]["role"] == "expert"


def test_consultation_context_deduplicates_high_issues_and_builds_expert_tasks():
    trigger = {
        "reason": "forensics 连续低置信",
        "target_agent": "forensics",
        "recent_challenges": [
            {
                "issues": [
                    {"type": "tool_failed", "severity": "high", "description": "工具失败", "agent": "forensics"},
                    {"type": "tool_failed", "severity": "high", "description": "工具失败", "agent": "forensics"},
                    {"type": "thin_graph", "severity": "medium", "description": "图谱偏薄", "agent": "osint"},
                ]
            }
        ],
    }

    context = build_consultation_context(
        task_id="task-1",
        case_prompt="核验样本",
        evidence_files=[],
        forensics_result={"confidence": 0.42},
        osint_result={"confidence": 0.61},
        challenger_feedback={"confidence": 0.38},
        trigger=trigger,
    )

    assert context["help_needed"] == ["工具失败"]
    assert len(context["expert_tasks"]) == 1
    assert context["expert_tasks"][0]["target_agent"] == "forensics"
    assert "工具失败" in context["expert_tasks"][0]["question"]


def test_consultation_context_keeps_semantic_dedupe_for_commander_llm():
    trigger = {
        "reason": "osint 连续低置信",
        "target_agent": "osint",
        "recent_challenges": [
            _challenge(
                target_agent="osint",
                round_number=1,
                high=True,
            ) | {
                "issues": [{
                    "type": "osint_tool_degraded",
                    "severity": "high",
                    "agent": "osint",
                    "description": "WhoisXML域名溯源工具降级（HTTPStatusError 422），导致无法获取moroba.com.br的注册人信息、注册时间、DNS历史及IP归属地。",
                }]
            },
            _challenge(
                target_agent="osint",
                round_number=2,
                high=True,
            ) | {
                "issues": [{
                    "type": "osint_tool_degraded",
                    "severity": "high",
                    "agent": "osint",
                    "description": "WhoisXML域名溯源工具降级（HTTPStatusError 422），未能获取moroba.com.br的注册人信息、注册时间、DNS历史及IP归属地。",
                }]
            },
            _challenge(
                target_agent="osint",
                round_number=3,
                high=True,
            ) | {
                "issues": [{
                    "type": "osint_tool_degraded",
                    "severity": "high",
                    "agent": "osint",
                    "description": "WhoisXML域名溯源工具持续降级（HTTPStatusError 422），导致无法获取moroba.com.br的注册人信息、注册时间、DNS历史及IP归属地。",
                }]
            },
        ],
    }

    context = build_consultation_context(
        task_id="task-1",
        case_prompt="核验钓鱼样本",
        evidence_files=[],
        forensics_result={"confidence": 0.82},
        osint_result={"confidence": 0.61},
        challenger_feedback={"confidence": 0.38},
        trigger=trigger,
    )

    assert len(context["help_needed"]) == 3
    assert "WhoisXML" in context["help_needed"][0]
    assert len(context["expert_tasks"]) == 3


@pytest.mark.asyncio
async def test_commander_llm_deduplicates_consultation_help_needed(monkeypatch):
    from app.agents.tools import llm_client

    async def fake_invoke(*_args, **_kwargs):
        return """{
          "help_needed": ["文本检测三轮均指向同一证据链缺口：需要专家判断客服通知文本是否存在 AI 生成或人工模板构造特征。"],
          "expert_tasks": [{
            "target_agent": "forensics",
            "issue_type": "model_challenge",
            "severity": "high",
            "question": "请专家判断客服通知文本的生成方式，并说明是否影响图文证据链。",
            "requested_action": "合并重复问题后给出一到三条补证建议。",
            "expected_output": "文本生成方式判断、证据链影响、后续补证动作。"
          }]
        }"""

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", fake_invoke)
    context = {
        "help_needed": [
            "文本AIGC检测因Unicode编码错误降级，无法判定客服通知文本是否为AI生成。",
            "文本检测工具仍处于降级状态，无法判断客服通知文本是AI生成还是人工撰写。",
            "连续三轮未能提供文本生成概率评估，图文混合证据链断裂。",
        ],
        "expert_tasks": [],
        "trigger": {"target_agent": "forensics", "reason": "forensics 连续低置信"},
    }

    result = await llm_client.commander_dedupe_consultation_context(context, case_prompt="核验客服通知")

    assert result["help_needed"] == ["文本检测三轮均指向同一证据链缺口：需要专家判断客服通知文本是否存在 AI 生成或人工模板构造特征。"]
    assert len(result["expert_tasks"]) == 1
    assert result["expert_tasks"][0]["target_agent"] == "forensics"


def test_consultation_workflow_has_no_text_aigc_api_specific_canonical_rule():
    from pathlib import Path

    source = Path("app/services/consultation_workflow.py").read_text(encoding="utf-8")

    assert "TEXT_AIGC_DEGRADED_HELP" not in source
    assert "_is_text_aigc_detector_degraded" not in source
    assert "_similar_issue_key" not in source
    assert "aidetectorapi" not in source.lower()


def test_moderator_summary_filters_system_messages_and_deduplicates_human_quotes():
    messages = [
        {"id": "m1", "role": "expert", "message": "需要补充原始发布时间？", "created_at": "2026-04-29T01:00:00+00:00"},
        {"id": "m1", "role": "expert", "message": "需要补充原始发布时间？", "created_at": "2026-04-29T01:00:00+00:00"},
        {"role": "commander", "message": "系统摘要，不应进入人工统计", "message_type": "summary"},
        {"role": "system", "message": "自动提示"},
        {"role": "user", "message": "我确认先查账号归属。", "created_at": "2026-04-29T01:01:00+00:00"},
    ]

    summary = build_moderator_summary(messages=messages)

    assert summary["human_message_count"] == 2
    assert summary["used_message_count"] == 2
    assert summary["message_count"] == 2
    assert [quote["role"] for quote in summary["key_quotes"]] == ["expert", "user"]
    assert "system" not in summary["generated_summary"].lower()
    assert summary["unresolved_questions"] == ["需要补充原始发布时间？"]


def test_latest_human_consultation_messages_filters_by_latest_session_and_deduplicates():
    sessions = [
        {"id": "old", "created_at": "2026-04-29T00:00:00+00:00"},
        {"id": "latest", "created_at": "2026-04-29T02:00:00+00:00"},
    ]
    messages = [
        {"id": "old-m", "session_id": "old", "role": "expert", "message": "旧会诊意见"},
        {"id": "new-m", "session_id": "latest", "role": "expert", "message": "最新专家意见"},
        {"id": "new-m", "session_id": "latest", "role": "expert", "message": "最新专家意见"},
        {"session_id": "latest", "role": "commander", "message": "主持人摘要", "message_type": "summary"},
    ]

    filtered = latest_human_consultation_messages(messages, sessions)

    assert filtered == [{"id": "new-m", "session_id": "latest", "role": "expert", "message": "最新专家意见"}]
