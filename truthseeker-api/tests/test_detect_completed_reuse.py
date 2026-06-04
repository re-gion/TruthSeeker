import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeQuery:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.filters = {}

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _key, desc=False):
        return self

    def execute(self):
        rows = list(self.db.setdefault(self.table_name, []))
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db):
        self.db = db

    def table(self, table_name):
        return FakeQuery(table_name, self.db)


@pytest.mark.asyncio
async def test_completed_task_stream_reuses_persisted_verdict_without_rerunning_graph(monkeypatch):
    from app.api.v1 import detect as detect_module

    db = {
        "tasks": [
            {
                "id": "task-completed",
                "user_id": "user-1",
                "status": "completed",
                "input_type": "text_image",
                "description": "completed case",
                "metadata": {
                    "case_prompt": "verify notification",
                    "files": [{"id": "file-1", "name": "notice.txt", "modality": "text"}],
                },
                "storage_paths": {
                    "files": [{"id": "file-1", "name": "notice.txt", "modality": "text"}],
                },
                "result": {"verdict": "suspicious", "confidence": 0.82},
            }
        ],
        "reports": [
            {
                "task_id": "task-completed",
                "verdict_payload": {
                    "verdict": "suspicious",
                    "confidence": 0.82,
                    "llm_ruling": "reuse existing verdict",
                },
            }
        ],
        "analysis_states": [],
    }
    monkeypatch.setattr(detect_module, "supabase", FakeSupabase(db))

    graph_calls = []

    class ExplodingGraph:
        async def astream(self, *_args, **_kwargs):
            graph_calls.append(True)
            raise AssertionError("completed task must not rerun graph")
            yield {}

    audit_events = []
    monkeypatch.setattr(detect_module, "compiled_graph", ExplodingGraph())
    monkeypatch.setattr(detect_module, "record_audit_event", lambda **kwargs: audit_events.append(kwargs))

    request = detect_module.DetectRequest(task_id="task-completed", resume=False)

    events = []
    async for raw in detect_module.sse_event_generator(request, "user-1"):
        if raw.startswith("data: "):
            events.append(json.loads(raw.removeprefix("data: ").strip()))

    assert graph_calls == []
    assert [event["type"] for event in events] == [
        "final_verdict",
        "case_import_skipped",
        "complete",
    ]
    assert events[0]["verdict"]["verdict"] == "suspicious"
    assert events[1]["reason"] == "already_completed"
    assert events[2]["reused"] is True
    assert [event["action"] for event in audit_events] == ["detect_reused_completed"]


def test_run_id_is_persisted_in_agent_logs_state_and_report_audit_metadata(monkeypatch):
    from app.services import analysis_persistence

    run_id = "run-final"
    updates = {
        "detection_run_id": run_id,
        "current_round": 1,
        "logs": [
            {
                "agent": "forensics",
                "type": "analysis",
                "content": "final run forensics",
                "timestamp": "2026-06-04T02:00:00+00:00",
            }
        ],
        "forensics_result": {"confidence": 0.91, "llm_analysis": "final forensics"},
        "final_verdict": {"verdict": "suspicious", "confidence": 0.88, "detection_run_id": run_id},
    }

    logs = analysis_persistence.build_agent_log_rows("task-1", "forensics", updates)
    state = analysis_persistence.build_analysis_state_row("task-1", "forensics", updates)
    report = analysis_persistence.build_report_row("task-1", updates["final_verdict"])

    assert logs[0]["metadata"]["detection_run_id"] == run_id
    assert state["result_snapshot"]["detection_run_id"] == run_id
    assert state["evidence_board"]["detection_run_id"] == run_id
    assert state["result_snapshot"]["final_verdict"]["detection_run_id"] == run_id
    assert report["verdict_payload"]["detection_run_id"] == run_id

    audit_events = []
    monkeypatch.setattr(analysis_persistence, "record_audit_event", lambda **kwargs: audit_events.append(kwargs))

    class FakePersistence(analysis_persistence.AnalysisPersistenceService):
        def __init__(self):
            super().__init__(client=SimpleNamespace())

        def _fetch_report(self, task_id):
            return None

        def _safe_insert(self, table_name, payload):
            return True

        def _safe_update_by_id(self, table_name, payload, record_id):
            return True

    FakePersistence().upsert_report("task-1", updates["final_verdict"])
    assert audit_events[0]["metadata"]["detection_run_id"] == run_id


