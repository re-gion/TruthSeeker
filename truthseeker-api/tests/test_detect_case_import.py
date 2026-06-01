import json
from types import SimpleNamespace

import pytest


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.payload = None
        self.operation = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def execute(self):
        table = self.db.setdefault(self.table_name, [])
        if self.operation == "insert":
            row = {**self.payload, "id": self.payload.get("id") or f"{self.table_name}-{len(table) + 1}"}
            table.append(row)
            return SimpleNamespace(data=[row])
        rows = list(table)
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


async def _drain_queue(queue):
    items = []
    while not queue.empty():
        raw = await queue.get()
        assert raw.startswith("data: ")
        items.append(json.loads(raw.removeprefix("data: ").strip()))
    return items


@pytest.mark.asyncio
async def test_run_case_import_phase_emits_created_events(monkeypatch):
    from app.api.v1 import detect as detect_module

    db = {
        "reports": [
            {
                "id": "report-1",
                "task_id": "task-1",
                "verdict": "forged",
                "confidence_overall": 0.91,
                "verdict_payload": {},
            }
        ],
        "case_library_entries": [],
    }
    monkeypatch.setattr(detect_module, "supabase", FakeSupabase(db))
    monkeypatch.setattr(detect_module, "get_llm", lambda: None)
    async def fake_index_case_record(*args, **kwargs):
        return {"status": "skipped"}

    monkeypatch.setattr(detect_module, "index_case_record", fake_index_case_record)
    audit_events = []
    monkeypatch.setattr(detect_module, "record_audit_event", lambda **kwargs: audit_events.append(kwargs))

    queue = detect_module.asyncio.Queue()
    task = {
        "id": "task-1",
        "user_id": "user-1",
        "description": "公开案例",
        "metadata": {
            "share_to_casebase": True,
            "files": [{"name": "notice.jpg", "modality": "image", "sha256": "sha-1"}],
        },
    }

    await detect_module._run_case_import_phase(queue, "task-1", task, {"verdict": "forged"}, "user-1")

    events = await _drain_queue(queue)
    assert [event["type"] for event in events] == ["case_import_start", "case_import_created"]
    assert db["case_library_entries"][0]["task_id"] == "task-1"
    assert audit_events[0]["action"] == "case_import_created"


@pytest.mark.asyncio
async def test_run_case_import_phase_emits_skipped_when_not_requested(monkeypatch):
    from app.api.v1 import detect as detect_module

    queue = detect_module.asyncio.Queue()

    await detect_module._run_case_import_phase(queue, "task-2", {"metadata": {}}, {"verdict": "forged"}, "user-1")

    events = await _drain_queue(queue)
    assert events == [{"type": "case_import_skipped", "task_id": "task-2", "reason": "not_requested"}]
