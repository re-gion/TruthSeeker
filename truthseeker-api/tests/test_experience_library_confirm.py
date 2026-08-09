"""Tests for confirm_experience_drafts resilience (per-draft isolation & idempotency)."""
from __future__ import annotations

from typing import Any

import pytest

from app.services.experience_library import confirm_experience_drafts

VALID_DRAFT: dict[str, Any] = {
    "title": "测试经验",
    "target_agents": ["forensics"],
    "problem_pattern": "问题模式描述",
    "recommended_method": "推荐方法描述",
    "evidence_to_check": [],
    "when_to_escalate": "",
    "limitations": "",
}


class _FakeResponse:
    def __init__(self, outcome: Any):
        self._outcome = outcome

    def execute(self):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return _FakeData(self._outcome)


class _FakeData:
    """Mimics supabase response object exposing .data (not a plain dict)."""

    def __init__(self, data: Any):
        self.data = data


class FakeTable:
    def __init__(self, client: "FakeClient", name: str):
        self._client = client
        self._name = name

    def insert(self, payload: dict) -> _FakeResponse:
        return _FakeResponse(self._client.on_insert(self._name, payload))

    def upsert(self, payload: dict, on_conflict: str | None = None) -> _FakeResponse:
        return _FakeResponse(self._client.on_upsert(self._name, payload, on_conflict))

    def select(self, *_args: Any) -> "FakeTable":
        return self

    def eq(self, *_args: Any) -> "FakeTable":
        return self

    def limit(self, *_args: Any) -> "FakeTable":
        return self

    def execute(self) -> dict:
        return {"data": []}


class FakeClient:
    """Supabase-like fake where tests configure insert/upsert behavior."""

    def __init__(self):
        # PostgREST 返回数据库生成的 id
        self.on_insert = lambda _name, payload: [{**payload, "id": "entry-fake"}]  # type: ignore[assignment]
        self.on_upsert = lambda _name, payload, on_conflict: [payload]  # type: ignore[assignment]

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)


async def _run(drafts: list[dict[str, Any]], client: FakeClient | None = None) -> dict[str, Any]:
    return await confirm_experience_drafts(
        client=client or FakeClient(),
        user_id="user-test",
        task_id="task-test",
        session_id="session-test",
        drafts=drafts,
    )


@pytest.mark.asyncio
async def test_confirm_single_insert_failure_does_not_abort_batch(monkeypatch):
    from app.services import experience_library

    monkeypatch.setattr(experience_library, "_existing_experiences", lambda client, user_id, agents: [])
    client = FakeClient()
    calls = []

    def failing_insert(name, payload):
        calls.append(payload)
        if len(calls) == 1:
            raise RuntimeError("boom: 23503 foreign key violation")
        return [{**payload, "id": "entry-fake"}]

    client.on_insert = failing_insert

    result = await _run([VALID_DRAFT, {**VALID_DRAFT, "title": "第二条经验"}], client)

    assert result["status"] == "partial"
    assert result["inserted"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["title"] == VALID_DRAFT["title"]
    assert "boom" in result["failed"][0]["error"]


@pytest.mark.asyncio
async def test_confirm_unique_violation_is_idempotent_skip(monkeypatch):
    from app.services import experience_library

    monkeypatch.setattr(experience_library, "_existing_experiences", lambda client, user_id, agents: [])

    class UniqueError(Exception):
        pass

    client = FakeClient()

    def unique_insert(name, payload):
        raise UniqueError("duplicate key value violates unique constraint \"idx_experience_entries_user_hash\" (23505)")

    client.on_insert = unique_insert

    result = await _run([VALID_DRAFT], client)

    assert result["status"] == "ok"
    assert result["inserted"] == 0
    assert result["failed"] == []


@pytest.mark.asyncio
async def test_confirm_chunk_index_failure_keeps_entry(monkeypatch):
    from app.services import experience_library

    monkeypatch.setattr(experience_library, "_existing_experiences", lambda client, user_id, agents: [])

    async def fake_embed(text):
        return {"status": "success", "embedding": [0.1] * 1024, "model": "test"}

    monkeypatch.setattr(experience_library, "embed_text", fake_embed)
    client = FakeClient()

    def failing_upsert(name, payload, on_conflict=None):
        if name == "experience_library_rag_chunks":
            raise RuntimeError("vector dimension mismatch")
        return [payload]

    client.on_upsert = failing_upsert

    result = await _run([VALID_DRAFT], client)

    assert result["status"] == "partial"
    assert result["inserted"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["indexing_failed"] is True


@pytest.mark.asyncio
async def test_confirm_all_success_returns_ok(monkeypatch):
    from app.services import experience_library

    monkeypatch.setattr(experience_library, "_existing_experiences", lambda client, user_id, agents: [])

    async def fake_embed(text):
        return {"status": "success", "embedding": [0.1] * 1024, "model": "test"}

    monkeypatch.setattr(experience_library, "embed_text", fake_embed)

    result = await _run([VALID_DRAFT, {**VALID_DRAFT, "title": "第二条经验"}])

    assert result["status"] == "ok"
    assert result["inserted"] == 2
    assert result["indexed_chunks"] == 2
    assert result["failed"] == []
