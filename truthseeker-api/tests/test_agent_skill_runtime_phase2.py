from __future__ import annotations

import json

import pytest


OSINT_REPORT = (
    "### 自主情报推理\n内容\n### 外部情报结果解读\n内容\n"
    "### 来源可信度与图谱质量\n内容\n### 关联风险与复核建议\n内容"
)
CHALLENGER_REPORT = (
    "### 质询对象与本轮置信度\n内容\n### 主要质询点\n内容\n"
    "### 打回/放行建议\n内容\n### 收敛依据\n内容"
)
COMMANDER_REPORT = (
    "### 最终裁决结论\n可疑\n### 置信度与证据链\n内容\n"
    "### Agent 结论与关键分歧\n内容\n### 后续建议与风险\n内容"
)


@pytest.mark.asyncio
async def test_phase_two_agent_llm_entrypoints_inject_skill_and_expose_status(monkeypatch):
    from app.agents.tools import llm_client

    calls: list[dict] = []

    async def capture(**kwargs):
        calls.append(kwargs)
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        prompt = kwargs["system_prompt"]
        if "开源情报" in prompt:
            return OSINT_REPORT
        if "批判性思维挑战者" in prompt:
            return json.dumps({
                "confidence": 0.82,
                "requires_more_evidence": False,
                "target_agent": "osint",
                "issues": [],
                "residual_risks": [],
                "markdown": CHALLENGER_REPORT,
            }, ensure_ascii=False)
        return COMMANDER_REPORT

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    statuses = [{}, {}, {}]

    await llm_client.osint_interpret(
        {}, "text", "案件数据", [], skill_context="OSINT_SKILL", llm_status=statuses[0]
    )
    await llm_client.challenger_model_review(
        {}, {}, [], "案件数据", [],
        phase="osint",
        skill_context="CHALLENGER_SKILL",
        llm_status=statuses[1],
    )
    await llm_client.commander_ruling(
        {}, {}, {}, {}, "案件数据", [],
        confidence_context={},
        skill_context="COMMANDER_SKILL",
        llm_status=statuses[2],
    )

    assert len(calls) == 3
    for call, marker in zip(calls, ("OSINT_SKILL", "CHALLENGER_SKILL", "COMMANDER_SKILL")):
        human_text = call["human_text"]
        assert marker in human_text
        assert human_text.index("<core_skill") < human_text.index("<case_context>")
    assert statuses == [
        {"status": "success", "mode": "text"},
        {"status": "success", "mode": "text"},
        {"status": "success", "mode": "text"},
    ]


@pytest.mark.asyncio
async def test_challenger_local_contract_fallback_cannot_claim_skill_application(monkeypatch):
    from app.agents.tools import llm_client

    async def invalid_response(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return "模型返回的不是 JSON"

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", invalid_response)
    status: dict = {}
    result = await llm_client.challenger_model_review(
        {}, {}, [], phase="forensics", skill_context="核心方法", llm_status=status
    )

    assert result["markdown"].startswith("### 质询对象与本轮置信度")
    assert status["status"] == "degraded"
    assert status["mode"] == "local_contract_fallback"


@pytest.mark.asyncio
async def test_multimodal_llm_initialization_failure_silently_degrades(monkeypatch):
    from app.agents.tools import llm_client

    monkeypatch.setattr(
        llm_client,
        "resolve_kimi_runtime",
        lambda: (_ for _ in ()).throw(RuntimeError("bad config")),
    )
    status: dict = {}
    result = await llm_client._invoke_multimodal_llm(
        system_prompt="系统",
        human_text="<case_context>数据</case_context>",
        sample_refs=None,
        fallback_text="本地报告",
        status_sink=status,
    )

    assert result.startswith("[降级模式: LLM不可用")
    assert "本地报告" in result
    assert status == {"status": "degraded", "mode": "local_fallback"}


@pytest.mark.asyncio
async def test_commander_human_collaboration_workflow_records_applied_skill(monkeypatch):
    from app.agents.tools import llm_client

    audit: list[dict] = []
    async def capture(**kwargs):
        assert "human_collaboration" in kwargs["human_text"]
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "help_needed": ["核验来源"],
            "expert_tasks": [{
                "target_agent": "osint",
                "issue_type": "source_gap",
                "severity": "high",
                "question": "请核验来源",
                "requested_action": "补充来源",
                "expected_output": "给出引用",
            }],
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **kwargs: audit.append(kwargs))
    result = await llm_client.commander_dedupe_consultation_context(
        {
            "task_id": "task-human-skill",
            "help_needed": ["核验来源", "再次核验来源"],
            "expert_tasks": [],
            "trigger": {"target_agent": "osint"},
        }
    )

    execution = result["skill_execution"]
    assert execution["workflow"] == "human_collaboration"
    assert execution["execution_status"] == "applied"
    assert any(item["action"] == "skill.applied" and item["agent"] == "commander" for item in audit)


