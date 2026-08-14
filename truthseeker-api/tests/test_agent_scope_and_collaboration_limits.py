"""分工边界过滤、上游结论引用、协同次数与问题数量上限的聚焦测试。"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def _no_experience(**_kwargs):
    return {"tool": "experience_rag_search", "status": "success", "matches": [], "summary": "未命中个人经验库"}


async def _model_review_out_of_scope(*_args, **_kwargs):
    return {
        "markdown": "越界质询",
        "confidence": 0.85,
        "requires_more_evidence": True,
        "target_agent": "forensics",
        "issues": [
            {
                "type": "missing_whois",
                "description": "取证阶段未执行 WHOIS 与 DNS 查询，无法确认域名注册风险。",
                "severity": "high",
                "agent": "forensics",
            },
            {
                "type": "missing_ip_history",
                "description": "建议补充历史 IP 与公开情报搜索以完善溯源。",
                "severity": "medium",
                "agent": "forensics",
            },
        ],
        "residual_risks": [],
    }


def _base_state() -> dict:
    return {
        "task_id": "task-scope",
        "user_id": "user-1",
        "input_files": {},
        "input_type": "text",
        "priority_focus": "balanced",
        "case_prompt": "检查品牌钓鱼风险",
        "evidence_files": [],
        "current_round": 1,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "analysis_phase": "forensics",
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [], "osint": [], "commander": []},
        "phase_residual_risks": [],
        "forensics_result": {
            "confidence": 0.85,
            "tool_summary": {"total": 1, "success": 1, "failed": 0, "degraded": 0},
        },
        "osint_result": {},
        "challenger_feedback": {},
        "final_verdict": {},
        "provenance_graph": {},
        "agent_weights": {},
        "previous_weights": {},
        "evidence_board": [],
        "confidence_history": [],
        "challenges": [],
        "logs": [],
        "is_converged": False,
        "termination_reason": None,
        "degradation_status": {},
        "tool_results": {},
        "expert_messages": [],
        "consultation_resume": None,
        "consultation_sessions": [],
        "consultation_trigger_history": [],
        "active_consultation_session": None,
        "pending_consultation_approval": None,
        "confirmed_consultation_summary": None,
        "timeline_events": [],
    }


@pytest.mark.asyncio
async def test_challenger_filters_out_of_scope_provenance_issues_for_forensics(monkeypatch):
    """要求取证阶段做 WHOIS/DNS/情报溯源的质询点必须被确定性过滤。"""
    from app.agents.nodes import challenger as challenger_module

    monkeypatch.setattr(challenger_module, "challenger_model_review", _model_review_out_of_scope)
    monkeypatch.setattr(challenger_module, "experience_rag_search", _no_experience)
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])

    result = await challenger_module.challenger_node(_base_state())
    feedback = result["challenger_feedback"]

    assert feedback["issue_count"] == 0
    assert feedback["high_severity_count"] == 0
    # 越界问题全部被过滤后不应再要求补证
    assert feedback["requires_more_evidence"] is False
    assert feedback["next_phase"] == "osint"


def test_out_of_scope_filter_is_directional():
    from app.agents.nodes.challenger import _filter_out_of_scope_issues

    forensics_issues = [
        {"type": "a", "description": "未做 WHOIS 查询", "severity": "high"},
        {"type": "b", "description": "图片未进行像素级篡改分析", "severity": "medium"},
    ]
    kept, dropped = _filter_out_of_scope_issues(forensics_issues, "forensics")
    assert [issue["type"] for issue in kept] == ["b"]
    assert [issue["type"] for issue in dropped] == ["a"]

    osint_issues = [
        {"type": "a", "description": "未做 WHOIS 查询", "severity": "high"},
        {"type": "b", "description": "未进行像素级篡改分析与 OCR 字体渲染比对", "severity": "medium"},
    ]
    kept, dropped = _filter_out_of_scope_issues(osint_issues, "osint")
    assert [issue["type"] for issue in kept] == ["a"]
    assert [issue["type"] for issue in dropped] == ["b"]

    commander_issues = [{"type": "a", "description": "未做 WHOIS 查询", "severity": "high"}]
    kept, dropped = _filter_out_of_scope_issues(commander_issues, "commander")
    assert len(kept) == 1 and not dropped


def test_collaboration_limited_to_one_session_per_phase():
    from app.services.consultation_workflow import evaluate_consultation_trigger

    records = [
        {
            "round": round_number,
            "phase": "osint",
            "target_agent": "osint",
            "phase_round": round_number,
            "confidence": 0.6,
            "quality_delta": 0.01,
            "high_severity_count": 0,
            "issues": [{"severity": "medium", "description": "引用覆盖率不足"}],
        }
        for round_number in (1, 2, 3)
    ]

    first = evaluate_consultation_trigger(records, existing_sessions=[], max_rounds=5)
    assert first["should_pause"] is True

    completed_session = {"status": "summary_confirmed", "triggered_by_agent": "osint", "trigger_phase": "osint"}
    second = evaluate_consultation_trigger(records, existing_sessions=[completed_session], max_rounds=5)
    assert second["should_pause"] is False
    assert "上限" in second["reason"]


def test_collaboration_context_caps_questions_at_three():
    from app.services.consultation_workflow import build_consultation_context

    issues = [
        {
            "round": 3,
            "phase": "osint",
            "target_agent": "osint",
            "confidence": 0.6,
            "high_severity_count": 4,
            "issues": [
                {
                    "type": f"issue-{index}",
                    "description": f"质询问题 {index}",
                    "severity": "high" if index <= 4 else "medium",
                    "agent": "osint",
                }
                for index in range(1, 6)
            ],
        }
    ]
    trigger = {
        "reason": "osint 连续低置信",
        "target_agent": "osint",
        "recent_challenges": issues,
    }

    context = build_consultation_context(
        task_id="task-questions",
        case_prompt="测试",
        evidence_files=[],
        forensics_result=None,
        osint_result=None,
        challenger_feedback=None,
        trigger=trigger,
    )

    assert len(context["help_needed"]) == 3
    assert len(context["expert_tasks"]) == 3
    assert [task["id"] for task in context["expert_tasks"]] == [
        "expert-task-1",
        "expert-task-2",
        "expert-task-3",
    ]


def test_osint_upstream_verified_conclusions_extract_forensics_verdict():
    from app.agents.nodes.osint import _upstream_verified_conclusions

    state = {
        "forensics_result": {
            "aigc_probability": 0.99,
            "is_aigc": True,
            "confidence": 0.9,
            "model_used": "sightengine_genai",
            "degraded": False,
            "tool_results": [
                {
                    "tool": "aigc_image_detector",
                    "status": "success",
                    "summary": "Sightengine AI 生成概率 0.99",
                },
                {
                    "tool": "ai_text_detector",
                    "status": "success",
                    "summary": "内部文本检测: AI 生成概率 33.3%，置信度 84.0%",
                },
                {
                    "tool": "virustotal_file_hash",
                    "status": "success",
                    "summary": "VT 无恶意检出",
                },
            ],
        }
    }

    conclusions = _upstream_verified_conclusions(state)
    assert conclusions is not None
    assert conclusions["aigc_probability"] == pytest.approx(0.99)
    assert conclusions["is_aigc"] is True
    assert conclusions["forensics_confidence"] == pytest.approx(0.9)
    assert conclusions["media_detection_summaries"] == ["Sightengine AI 生成概率 0.99"]
    # 文本 AIGC 检测也是取证鉴伪结论，必须进入上游注入，否则 OSINT 复用后
    # 会把上游数字包装成独立推断（本次修复的根因之一）
    assert conclusions["text_detection_summaries"] == ["内部文本检测: AI 生成概率 33.3%，置信度 84.0%"]
    assert "直接引用" in conclusions["citation_rule"]

    assert _upstream_verified_conclusions({"forensics_result": {}}) is None
    assert _upstream_verified_conclusions({}) is None


def test_upstream_citation_markdown_covers_image_and_text_findings():
    from app.agents.nodes.osint import _upstream_citation_markdown

    conclusions = {
        "verified_by": "电子取证阶段结论，已通过逻辑质询 Agent 阶段审查",
        "aigc_probability": 0.99,
        "is_aigc": True,
        "forensics_confidence": 0.95,
        "media_detection_summaries": ["provider=sightengine, ai_generated_probability=0.99"],
        "text_detection_summaries": ["内部文本检测: AI 生成概率 33.3%，置信度 84.0%"],
    }

    block = _upstream_citation_markdown("task-123", conclusions)

    assert block.startswith("### 上游已核验结论引用")
    assert "task-123" in block
    assert "检出 AIGC 特征" in block
    assert "99.0%" in block
    assert "provider=sightengine" in block
    assert "内部文本检测" in block
    assert "确定性注入" in block

    non_aigc = _upstream_citation_markdown("task-124", {**conclusions, "is_aigc": False, "aigc_probability": 0.1})
    assert "未检出 AIGC 特征" in non_aigc


def test_osint_search_confidence_floors_valid_negative_at_release_threshold():
    from app.agents.nodes.osint import _osint_search_confidence

    # 有效负结果：搜索正常完成但零命中 → 保底放行线
    assert _osint_search_confidence("success", 0, has_virustotal=False) == pytest.approx(0.80)
    # 命中加分但不超过上限
    assert _osint_search_confidence("success", 3, has_virustotal=False) == pytest.approx(0.89)
    assert _osint_search_confidence("success", 10, has_virustotal=False) == pytest.approx(0.92)
    # 搜索失败且无 VT 佐证保持低置信
    assert _osint_search_confidence("failed", 0, has_virustotal=False) == pytest.approx(0.25)
    # 失败但有 VT 佐证、降级等沿用原基础分
    assert _osint_search_confidence("failed", 0, has_virustotal=True) == pytest.approx(0.62)
    assert _osint_search_confidence("degraded", 0, has_virustotal=False) == pytest.approx(0.62)


def test_find_reusable_exa_hit_skips_empty_results():
    from app.agents.nodes.osint import _find_reusable_exa_hit

    empty_success = {
        "tool": "exa_search",
        "status": "success",
        "result": {"status": "success", "results": [], "reason": "no_case_specific_matches"},
    }
    hit_success = {
        "tool": "exa_search",
        "status": "success",
        "result": {"status": "success", "results": [{"url": "https://x.example/a"}]},
    }

    # 第一轮不复用
    assert _find_reusable_exa_hit({("exa_search", "q"): hit_success}, 1) is None
    # 零命中的有效负结果不复用（否则重跑轮次不会真实重搜）
    assert _find_reusable_exa_hit({("exa_search", "q"): empty_success}, 2) is None
    # 已有命中的结果继续复用
    reused = _find_reusable_exa_hit({("exa_search", "q"): hit_success}, 2)
    assert reused is not None
    assert reused["reused"] is True
    assert reused["result"]["results"] == [{"url": "https://x.example/a"}]


def test_parse_entity_array_tolerates_wrapping_and_limits():
    from app.agents.tools.llm_client import _parse_entity_array

    assert _parse_entity_array('["星购生活", "某某App"]', max_entities=3) == ["星购生活", "某某App"]
    assert _parse_entity_array('实体如下：["甲牌", "乙牌"] 以上。', max_entities=3) == ["甲牌", "乙牌"]
    # 单字符实体搜索价值过低，被长度下限过滤
    assert _parse_entity_array('["A", "甲"]', max_entities=3) == []
    assert _parse_entity_array("[降级模式: LLM不可用] []", max_entities=3) == []
    assert _parse_entity_array("没有 JSON", max_entities=3) == []
    # 去重、长度过滤（>40 字符）与上限
    too_long = "超长品牌实体名称" * 6  # 48 字符，超过 MAX_SEARCH_ENTITY_CHARS=40
    assert len(too_long) > 40
    parsed = _parse_entity_array(
        json.dumps(["A", "品牌甲", "品牌甲", too_long, "品牌乙"], ensure_ascii=False),
        max_entities=2,
    )
    assert parsed == ["品牌甲", "品牌乙"]


def test_commander_recommendation_uses_cross_agent_validation_wording():
    from app.agents.nodes.commander import _generate_recommendations

    recommendations = _generate_recommendations("suspicious", {}, {}, {"issue_count": 0})
    assert any("跨 Agent 交叉验证" in item for item in recommendations)
    assert not any("不同检测工具交叉验证" in item for item in recommendations)


def test_agent_conclusion_table_injected_into_ruling():
    from app.agents.nodes.commander import _enforce_agent_conclusion_table

    report = (
        "### 最终裁决结论\n伪造\n\n"
        "### 置信度与证据链\n说明\n\n"
        "### Agent 结论与关键分歧\n"
        "| Agent | 结论 |\n|---|---|\n| 模型自写 | 旧表格 |\n"
        "两阶段结论存在分歧。\n\n"
        "### 后续建议与风险\n建议\n"
    )
    forensics = {"aigc_probability": 0.99, "is_aigc": True, "confidence": 0.9, "degraded": False}
    osint = {"threat_score": 0.82, "confidence": 0.7, "is_malicious": True, "is_suspicious": True, "degraded": False}
    challenger = {"issue_count": 2, "high_severity_count": 0, "confidence": 0.76}

    result = _enforce_agent_conclusion_table(report, forensics, osint, challenger)

    assert "| Agent | 核心结论 | 置信度 | 状态说明 |" in result
    assert "| 电子取证 Agent | AIGC 概率 99.0%，判定为AI 生成内容 | 90.0% | 正常 |" in result
    assert "| 情报溯源 Agent | 威胁评分 82.0%，判定为恶意/虚假内容 | 70.0% | 正常 |" in result
    assert "| 逻辑质询 Agent | 质询 2 个问题（高严重度 0 个），无阻断性分歧 | 76.0% | 正常收敛 |" in result
    # 模型自写的旧表格被移除，叙述保留
    assert "模型自写" not in result
    assert "两阶段结论存在分歧。" in result