@pytest.mark.asyncio
async def test_report_and_audit_exports_filter_to_final_detection_run(monkeypatch):
    from app.services import report_generator

    async def fake_fetch_task_data(_task_id):
        return {
            "task": {
                "id": "task-1",
                "title": "案例3-图片",
                "input_type": "text_image",
                "status": "completed",
                "created_at": "2026-06-04T01:27:04+00:00",
                "completed_at": "2026-06-04T02:15:40+00:00",
                "updated_at": "2026-06-04T02:15:50+00:00",
                "metadata": {"detection_run_count": 2, "last_detection_run_id": "run-final"},
            },
            "report": {
                "generated_at": "2026-06-04T02:15:40+00:00",
                "report_hash": "hash-final",
                "verdict_payload": {
                    "verdict": "suspicious",
                    "confidence": 0.88,
                    "detection_run_id": "run-final",
                    "analysis_summary": "final verdict summary",
                },
            },
            "analysis_states": [
                {
                    "created_at": "2026-06-04T01:30:00+00:00",
                    "round_number": 1,
                    "current_agent": "forensics",
                    "result_snapshot": {
                        "detection_run_id": "run-old",
                        "forensics": {"confidence": 0.2, "llm_analysis": "OLD FORENSICS SHOULD NOT APPEAR"},
                    },
                    "evidence_board": {"detection_run_id": "run-old", "timeline_events": []},
                },
                {
                    "created_at": "2026-06-04T02:12:00+00:00",
                    "round_number": 1,
                    "current_agent": "forensics",
                    "result_snapshot": {
                        "detection_run_id": "run-final",
                        "forensics": {"confidence": 0.91, "llm_analysis": "FINAL FORENSICS SHOULD APPEAR"},
                    },
                    "evidence_board": {"detection_run_id": "run-final", "timeline_events": []},
                },
            ],
            "agent_logs": [
                {
                    "timestamp": "2026-06-04T01:30:01+00:00",
                    "agent_name": "forensics",
                    "log_type": "analysis",
                    "content": "OLD LOG SHOULD NOT APPEAR",
                    "metadata": {"detection_run_id": "run-old"},
                },
                {
                    "timestamp": "2026-06-04T02:12:01+00:00",
                    "agent_name": "forensics",
                    "log_type": "analysis",
                    "content": "FINAL LOG SHOULD APPEAR",
                    "metadata": {"detection_run_id": "run-final"},
                },
            ],
            "audit_logs": [
                {
                    "created_at": "2026-06-04T01:29:59+00:00",
                    "action": "detect_start",
                    "metadata": {"detection_run_id": "run-old"},
                },
                {
                    "created_at": "2026-06-04T01:30:02+00:00",
                    "action": "forensics.completed",
                    "metadata": {},
                },
                {
                    "created_at": "2026-06-04T02:11:59+00:00",
                    "action": "detect_start",
                    "metadata": {"detection_run_id": "run-final"},
                },
                {
                    "created_at": "2026-06-04T02:12:02+00:00",
                    "action": "forensics.completed",
                    "metadata": {},
                },
                {
                    "created_at": "2026-06-04T02:15:40+00:00",
                    "action": "detect_completed",
                    "metadata": {"detection_run_id": "run-final"},
                },
            ],
            "consultation_sessions": [],
            "consultation_messages": [],
        }

    monkeypatch.setattr(report_generator, "_fetch_task_data", fake_fetch_task_data)

    markdown = await report_generator.generate_markdown_report("task-1")
    audit_markdown = await report_generator.generate_audit_log_markdown("task-1")

    assert "| 创建时间 | 2026-06-04 09:27:04 |" in markdown
    assert "| 完成时间 | 2026-06-04 10:15:40 |" in markdown
    assert "- **裁决时间**: 2026-06-04 10:15:40" in markdown
    assert "检测运行次数" not in markdown
    assert "最终有效运行 ID" not in markdown
    assert "任务记录更新时间" not in markdown
    assert "FINAL FORENSICS SHOULD APPEAR" in markdown
    assert "FINAL LOG SHOULD APPEAR" in markdown
    assert "forensics.completed" in markdown
    assert "OLD FORENSICS SHOULD NOT APPEAR" not in markdown
    assert "OLD LOG SHOULD NOT APPEAR" not in markdown

    assert "FINAL LOG SHOULD APPEAR" in audit_markdown
    assert "OLD LOG SHOULD NOT APPEAR" not in audit_markdown


def test_active_analyzing_task_with_run_id_is_locked_against_fresh_start():
    from app.api.v1 import detect as detect_module

    assert detect_module._is_active_analyzing_task(
        {
            "status": "analyzing",
            "metadata": {"active_detection_run_id": "run-active"},
        }
    )


@pytest.mark.asyncio
async def test_detect_stream_rejects_fresh_start_when_task_is_already_analyzing(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1 import detect as detect_module

    monkeypatch.setattr(
        detect_module,
        "_fetch_task",
        lambda _task_id: {
            "id": "task-active",
            "user_id": "user-1",
            "status": "analyzing",
            "metadata": {"active_detection_run_id": "run-active"},
        },
    )

    request = detect_module.DetectRequest(task_id="task-active", resume=False)
    raw_request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))

    with pytest.raises(HTTPException) as exc_info:
        await detect_module.detect_stream(request, raw_request)

    assert exc_info.value.status_code == 409
    assert "避免重复研判" in exc_info.value.detail