@pytest.mark.asyncio
async def test_commander_collaboration_degradation_does_not_claim_llm_available(monkeypatch):
    from app.agents.tools import llm_client

    async def degraded(**kwargs):
        kwargs["status_sink"].update({"status": "degraded", "mode": "local_fallback"})
        return "[降级模式: LLM不可用]\n" + json.dumps({
            "help_needed": ["核验来源"],
            "expert_tasks": [{
                "target_agent": "osint",
                "issue_type": "source_gap",
                "severity": "high",
                "question": "请核验来源",
                "requested_action": "补充来源",
                "expected_output": "给出引用",
            }],
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", degraded)
    result = await llm_client.commander_dedupe_consultation_context({
        "task_id": "task-human-degraded",
        "help_needed": ["核验来源", "再次核验来源"],
        "expert_tasks": [],
        "trigger": {"target_agent": "osint"},
    })

    assert result["help_needed_dedupe"]["provider"] == "generic_similarity_fallback"
    assert result["help_needed_dedupe"]["llm_available"] is False
    assert result["skill_execution"]["execution_status"] == "skipped"


@pytest.mark.asyncio
async def test_commander_summary_and_experience_workflows_expose_skill_execution(monkeypatch):
    from app.agents.tools import llm_client

    audit: list[dict] = []
    responses = iter([
        {
            "generated_summary": "专家建议复核来源。",
            "expert_answer_summary": "需要补证。",
            "recommended_actions": ["复核"],
            "unresolved_questions": [],
        },
        {"drafts": []},
    ])

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps(next(responses), ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **kwargs: audit.append(kwargs))
    summary = await llm_client.commander_summarize_consultation(
        messages=[{"role": "expert", "message": "建议复核来源"}],
        context_payload={"task_id": "task-summary-skill", "help_needed": ["来源"]},
        fallback_summary={"generated_summary": "兜底"},
    )
    experience_execution: dict = {}
    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "建议复核来源"}],
        context_payload={"task_id": "task-summary-skill"},
        summary_payload=summary,
        skill_execution_sink=experience_execution,
    )

    assert summary["skill_execution"]["workflow"] == "human_collaboration"
    assert summary["skill_execution"]["execution_status"] == "applied"
    assert drafts == []
    assert experience_execution["workflow"] == "experience_distillation"
    assert experience_execution["execution_status"] == "applied"
    assert sum(item["action"] == "skill.applied" for item in audit) == 2


