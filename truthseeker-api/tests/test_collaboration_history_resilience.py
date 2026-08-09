import asyncio
import threading
from types import SimpleNamespace

import pytest


class FakeQuery:
    def __init__(self, table_name, db, failing_tables):
        self.table_name = table_name
        self.db = db
        self.failing_tables = failing_tables
        self.filters = {}

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _key, desc=False):
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.table_name in self.failing_tables:
            raise RuntimeError(f"temporary {self.table_name} read failure")
        rows = list(self.db.get(self.table_name, []))
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db, failing_tables=()):
        self.db = db
        self.failing_tables = set(failing_tables)

    def table(self, table_name):
        return FakeQuery(table_name, self.db, self.failing_tables)


class BlockingTaskQuery(FakeQuery):
    def __init__(self, table_name, db, release):
        super().__init__(table_name, db, ())
        self.release = release

    def execute(self):
        if self.table_name == "tasks":
            self.release.wait(timeout=0.2)
        return super().execute()


class BlockingTaskSupabase(FakeSupabase):
    def __init__(self, db, release):
        super().__init__(db)
        self.release = release

    def table(self, table_name):
        return BlockingTaskQuery(table_name, self.db, self.release)


@pytest.mark.asyncio
async def test_message_history_does_not_block_event_loop_while_database_is_slow(monkeypatch):
    from app.api.v1 import consultation

    release = threading.Event()
    db = {
        "tasks": [{"id": "task-1", "user_id": "user-1"}],
        "collaboration_sessions": [{
            "id": "session-1",
            "task_id": "task-1",
            "created_at": "2026-08-06T09:00:00+00:00",
        }],
        "collaboration_messages": [],
        "consultation_messages": [],
    }
    monkeypatch.setattr(consultation, "supabase", BlockingTaskSupabase(db, release))
    request = SimpleNamespace(
        state=SimpleNamespace(is_authenticated=True, user_id="user-1"),
    )
    asyncio.get_running_loop().call_later(0.02, release.set)

    result = await consultation.get_consultation_messages("task-1", request)

    assert result == {"messages": []}
    assert release.is_set(), "同步 Supabase 查询阻塞了 FastAPI 事件循环"


@pytest.mark.asyncio
async def test_agent_history_degrades_when_optional_audit_history_is_unavailable(monkeypatch):
    from app.api.v1 import consultation

    db = {
        "tasks": [{
            "id": "task-1",
            "user_id": "user-1",
            "title": "case",
            "status": "waiting_collaboration",
            "input_type": "image",
            "result": None,
            "metadata": {},
        }],
        "agent_logs": [{
            "id": "log-1",
            "task_id": "task-1",
            "agent": "challenger",
            "timestamp": "2026-08-06T09:00:00+00:00",
        }],
        "analysis_states": [],
        "reports": [],
        "collaboration_sessions": [],
        "consultation_sessions": [],
    }
    monkeypatch.setattr(
        consultation,
        "supabase",
        FakeSupabase(db, failing_tables={"audit_logs"}),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(is_authenticated=True, user_id="user-1"),
    )

    history = await consultation.get_agent_history("task-1", request)

    assert history["task"]["status"] == "waiting_collaboration"
    assert history["agent_logs"][0]["id"] == "log-1"
    assert history["audit_logs"] == []
    assert "audit_logs" in history["history_warnings"]


