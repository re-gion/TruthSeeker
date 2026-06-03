import pytest

from app.agents.nodes import challenger as challenger_module


class _EmptyQuery:
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        class Response:
            data = []

        return Response()


class _EmptySupabase:
    def table(self, *_args, **_kwargs):
        return _EmptyQuery()


def _state(**overrides):
    state = {
        "task_id": "task-1",
        "user_id": "user-1",
        "input_files": {},
        "input_type": "image_text",
        "priority_focus": "balanced",
        "case_prompt": "核验诈骗样本",
        "evidence_files": [],
        "current_round": 3,
        "max_rounds": 5,
        "convergence_threshold": 0.08,
        "analysis_phase": "forensics",
        "phase_rounds": {"forensics": 3, "osint": 1, "commander": 1},
        "phase_quality_history": {"forensics": [0.44, 0.44], "osint": [], "commander": []},
        "phase_residual_risks": [],
        "forensics_result": {"confidence": 0.95, "tool_summary": {"total": 1, "failed": 0, "degraded": 0}},
        "osint_result": None,
        "challenger_feedback": None,
        "final_verdict": None,
        "provenance_graph": None,
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
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_resume_after_consultation_does_not_force_challenger_to_advance(monkeypatch):
    async def model_review(*_args, **_kwargs):
        return {
            "confidence": 0.44,
            "requires_more_evidence": True,
            "target_agent": "forensics",
            "issues": [{"type": "missing_source", "severity": "high", "agent": "forensics", "description": "仍需补证"}],
            "residual_risks": [],
            "markdown": "### 质询对象与本轮置信度\nforensics",
        }

    monkeypatch.setattr(challenger_module, "supabase", _EmptySupabase())
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(challenger_module, "challenger_model_review", model_review)
    monkeypatch.setattr(
        challenger_module,
        "evaluate_consultation_trigger",
        lambda *_args, **_kwargs: {
            "should_pause": True,
            "event_type": "consultation_required",
            "target_agent": "forensics",
            "reason": "forensics 连续 3 轮低置信高质询且置信度变化停滞",
        },
    )
    monkeypatch.setattr(
        challenger_module,
        "interrupt",
        lambda _payload: {
            "action": "resume_after_consultation",
            "expert_messages": [{"id": "m1", "role": "expert", "message": "仍需核验来源"}],
            "confirmed_consultation_summary": {"confirmed_summary": "专家认为仍需补证"},
        },
    )

    result = await challenger_module.challenger_node(_state())

    feedback = result["challenger_feedback"]
    assert feedback["requires_more_evidence"] is True
    assert feedback["next_phase"] == "forensics"
    assert result["phase_rounds"]["forensics"] == 4


@pytest.mark.asyncio
async def test_resume_payload_expert_messages_are_passed_to_model_context(monkeypatch):
    captured = {}

    async def model_review(*_args, **kwargs):
        captured["challenges"] = _args[2]
        return {
            "confidence": 0.91,
            "requires_more_evidence": False,
            "target_agent": "forensics",
            "issues": [],
            "residual_risks": [],
            "markdown": "### 质询对象与本轮置信度\nforensics",
        }

    monkeypatch.setattr(challenger_module, "supabase", _EmptySupabase())
    monkeypatch.setattr(challenger_module, "_fetch_consultation_sessions", lambda _task_id: [])
    monkeypatch.setattr(challenger_module, "record_audit_event", lambda **_kwargs: None)
    monkeypatch.setattr(challenger_module, "challenger_model_review", model_review)

    await challenger_module.challenger_node(_state(
        consultation_resume={
            "action": "resume_after_consultation",
            "expert_messages": [{"id": "m1", "role": "expert", "message": "URL 与国内公司不符"}],
            "confirmed_consultation_summary": {"confirmed_summary": "专家指出 URL 与公司地域不符"},
        },
    ))

    assert any(item.get("type") == "human_consultation" for item in captured["challenges"])