@pytest.mark.asyncio
async def test_commander_summary_validates_the_normalized_runtime_payload(monkeypatch):
    """真实模型会把摘要字段输出成对象；运行时归一化后仍应满足 Skill 合同。"""
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "generated_summary": "专家建议补充来源核验。",
            "expert_answer_summary": {
                "来源核验": {
                    "expert_conclusion": "需要补证",
                    "judgment_basis": "当前只有单一来源",
                }
            },
            "recommended_actions": [
                {"action": "补充检索", "detail": "查询官方来源"},
            ],
            "unresolved_questions": [],
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)

    summary = await llm_client.commander_summarize_consultation(
        messages=[{"role": "expert", "message": "建议补充来源核验"}],
        context_payload={"task_id": "task-summary-normalized", "help_needed": ["来源"]},
        fallback_summary={"generated_summary": "兜底"},
    )

    assert summary["skill_execution"]["execution_status"] == "applied"
    assert isinstance(summary["expert_answer_summary"], str)
    assert summary["recommended_actions"] == ["补充检索：查询官方来源"]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"generated_summary": "只有摘要"},
    {
        "generated_summary": {"text": "不能强转"},
        "expert_answer_summary": "意见",
        "recommended_actions": [],
        "unresolved_questions": [],
    },
    {
        "generated_summary": "摘要",
        "expert_answer_summary": "意见",
        "recommended_actions": [{"unexpected": "不能静默 JSON 化"}],
        "unresolved_questions": [],
    },
])
async def test_commander_summary_does_not_hide_missing_or_unknown_contract_fields(monkeypatch, payload):
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)

    summary = await llm_client.commander_summarize_consultation(
        messages=[{"role": "expert", "message": "测试"}],
        context_payload={"task_id": "task-summary-invalid"},
        fallback_summary={"generated_summary": "兜底"},
    )

    assert summary["skill_execution"]["execution_status"] == "check_failed"


@pytest.mark.asyncio
async def test_commander_experience_validates_the_normalized_runtime_drafts(monkeypatch):
    """缺省检查项和夹带 commander 目标应按实际返回草稿归一化后再审计。"""
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "drafts": [{
                "title": "单工具边界",
                "target_agents": ["osint", "commander"],
                "problem_pattern": "单一工具零结果容易被误读。",
                "recommended_method": "显式记录工具边界。",
                "when_to_escalate": "发现替代工具时升级。",
                "limitations": "不能证明对象不存在。",
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "记录工具边界"}],
        context_payload={"task_id": "task-experience-normalized"},
        skill_execution_sink=execution,
    )

    assert execution["execution_status"] == "applied"
    assert drafts == [{
        "title": "单工具边界",
        "target_agents": ["osint"],
        "problem_pattern": "单一工具零结果容易被误读。",
        "recommended_method": "显式记录工具边界。",
        "evidence_to_check": [],
        "when_to_escalate": "发现替代工具时升级。",
        "limitations": "不能证明对象不存在。",
    }]


@pytest.mark.asyncio
async def test_commander_experience_does_not_hide_a_fully_invalid_draft(monkeypatch):
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "drafts": [{
                "title": "无效目标",
                "target_agents": ["commander"],
                "problem_pattern": "模式",
                "recommended_method": "方法",
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "测试"}],
        context_payload={"task_id": "task-experience-invalid"},
        skill_execution_sink=execution,
    )

    assert drafts == []
    assert execution["execution_status"] == "check_failed"


@pytest.mark.asyncio
async def test_commander_experience_does_not_stringify_invalid_required_text(monkeypatch):
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "drafts": [{
                "title": {"text": "对象标题"},
                "target_agents": ["osint"],
                "problem_pattern": "模式",
                "recommended_method": "方法",
                "evidence_to_check": [],
                "when_to_escalate": "升级条件",
                "limitations": "限制",
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "测试"}],
        context_payload={"task_id": "task-experience-invalid-text"},
        skill_execution_sink=execution,
    )

    assert drafts == []
    assert execution["execution_status"] == "check_failed"


@pytest.mark.asyncio
async def test_commander_experience_does_not_fill_missing_required_text(monkeypatch):
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "drafts": [{
                "title": "缺少必填字段",
                "target_agents": ["osint"],
                "problem_pattern": "模式",
                "recommended_method": "方法",
                "evidence_to_check": [],
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "测试"}],
        context_payload={"task_id": "task-experience-missing-text"},
        skill_execution_sink=execution,
    )

    assert drafts == []
    assert execution["execution_status"] == "check_failed"


