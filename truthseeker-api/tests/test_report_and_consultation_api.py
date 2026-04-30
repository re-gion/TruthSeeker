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
        self.operation = None

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
        self.operation = "insert"
        return self

    def update(self, payload):
        self.payload = payload
        self.operation = "update"
        return self

    def upsert(self, payload, **_kwargs):
        self.payload = payload
        self.operation = "upsert"
        return self

    def execute(self):
        table = self.db.setdefault(self.table_name, [])

        if self.payload is not None and self.operation == "insert":
            table.append(self.payload)
            return SimpleNamespace(data=[self.payload])

        if self.payload is not None and self.operation in ("update", "upsert"):
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
        if self.order_by:
            key, desc = self.order_by
            rows = sorted(rows, key=lambda row: row.get(key) or "", reverse=desc)
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


def test_create_share_link_builds_report_from_completed_task_when_missing(monkeypatch):
    from app.api.v1 import share as share_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)

    db = {
        "tasks": [
            {
                "id": "task-1",
                "status": "completed",
                "result": {
                    "verdict": "suspicious",
                    "confidence": 0.72,
                    "analysis_summary": "已完成研判",
                    "key_evidence": ["取证命中"],
                    "recommendations": ["人工复核"],
                },
            }
        ],
        "reports": [],
    }
    monkeypatch.setattr(share_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.post("/api/v1/share/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["share_token"]
    assert body["share_url"].endswith(f"/report/{body['share_token']}")
    assert db["reports"][0]["task_id"] == "task-1"
    assert db["reports"][0]["share_token"] == body["share_token"]
    assert db["reports"][0]["report_hash"]


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


def test_used_consultation_invite_can_still_read_messages(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    db = {
        "consultation_invites": [
            {
                "id": "invite-1",
                "task_id": "task-10",
                "token": "used-token",
                "status": "used",
                "expires_at": "2999-01-01T00:00:00+00:00",
            }
        ],
        "consultation_messages": [
            {
                "task_id": "task-10",
                "role": "expert",
                "message": "建议人工复核",
                "expert_name": "expert",
                "created_at": "2026-04-21T00:00:00+00:00",
            }
        ],
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.get("/api/v1/consultation/task-10/messages?invite_token=used-token")

    assert response.status_code == 200
    assert response.json()["messages"][0]["message"] == "建议人工复核"


def test_consultation_invite_is_scoped_to_its_session(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)

    db = {
        "consultation_sessions": [
            {
                "id": "session-1",
                "task_id": "task-10",
                "status": "active",
                "created_at": "2026-04-21T00:00:00+00:00",
            },
            {
                "id": "session-2",
                "task_id": "task-10",
                "status": "summary_confirmed",
                "created_at": "2026-04-21T01:00:00+00:00",
            },
        ],
        "consultation_invites": [
            {
                "id": "invite-1",
                "task_id": "task-10",
                "session_id": "session-1",
                "token": "session-token",
                "status": "pending",
                "expires_at": "2999-01-01T00:00:00+00:00",
            }
        ],
        "consultation_messages": [
            {
                "task_id": "task-10",
                "session_id": "session-1",
                "role": "expert",
                "message": "本轮会诊意见",
                "created_at": "2026-04-21T00:00:00+00:00",
            },
            {
                "task_id": "task-10",
                "session_id": "session-2",
                "role": "expert",
                "message": "其他轮次意见",
                "created_at": "2026-04-21T00:00:01+00:00",
            },
        ],
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.get("/api/v1/consultation/task-10/messages?invite_token=session-token")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["message"] == "本轮会诊意见"


def test_consultation_session_approval_skip_close_and_summary(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)

    db = {
        "tasks": [{"id": "task-10", "status": "waiting_consultation", "user_id": "owner"}],
        "consultation_sessions": [
            {
                "id": "session-1",
                "task_id": "task-10",
                "status": "waiting_user_approval",
                "repeat_index": 2,
                "triggered_by_agent": "osint",
                "reason": "连续三轮低置信高质询",
                "context_payload": {"current_blocker": "图谱引用不足"},
            }
        ],
        "consultation_messages": [],
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    current = client.get("/api/v1/consultation/task-10/session")
    assert current.status_code == 200
    assert current.json()["session"]["id"] == "session-1"

    approved = client.post("/api/v1/consultation/task-10/sessions/session-1/approve")
    assert approved.status_code == 200
    assert approved.json()["session"]["status"] == "active"

    closed = client.post("/api/v1/consultation/task-10/sessions/session-1/close")
    assert closed.status_code == 200
    assert closed.json()["session"]["status"] == "summary_pending"
    assert db["consultation_messages"][-1]["role"] == "commander"

    confirmed = client.post(
        "/api/v1/consultation/task-10/sessions/session-1/summary",
        json={"summary": "用户确认：专家意见已纳入，优先复核来源账号。"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["session"]["status"] == "summary_confirmed"
    assert confirmed.json()["session"]["summary_payload"]["confirmed_summary"].startswith("用户确认")


def test_consultation_session_skip_records_this_round_only(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    monkeypatch.setattr("app.middleware.auth._is_public", lambda path, method="GET": True)

    db = {
        "tasks": [{"id": "task-11", "status": "waiting_consultation_approval", "user_id": "owner"}],
        "consultation_sessions": [
            {
                "id": "session-skip",
                "task_id": "task-11",
                "status": "waiting_user_approval",
                "repeat_index": 2,
                "triggered_by_agent": "commander",
                "reason": "最终报告连续低置信",
            }
        ],
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.post(
        "/api/v1/consultation/task-11/sessions/session-skip/skip",
        json={"reason": "本次先跳过，保留风险继续流程。"},
    )

    assert response.status_code == 200
    assert response.json()["session"]["status"] == "skipped"
    assert response.json()["session"]["summary_payload"]["skip_scope"] == "current_only"


def test_agent_history_available_to_expert_invite(monkeypatch):
    from app.api.v1 import consultation as consultation_module

    db = {
        "consultation_invites": [
            {
                "id": "invite-1",
                "task_id": "task-10",
                "token": "invite-token",
                "status": "pending",
                "expires_at": "2999-01-01T00:00:00+00:00",
            }
        ],
        "tasks": [{"id": "task-10", "status": "completed", "result": {"verdict": "suspicious"}}],
        "agent_logs": [
            {
                "task_id": "task-10",
                "round_number": 1,
                "agent_name": "forensics",
                "log_type": "finding",
                "content": "检测完成",
                "timestamp": "2026-04-21T00:00:00+00:00",
            }
        ],
        "analysis_states": [
            {
                "task_id": "task-10",
                "round_number": 1,
                "current_agent": "forensics",
                "result_snapshot": {"forensics": {"confidence": 0.7}},
                "evidence_board": {"evidence": []},
                "created_at": "2026-04-21T00:00:01+00:00",
            }
        ],
        "reports": [{"task_id": "task-10", "verdict_payload": {"verdict": "suspicious", "confidence": 0.8}}],
    }
    monkeypatch.setattr(consultation_module, "supabase", FakeSupabase(db))

    client = TestClient(app)
    response = client.get("/api/v1/consultation/task-10/agent-history?invite_token=invite-token")

    assert response.status_code == 200
    body = response.json()
    assert body["agent_logs"][0]["content"] == "检测完成"
    assert body["analysis_states"][0]["result_snapshot"]["forensics"]["confidence"] == 0.7
    assert body["report"]["verdict_payload"]["verdict"] == "suspicious"


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
