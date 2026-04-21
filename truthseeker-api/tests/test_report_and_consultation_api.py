from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}
        self.payload = None
        self.order_by = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def gt(self, key, value):
        self.filters[key] = ("gt", value)
        return self

    def order(self, key, desc=False):
        self.order_by = (key, desc)
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self.payload = payload
        return self

    def execute(self):
        table = self.db.setdefault(self.table_name, [])

        if self.payload is not None and self.table_name == "consultation_invites":
            table.append(self.payload)
            return SimpleNamespace(data=[self.payload])

        if self.payload is not None and self.table_name == "reports":
            for row in table:
                if all(row.get(k) == v for k, v in self.filters.items()):
                    row.update(self.payload)
                    return SimpleNamespace(data=[row])
            table.append(self.payload)
            return SimpleNamespace(data=[self.payload])

        rows = table
        for key, value in self.filters.items():
            if isinstance(value, tuple) and value[0] == "gt":
                rows = [row for row in rows if row.get(key, "") > value[1]]
            else:
                rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


def test_create_share_link_reuses_existing_token(monkeypatch):
    from app.api.v1 import share as share_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)

    db = {
        "reports": [{"id": "report-1", "task_id": "task-1", "share_token": "existing-token"}],
    }
    monkeypatch.setattr(share_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.post("/api/v1/share/task-1")

    assert response.status_code == 200
    assert response.json()["share_token"] == "existing-token"
    assert response.json()["share_url"].endswith("/report/existing-token")


def test_create_consultation_invite_returns_tokenized_url(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)

    db = {
        "tasks": [{"id": "task-9", "status": "analyzing"}],
        "consultation_invites": [],
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.post("/api/v1/consultation/task-9/invite")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-9"
    assert body["invite_url"].startswith("/detect/task-9?")
    assert "invite_token=" in body["invite_url"]
    assert db["consultation_invites"][0]["task_id"] == "task-9"
    assert not db["consultation_invites"][0]["expires_at"].startswith("2999-")


def test_validate_consultation_invite_returns_task_and_role(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    db = {
        "consultation_invites": [
            {
                "task_id": "task-10",
                "token": "invite-token",
                "status": "pending",
                "expires_at": "2999-01-01T00:00:00+00:00",
            }
        ]
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.get("/api/v1/consultation/invite/invite-token")

    assert response.status_code == 200
    assert response.json()["task_id"] == "task-10"
    assert response.json()["role"] == "expert"


def test_validate_expired_consultation_invite_returns_410(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    db = {
        "consultation_invites": [
            {
                "task_id": "task-10",
                "token": "expired-token",
                "status": "pending",
                "expires_at": "2000-01-01T00:00:00+00:00",
            }
        ]
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.get("/api/v1/consultation/invite/expired-token")

    assert response.status_code == 410


def test_create_share_link_rejects_cross_user_task(monkeypatch):
    from app.api.v1 import share as share_module

    db = {
        "tasks": [{"id": "task-1", "user_id": "owner-user"}],
    }
    monkeypatch.setattr(share_module, "supabase", FakeSupabase(db))
    request = SimpleNamespace(state=SimpleNamespace(user_id="other-user"))

    with pytest.raises(HTTPException) as exc_info:
        share_module._assert_task_owner("task-1", request)

    assert exc_info.value.status_code == 403


def test_download_pdf_returns_error_when_generation_unavailable(monkeypatch):
    from app.api.v1 import report as report_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)
    monkeypatch.setattr(report_module, "_assert_task_owner", lambda task_id, request: None)

    async def fake_generate_pdf_report(_task_id):
        raise RuntimeError("PDF generation unavailable")

    monkeypatch.setattr(report_module, "generate_pdf_report", fake_generate_pdf_report)

    client = TestClient(app)
    response = client.get("/api/v1/report/task-11/pdf")

    assert response.status_code == 500
    assert response.json()["detail"] == "报告生成失败"