@pytest.mark.asyncio
async def test_commander_experience_retries_once_after_repairable_contract_failure(monkeypatch):
    from app.agents.tools import llm_client

    calls = 0

    async def capture(**kwargs):
        nonlocal calls
        calls += 1
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        if calls == 1:
            return json.dumps({
                "drafts": [{
                    "title": "域名工具复核",
                    "target_agents": ["osint"],
                    "problem_pattern": "已执行的工具仍被列为待办。",
                    "recommended_method": "先核对工具执行状态。",
                    "evidence_to_check": [],
                }]
            }, ensure_ascii=False)
        assert "when_to_escalate" in kwargs["human_text"]
        assert "limitations" in kwargs["human_text"]
        return json.dumps({
            "drafts": [{
                "title": "域名工具复核",
                "target_agents": ["osint"],
                "problem_pattern": "已执行的工具仍被列为待办。",
                "recommended_method": "先核对工具执行状态。",
                "evidence_to_check": [],
                "when_to_escalate": "工具失败或部分可用时升级。",
                "limitations": "历史 DNS 不属于默认查询范围。",
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "先检查工具执行状态"}],
        context_payload={"task_id": "task-experience-retry"},
        skill_execution_sink=execution,
    )

    assert calls == 2
    assert len(drafts) == 1
    assert execution["execution_status"] == "applied"


@pytest.mark.asyncio
async def test_commander_experience_normalizes_string_evidence_checklist(monkeypatch):
    """非关键核验清单的常见字符串漂移不应让整批可编辑草稿归零。"""
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "drafts": [{
                "title": "可疑客服通知域名核验",
                "target_agents": ["osint"],
                "problem_pattern": "通知引导用户访问非官方域名。",
                "recommended_method": "核对注册域、品牌官方域和独立情报。",
                "evidence_to_check": "注册域；跳转链路；独立第三方情报",
                "when_to_escalate": "域名归属无法确认时升级。",
                "limitations": "不能仅凭话术定性。",
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "需要核验非官方域名"}],
        context_payload={"task_id": "task-experience-string-evidence"},
        skill_execution_sink=execution,
    )

    assert len(drafts) == 1
    assert drafts[0]["evidence_to_check"] == ["注册域", "跳转链路", "独立第三方情报"]
    assert execution["execution_status"] == "applied"


