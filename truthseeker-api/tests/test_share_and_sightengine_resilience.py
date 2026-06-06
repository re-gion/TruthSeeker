import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.payload = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None and self.table_name == "reports" and "share_token" in self.payload:
            if "task_id" in self.payload:
                raise RuntimeError("duplicate key value violates unique constraint")
            for row in self.db.setdefault("reports", []):
                if all(row.get(key) == value for key, value in self.filters.items()):
                    row.update(self.payload)
                    return SimpleNamespace(data=[row])
        rows = list(self.db.setdefault(self.table_name, []))
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


def test_share_creation_recovers_when_report_is_inserted_concurrently(monkeypatch):
    from app.api.v1 import share as share_module

    db = {
        "tasks": [{"id": "task-1", "status": "completed", "result": {"verdict": "forged"}}],
        "reports": [{"id": "report-1", "task_id": "task-1", "share_token": None, "report_hash": "hash-1"}],
    }
    monkeypatch.setattr(share_module, "supabase", FakeSupabase(db))
    monkeypatch.setattr(
        share_module,
        "build_report_row",
        lambda task_id, task_result, existing_share_token=None: {
            "task_id": task_id,
            "share_token": existing_share_token,
            "report_hash": "new-hash",
        },
    )

    report = share_module._create_report_from_completed_task("task-1", "token-1")

    assert report["id"] == "report-1"
    assert report["share_token"] == "token-1"
    assert db["reports"][0]["share_token"] == "token-1"


@pytest.mark.asyncio
async def test_sightengine_retries_transient_connect_errors(monkeypatch):
    from app.agents.tools import deepfake_api

    attempts = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "type": {"ai_generated": 0.72}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            attempts.append((args, kwargs))
            if len(attempts) < 3:
                raise httpx.ConnectError("temporary network failure")
            return FakeResponse()

    async def no_sleep(_delay):
        return None

    async def fake_download(_file_url):
        return b"image-bytes", "case.jpg"

    monkeypatch.setattr(deepfake_api, "_get_sightengine_credentials", lambda: ("user", "secret"))
    monkeypatch.setattr(deepfake_api, "_download_file", fake_download)
    monkeypatch.setattr(deepfake_api.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(deepfake_api.asyncio, "sleep", no_sleep)

    result = await deepfake_api.analyze_with_sightengine("signed-url")

    assert len(attempts) == 3
    assert result["provider"] == "sightengine"
    assert result["analysis_available"] is True
