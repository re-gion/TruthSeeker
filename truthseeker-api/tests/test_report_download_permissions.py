import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeQuery:
    def __init__(self, rows, failures=None):
        self.rows = rows
        self.failures = failures
        self.filters = {}

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure
        rows = list(self.rows)
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, tasks, failures=None):
        self.tasks = tasks
        self.failures = failures or []

    def table(self, table_name):
        assert table_name == "tasks"
        return FakeQuery(self.tasks, self.failures)


@pytest.mark.asyncio
async def test_markdown_download_allows_legacy_anonymous_task(monkeypatch):
    from app.api.v1 import report as report_module
    from app.utils import supabase_client

    monkeypatch.setattr(
        supabase_client,
        "supabase",
        FakeSupabase([{"id": "task-1", "user_id": "anonymous"}]),
    )

    async def fake_generate_markdown_report(_task_id):
        return "# report"

    monkeypatch.setattr(report_module, "generate_markdown_report", fake_generate_markdown_report)
    monkeypatch.setattr(report_module, "record_audit_event", lambda **_kwargs: None)

    request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))

    response = await report_module.download_markdown_report("task-1", request)

    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    assert response.status_code == 200
    assert body == b"# report"


@pytest.mark.asyncio
async def test_markdown_download_retries_ssl_eof_owner_lookup(monkeypatch):
    from app.api.v1 import report as report_module
    from app.utils import supabase_client

    failures = [
        RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)"),
        None,
    ]
    monkeypatch.setattr(
        supabase_client,
        "supabase",
        FakeSupabase([{"id": "task-1", "user_id": "user-1"}], failures=failures),
    )

    async def fake_generate_markdown_report(_task_id):
        return "# report"

    monkeypatch.setattr(report_module, "generate_markdown_report", fake_generate_markdown_report)
    monkeypatch.setattr(report_module, "record_audit_event", lambda **_kwargs: None)

    request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))

    response = await report_module.download_markdown_report("task-1", request)

    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    assert response.status_code == 200
    assert body == b"# report"


@pytest.mark.asyncio
async def test_markdown_download_reports_ssl_eof_owner_lookup_as_unavailable(monkeypatch):
    from fastapi import HTTPException

    from app.api.v1 import report as report_module
    from app.utils import supabase_client

    failures = [
        RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)"),
        RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)"),
        RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)"),
    ]
    monkeypatch.setattr(
        supabase_client,
        "supabase",
        FakeSupabase([{"id": "task-1", "user_id": "user-1"}], failures=failures),
    )

    request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))

    with pytest.raises(HTTPException) as exc_info:
        await report_module.download_markdown_report("task-1", request)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "报告权限校验暂时不可用，请稍后重试"


def test_ssl_eof_is_treated_as_transient_report_read_error():
    from app.services.report_generator import _is_transient_read_error

    exc = RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)")

    assert _is_transient_read_error(exc) is True