@pytest.mark.asyncio
async def test_commander_experience_normalizes_grouped_evidence_checklists(monkeypatch):
    """模型把核验项按必查/选查分组时，不应让整批草稿合同失败。"""
    from app.agents.tools import llm_client

    async def capture(**kwargs):
        kwargs["status_sink"].update({"status": "success", "mode": "text"})
        return json.dumps({
            "drafts": [
                {
                    "title": f"经验草稿 {index}",
                    "target_agents": ["osint"],
                    "problem_pattern": "核验清单被模型按类别分组。",
                    "recommended_method": "保留分组语义并转成可编辑清单。",
                    "evidence_to_check": {
                        "必查": ["注册域", "跳转链路"],
                        "选查": ["独立第三方情报"],
                    },
                    "when_to_escalate": "关键证据缺失时升级。",
                    "limitations": "分组名称不是证据本身。",
                }
                for index in range(3)
            ]
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "_invoke_multimodal_llm", capture)
    monkeypatch.setattr(llm_client, "record_audit_event", lambda **_kwargs: None)
    execution: dict = {}

    drafts = await llm_client.commander_extract_experience_drafts(
        messages=[{"role": "expert", "message": "三条经验均包含分组核验项"}],
        context_payload={"task_id": "task-experience-grouped-evidence"},
        skill_execution_sink=execution,
    )

    assert len(drafts) == 3
    assert all(
        draft["evidence_to_check"] == ["必查：注册域", "必查：跳转链路", "选查：独立第三方情报"]
        for draft in drafts
    )
    assert execution["execution_status"] == "applied"


def test_commander_confidence_section_removes_a_second_model_written_formula():
    """模型自带另一时点的分项公式时，最终报告只能保留确定性公式。"""
    from app.agents.nodes.commander import _enforce_deterministic_confidence_section

    report = (
        "### 最终裁决结论\n可疑\n\n"
        "### 置信度与证据链\n"
        "研判指挥 Agent 综合置信度：79.7%\n"
        "计算过程（由研判指挥 Agent 汇总）：\n"
        "- 电子取证 Agent：95.0% × 45.0% = 42.8%\n"
        "- 情报溯源 Agent：82.0% × 30.0% = 24.6%\n"
        "- 交叉质询 Agent：49.0% × 25.0% = 12.3%\n"
        "- 合计：42.8% + 24.6% + 12.3% = 79.7%\n\n"
        "- 证据链仍有一项来源待确认。\n\n"
        "### Agent 结论与关键分歧\n内容"
    )

    result = _enforce_deterministic_confidence_section(
        report,
        0.784,
        {
            "forensics": {"confidence": 0.95, "weight": 0.45, "weighted": 0.4275},
            "osint": {"confidence": 0.82, "weight": 0.30, "weighted": 0.246},
            "challenger": {"confidence": 0.44, "weight": 0.25, "weighted": 0.11},
        },
    )

    assert result.count("计算过程（由研判指挥 Agent 汇总）：") == 1
    assert "研判指挥 Agent 综合置信度：78.4%" in result
    assert "交叉质询 Agent：44.0% × 25.0% = 11.0%" in result
    assert "79.7%" not in result
    assert "49.0% × 25.0%" not in result
    assert "证据链仍有一项来源待确认" in result


@pytest.mark.asyncio
async def test_commander_removes_redundant_whois_action_after_success(monkeypatch):
    from app.agents.nodes import commander

    async def ruling(*_args, expected_verdict_cn="", llm_status=None, **_kwargs):
        llm_status.update({"status": "success", "mode": "text"})
        return (
            f"### 最终裁决结论\n{expected_verdict_cn}\n"
            "### 置信度与证据链\n内容\n"
            "### Agent 结论与关键分歧\n内容\n"
            "### 后续建议与风险\n"
            "- OSINT 扩展：对 moroba.com.br 域名执行 WHOIS 查询、历史 IP 追踪、"
            "内容快照取证，检索该域名是否关联其他已知钓鱼活动。"
        )

    monkeypatch.setattr(commander, "commander_ruling", ruling)
    monkeypatch.setattr(commander, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(commander, "build_provenance_graph", lambda **_kwargs: {
        "nodes": [], "edges": [], "citations": [], "quality": {}
    })
    state = _base_state("commander-whois-complete")
    state["osint_result"]["domain_provenance_summary"] = [{
        "domain": "moroba.com.br",
        "status": "success",
        "whois": {"registrar": "Example Registrar"},
        "dns_lookup": [{"type": "A", "value": "198.51.100.7"}],
        "ip_geolocation": [{"ip": "198.51.100.7", "country": "BR"}],
        "dns_history": [],
    }]

    result = await commander.commander_node(state)
    ruling_text = result["final_verdict"]["llm_ruling"]

    assert "执行 WHOIS 查询" not in ruling_text
    assert "WHOIS 已完成" in ruling_text
    assert "历史 IP 追踪未在默认查询范围内" in ruling_text
    assert "内容快照取证" in ruling_text
    assert "已知钓鱼活动" in ruling_text


@pytest.mark.asyncio
async def test_osint_node_persists_skill_execution_in_result_logs_audit_and_degradation(monkeypatch):
    from app.agents.nodes import osint

    audit: list[dict] = []

    async def search(_queries):
        return {"tool": "exa_search", "status": "success", "results": [], "degraded": False}

    async def rag(**_kwargs):
        return {"tool": "case_rag_search", "status": "success", "matches": [], "degraded": False, "summary": "无"}

    async def experience(**_kwargs):
        return {"tool": "experience_rag_search", "status": "success", "matches": [], "degraded": False, "summary": "无"}

    async def interpret(*_args, skill_context="", llm_status=None, **_kwargs):
        assert "osint-provenance" in skill_context
        llm_status.update({"status": "success", "mode": "text"})
        return OSINT_REPORT

    monkeypatch.setattr(osint, "search_osint", search)
    monkeypatch.setattr(osint, "case_rag_search", rag)
    monkeypatch.setattr(osint, "experience_rag_search", experience)
    monkeypatch.setattr(osint, "osint_interpret", interpret)
    monkeypatch.setattr(osint, "record_audit_event", lambda **kwargs: audit.append(kwargs))
    monkeypatch.setattr(osint, "build_provenance_graph", lambda **_kwargs: {
        "nodes": [], "edges": [], "citations": [], "quality": {}
    })

    result = await osint.osint_node(_base_state("osint"))
    execution = result["osint_result"]["skill_execution"]

    assert execution["execution_status"] == "applied"
    assert result["degradation_status"]["skill.osint"] == "applied"
    assert any("核心 Skill 已应用" in item["content"] for item in result["logs"])
    assert any(item["action"] == "skill.applied" for item in audit)


@pytest.mark.asyncio
async def test_challenger_node_persists_phase_review_skill_execution(monkeypatch):
    from app.agents.nodes import challenger

    audit: list[dict] = []

    async def model_review(*_args, skill_context="", llm_status=None, **_kwargs):
        assert "evidence-challenge" in skill_context
        llm_status.update({"status": "success", "mode": "text"})
        return {
            "markdown": CHALLENGER_REPORT,
            "confidence": 0.9,
            "requires_more_evidence": False,
            "target_agent": "forensics",
            "issues": [],
            "residual_risks": [],
        }

    async def no_experience(**_kwargs):
        return {"tool": "experience_rag_search", "status": "success", "matches": [], "degraded": False}

    monkeypatch.setattr(challenger, "challenger_model_review", model_review)
    monkeypatch.setattr(challenger, "experience_rag_search", no_experience)
    monkeypatch.setattr(challenger, "record_audit_event", lambda **kwargs: audit.append(kwargs))
    monkeypatch.setattr(challenger, "_fetch_consultation_sessions", lambda _task_id: [])
    monkeypatch.setattr(challenger, "_fetch_collaboration_messages", lambda _task_id: [])

    result = await challenger.challenger_node(_base_state("forensics"))
    execution = result["challenger_feedback"]["skill_execution"]

    assert execution["execution_status"] == "applied"
    assert result["degradation_status"]["skill.challenger"] == "applied"
    assert any("核心 Skill 已应用" in item["content"] for item in result["logs"])
    assert any(item["action"] == "skill.applied" for item in audit)


@pytest.mark.asyncio
async def test_commander_node_persists_final_adjudication_skill_execution(monkeypatch):
    from app.agents.nodes import commander

    audit: list[dict] = []

    async def ruling(*_args, skill_context="", llm_status=None, **_kwargs):
        assert "final_adjudication" in skill_context
        llm_status.update({"status": "success", "mode": "text"})
        return COMMANDER_REPORT.replace("可疑", "真实", 1)

    monkeypatch.setattr(commander, "commander_ruling", ruling)
    monkeypatch.setattr(commander, "record_audit_event", lambda **kwargs: audit.append(kwargs))
    monkeypatch.setattr(commander, "build_provenance_graph", lambda **_kwargs: {
        "nodes": [], "edges": [], "citations": [], "quality": {}
    })

    result = await commander.commander_node(_base_state("commander"))
    execution = result["final_verdict"]["skill_execution"]

    assert execution["execution_status"] == "applied"
    assert result["degradation_status"]["skill.commander"] == "applied"
    assert any("核心 Skill 已应用" in item["content"] for item in result["logs"])
    assert any(item["action"] == "skill.applied" for item in audit)


@pytest.mark.asyncio
async def test_commander_node_enforces_the_deterministic_verdict_in_llm_report(monkeypatch):
    """LLM 不得用自然语言结论覆盖 Python 已计算的四分类裁决。"""
    from app.agents.nodes import commander

    async def ruling(*_args, expected_verdict_cn="", llm_status=None, **_kwargs):
        assert expected_verdict_cn == "真实"
        llm_status.update({"status": "success", "mode": "text"})
        return (
            "最终裁决为伪造。\n"
            + COMMANDER_REPORT.replace("可疑", "伪造", 1)
            + "\n补充说明：最终判定是伪造。"
        )

    monkeypatch.setattr(commander, "commander_ruling", ruling)
    monkeypatch.setattr(commander, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(commander, "build_provenance_graph", lambda **_kwargs: {
        "nodes": [], "edges": [], "citations": [], "quality": {}
    })

    result = await commander.commander_node(_base_state("commander-verdict-guard"))

    assert result["final_verdict"]["verdict_cn"] == "真实"
    assert "### 最终裁决结论\n真实" in result["final_verdict"]["llm_ruling"]
    assert not result["final_verdict"]["llm_ruling"].startswith("最终裁决为伪造")
    assert "最终判定是伪造" not in result["final_verdict"]["llm_ruling"]
    assert result["final_verdict"]["skill_execution"]["execution_status"] == "applied"


@pytest.mark.asyncio
async def test_commander_node_uses_one_deterministic_overall_confidence_with_formula(monkeypatch):
    from app.agents.nodes import commander

    async def ruling(*_args, expected_verdict_cn="", llm_status=None, **_kwargs):
        llm_status.update({"status": "success", "mode": "text"})
        return (
            f"### 最终裁决结论\n{expected_verdict_cn}\n\n"
            "### 置信度与证据链\n"
            "**综合置信度：0.95**（引用自结构化 `final_verdict.confidence_overall` / "
            "取证分析 `forensics_score`）\n"
            "- 证据A可信\n"
            "- 证据B存在限制\n\n"
            "| 证据维度 | 关键发现 | 权重贡献 |\n"
            "|---|---|---|\n"
            "| 图像AIGC检测 | 概率 0.99 | 核心权重 |\n\n"
            "### Agent 结论与关键分歧\n内容\n\n"
            "### 后续建议与风险\n内容"
        )

    monkeypatch.setattr(commander, "commander_ruling", ruling)
    monkeypatch.setattr(commander, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(commander, "build_provenance_graph", lambda **_kwargs: {
        "nodes": [], "edges": [], "citations": [], "quality": {}
    })
    state = _base_state("commander-confidence-guard")
    state["forensics_result"]["confidence"] = 0.95
    state["osint_result"]["confidence"] = 0.82
    state["challenger_feedback"]["confidence"] = 0.44

    result = await commander.commander_node(state)
    final = result["final_verdict"]
    ruling_text = final["llm_ruling"]
    confidence_section = ruling_text.split("### 置信度与证据链", 1)[-1].split(
        "### Agent 结论与关键分歧", 1
    )[0]

    assert final["confidence_overall"] == 0.784
    assert "研判指挥 Agent 综合置信度：78.4%" in ruling_text
    assert "电子取证 Agent：95.0% × 45.0% = 42.8%" in ruling_text
    assert "情报溯源 Agent：82.0% × 30.0% = 24.6%" in ruling_text
    assert "交叉质询 Agent：44.0% × 25.0% = 11.0%" in ruling_text
    assert "合计：42.8% + 24.6% + 11.0% = 78.4%" in ruling_text
    assert "证据A可信" in confidence_section
    assert "证据B存在限制" in confidence_section
    assert "综合置信度：0.95" not in ruling_text
    assert "forensics_score" not in confidence_section
    assert final["skill_execution"]["execution_status"] == "applied"


@pytest.mark.asyncio
async def test_commander_node_uses_explicit_llm_status_for_degradation_log(monkeypatch):
    from app.agents.nodes import commander

    async def degraded_ruling(*_args, llm_status=None, **_kwargs):
        llm_status.update({"status": "degraded", "mode": "local_fallback"})
        return "[降级模式: LLM不可用] " + COMMANDER_REPORT

    monkeypatch.setattr(commander, "commander_ruling", degraded_ruling)
    monkeypatch.setattr(commander, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(commander, "build_provenance_graph", lambda **_kwargs: {
        "nodes": [], "edges": [], "citations": [], "quality": {}
    })

    result = await commander.commander_node(_base_state("commander"))
    contents = [item["content"] for item in result["logs"]]

    assert result["final_verdict"]["skill_execution"]["execution_status"] == "skipped"
    assert "### 最终裁决结论\n真实" in result["final_verdict"]["llm_ruling"]
    assert any("LLM 裁决不可用" in content for content in contents)
    assert not any("LLM 裁决报告生成完成" in content for content in contents)


def _base_state(phase: str) -> dict:
    return {
        "task_id": f"task-{phase}-skill",
        "user_id": "user-skill",
        "input_files": {},
        "input_type": "text",
        "priority_focus": "balanced",
        "case_prompt": "",
        "evidence_files": [],
        "current_round": 1,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "analysis_phase": phase,
        "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [], "osint": [], "commander": []},
        "phase_residual_risks": [],
        "forensics_result": {"confidence": 0.9, "tool_summary": {"total": 0, "success": 0, "failed": 0, "degraded": 0}},
        "osint_result": {"confidence": 0.9, "threat_score": 0.1, "tool_summary": {"total": 0, "success": 0, "failed": 0, "degraded": 0}},
        "challenger_feedback": {"confidence": 0.9, "quality_score": 0.9, "issues_found": []},
        "final_verdict": {},
        "provenance_graph": {"nodes": [], "edges": [], "citations": [], "quality": {}},
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
async def test_experience_service_propagates_commander_skill_execution(monkeypatch):
    from app.services import experience_library

    expected = {
        "skill_name": "command-collaboration",
        "workflow": "experience_distillation",
        "load_status": "loaded",
        "execution_status": "applied",
    }

    async def extract(*, skill_execution_sink=None, **_kwargs):
        skill_execution_sink.update(expected)
        return []

    monkeypatch.setattr(experience_library, "commander_extract_experience_drafts", extract)
    sink: dict = {}
    drafts = await experience_library.build_experience_drafts(
        client=object(),
        user_id="user-skill",
        task_id="task-skill",
        session_id="session-skill",
        messages=[{"role": "expert", "message": "建议"}],
        skill_execution_sink=sink,
    )

    assert drafts == []
    assert sink == expected


def test_confirmed_summary_merge_preserves_commander_metadata():
    from app.api.v1 import consultation

    previous = {
        "generated_summary": "模型摘要",
        "expert_answer_summary": "专家依据",
        "recommended_actions": ["补证"],
        "unresolved_questions": ["来源是谁"],
        "help_needed": ["核验来源"],
        "summary_provider": "commander_llm",
        "skill_execution": {"execution_status": "applied"},
        "experience_drafts": [],
        "experience_skill_execution": {"execution_status": "applied"},
    }
    confirmed = {
        "generated_summary": "用户确认内容",
        "confirmed_summary": "用户确认内容",
        "unresolved_questions": ["机械重算的问题"],
    }

    merged = consultation._merge_confirmed_summary_payload(confirmed, previous)

    assert merged["confirmed_summary"] == "用户确认内容"
    assert merged["expert_answer_summary"] == "专家依据"
    assert merged["recommended_actions"] == ["补证"]
    assert merged["unresolved_questions"] == ["来源是谁"]
    assert merged["help_needed"] == ["核验来源"]
    assert merged["summary_provider"] == "commander_llm"
    assert merged["skill_execution"]["execution_status"] == "applied"
    assert merged["experience_skill_execution"]["execution_status"] == "applied"