@pytest.mark.asyncio
async def test_close_runs_summary_and_experience_draft_generation_concurrently(monkeypatch):
    from app.api.v1 import consultation

    summary_started = asyncio.Event()
    experience_started = asyncio.Event()

    async def summarize(**_kwargs):
        summary_started.set()
        await asyncio.wait_for(experience_started.wait(), timeout=0.1)
        return {
            "generated_summary": "专家建议补充来源链路。",
            "human_message_count": 1,
        }

    async def build_drafts(**_kwargs):
        experience_started.set()
        await asyncio.wait_for(summary_started.wait(), timeout=0.1)
        return []

    session = {
        "id": "session-1",
        "status": "active",
        "context_payload": {"help_needed": ["核验来源链路"]},
    }
    monkeypatch.setattr(consultation, "_fetch_task_or_404", lambda *_args, **_kwargs: {"id": "task-1", "user_id": "user-1"})
    monkeypatch.setattr(consultation, "_fetch_session_or_404", lambda *_args, **_kwargs: session)
    monkeypatch.setattr(consultation, "_session_messages", lambda *_args, **_kwargs: [{
        "role": "expert",
        "message": "建议补充原始发布页和时间戳。",
    }])
    monkeypatch.setattr(consultation, "commander_summarize_consultation", summarize)
    monkeypatch.setattr(consultation, "build_experience_drafts", build_drafts)
    monkeypatch.setattr(consultation, "_update_session", lambda _session_id, payload: {**session, **payload})
    monkeypatch.setattr(consultation, "_insert_commander_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(consultation, "record_audit_event", lambda **_kwargs: None)
    request = SimpleNamespace(state=SimpleNamespace(is_authenticated=True, user_id="user-1"))

    response = await asyncio.wait_for(
        consultation.close_consultation_session("task-1", "session-1", request),
        timeout=0.2,
    )

    assert response["session"]["status"] == "summary_pending"
    assert summary_started.is_set()
    assert experience_started.is_set()


@pytest.mark.asyncio
async def test_close_accepts_slow_llm_results_instead_of_forcing_local_fallback(monkeypatch):
    from app.api.v1 import consultation

    async def slow_summary(**_kwargs):
        await asyncio.sleep(0.03)
        return {
            "generated_summary": "LLM 结合专家意见建议核验原始发布页与时间戳。",
            "summary_provider": "commander_llm",
            "human_message_count": 1,
        }

    async def build_drafts(**_kwargs):
        await asyncio.sleep(0.02)
        return [{"title": "核验来源链路"}]

    session = {
        "id": "session-1",
        "status": "active",
        "context_payload": {"help_needed": ["核验来源链路"]},
    }
    monkeypatch.setattr(consultation, "COLLABORATION_LLM_TIMEOUT_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(consultation, "_fetch_task_or_404", lambda *_args, **_kwargs: {"id": "task-1", "user_id": "user-1"})
    monkeypatch.setattr(consultation, "_fetch_session_or_404", lambda *_args, **_kwargs: session)
    monkeypatch.setattr(consultation, "_session_messages", lambda *_args, **_kwargs: [{
        "role": "expert",
        "message": "建议补充原始发布页和时间戳。",
    }])
    monkeypatch.setattr(consultation, "commander_summarize_consultation", slow_summary)
    monkeypatch.setattr(consultation, "build_experience_drafts", build_drafts)
    monkeypatch.setattr(consultation, "_update_session", lambda _session_id, payload: {**session, **payload})
    monkeypatch.setattr(consultation, "_insert_commander_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(consultation, "record_audit_event", lambda **_kwargs: None)
    request = SimpleNamespace(state=SimpleNamespace(is_authenticated=True, user_id="user-1"))

    response = await asyncio.wait_for(
        consultation.close_consultation_session("task-1", "session-1", request),
        timeout=0.2,
    )

    payload = response["session"]["summary_payload"]
    assert payload["generated_summary"] == "LLM 结合专家意见建议核验原始发布页与时间戳。"
    assert payload["summary_provider"] == "commander_llm"
    assert payload["experience_drafts"] == [{"title": "核验来源链路"}]
    assert payload.get("summary_degraded") is not True


@pytest.mark.asyncio
async def test_close_exposes_experience_contract_failure_when_no_drafts_survive(monkeypatch):
    from app.api.v1 import consultation

    async def summarize(**_kwargs):
        return {"generated_summary": "已汇总专家意见。", "human_message_count": 1}

    async def build_drafts(**kwargs):
        kwargs["skill_execution_sink"].update({
            "load_status": "loaded",
            "execution_status": "check_failed",
            "limitations": ["Skill 输出检查未通过：experience_distillation_contract"],
        })
        return []

    session = {"id": "session-1", "status": "active", "context_payload": {}}
    monkeypatch.setattr(consultation, "_fetch_task_or_404", lambda *_args, **_kwargs: {"id": "task-1", "user_id": "user-1"})
    monkeypatch.setattr(consultation, "_fetch_session_or_404", lambda *_args, **_kwargs: session)
    monkeypatch.setattr(consultation, "_session_messages", lambda *_args, **_kwargs: [{"role": "expert", "message": "核验来源"}])
    monkeypatch.setattr(consultation, "commander_summarize_consultation", summarize)
    monkeypatch.setattr(consultation, "build_experience_drafts", build_drafts)
    monkeypatch.setattr(consultation, "_update_session", lambda _session_id, payload: {**session, **payload})
    monkeypatch.setattr(consultation, "_insert_commander_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(consultation, "record_audit_event", lambda **_kwargs: None)
    request = SimpleNamespace(state=SimpleNamespace(is_authenticated=True, user_id="user-1"))

    response = await consultation.close_consultation_session("task-1", "session-1", request)

    payload = response["session"]["summary_payload"]
    assert payload["experience_drafts"] == []
    assert payload["experience_drafts_error"] == "个人经验草稿未通过输出检查，请重新发起协同或重试检测"
