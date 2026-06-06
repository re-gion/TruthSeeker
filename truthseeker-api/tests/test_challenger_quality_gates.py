import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def _no_experience(**_kwargs):
    return {"tool": "experience_rag_search", "status": "success", "matches": [], "summary": "未命中个人经验库"}


async def _model_review(*_args, **_kwargs):
    return {
        "markdown": "低置信质询",
        "confidence": 0.57,
        "requires_more_evidence": False,
        "target_agent": "forensics",
        "issues": [
            {
                "type": "citation_gap",
                "description": "引用覆盖不足，需要补强直接证据。",
                "severity": "medium",
                "agent": "forensics",
            }
        ],
        "residual_risks": [],
    }


def _base_state(phase_round: int) -> dict:
    return {
        "task_id": "task-challenger",
        "user_id": "user-1",
        "input_files": {},
        "input_type": "text",
        "priority_focus": "balanced",
        "case_prompt": "检查品牌钓鱼风险",
        "evidence_files": [],
        "current_round": phase_round,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "analysis_phase": "forensics",
        "phase_rounds": {"forensics": phase_round, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [0.59] * max(0, phase_round - 1), "osint": [], "commander": []},
        "phase_residual_risks": [],
        "forensics_result": {
            "confidence": 0.57,
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
async def test_low_confidence_before_round_five_always_returns_target_agent(monkeypatch):
    from app.agents.nodes import challenger as challenger_module

    monkeypatch.setattr(challenger_module, "challenger_model_review", _model_review)
    monkeypatch.setattr(challenger_module, "experience_rag_search", _no_experience)
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])

    result = await challenger_module.challenger_node(_base_state(1))
    feedback = result["challenger_feedback"]

    assert feedback["confidence"] == pytest.approx(0.57)
    assert feedback["requires_more_evidence"] is True
    assert feedback["target_agent"] == "forensics"
    assert feedback["next_phase"] == "forensics"
    assert feedback["max_rounds_release"] is False


@pytest.mark.asyncio
async def test_round_five_low_confidence_releases_with_residual_risk(monkeypatch):
    from app.agents.nodes import challenger as challenger_module

    monkeypatch.setattr(challenger_module, "challenger_model_review", _model_review)
    monkeypatch.setattr(challenger_module, "experience_rag_search", _no_experience)
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])

    result = await challenger_module.challenger_node(_base_state(5))
    feedback = result["challenger_feedback"]

    assert feedback["confidence"] == pytest.approx(0.57)
    assert feedback["requires_more_evidence"] is False
    assert feedback["target_agent"] is None
    assert feedback["next_phase"] == "osint"
    assert feedback["max_rounds_release"] is True
    assert feedback["residual_risks"]
    assert "轮次上限" in feedback["residual_risks"][0]["reason"]


def test_collaboration_trigger_uses_low_confidence_stagnation_without_high_issue_requirement():
    from app.services.consultation_workflow import evaluate_consultation_trigger

    records = [
        {
            "round": 1,
            "phase": "osint",
            "target_agent": "osint",
            "phase_round": 1,
            "confidence": 0.65,
            "quality_delta": None,
            "high_severity_count": 0,
            "issues": [{"severity": "medium", "description": "引用覆盖率不足"}],
        },
        {
            "round": 2,
            "phase": "osint",
            "target_agent": "osint",
            "phase_round": 2,
            "confidence": 0.62,
            "quality_delta": 0.03,
            "high_severity_count": 0,
            "issues": [{"severity": "medium", "description": "引用覆盖率不足"}],
        },
        {
            "round": 3,
            "phase": "osint",
            "target_agent": "osint",
            "phase_round": 3,
            "confidence": 0.60,
            "quality_delta": 0.02,
            "high_severity_count": 0,
            "issues": [{"severity": "medium", "description": "引用覆盖率不足"}],
        },
    ]

    trigger = evaluate_consultation_trigger(records, existing_sessions=[], max_rounds=5)

    assert trigger["should_pause"] is True
    assert trigger["event_type"] == "collaboration_required"
    assert "低置信" in trigger["reason"]
