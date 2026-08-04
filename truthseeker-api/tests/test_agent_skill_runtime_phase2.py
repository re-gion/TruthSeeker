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
