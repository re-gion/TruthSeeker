"""回归测试：载荷中的 NUL（U+0000）不得导致 Postgres 22P05 写入失败。

背景：一次视频+文本检材检测中，外部工具/文本内容混入 \x00，
analysis_states/reports/tasks 三处写入全部被 Postgres 拒绝（错误码 22P05），
整次检测在最后一步丢失。持久化层现在必须在写入前剥离 NUL。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import analysis_persistence, audit_log
from app.services.report_integrity import build_report_hash
from app.services.text_validation import decode_text_bytes, strip_null_bytes


def _serialized(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class PostgresNulRejected(Exception):
    """模拟 Postgres: \\u0000 cannot be converted to text (22P05)."""


def _assert_no_nul(value) -> None:
    if isinstance(value, str):
        if "\x00" in value:
            raise PostgresNulRejected(
                "{'message': 'unsupported Unicode escape sequence', "
                "'code': '22P05', 'details': '\\\\u0000 cannot be converted to text.'}"
            )
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_no_nul(key)
            _assert_no_nul(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_nul(item)


class FakeQuery:
    def __init__(self, table_name, db, fail_tables=()):
        self.table_name = table_name
        self.db = db
        self.fail_tables = fail_tables
        self.filters = {}
        self._payload = None
        self._mode = None

    def select(self, _columns):
        self._mode = "select"
        return self

    def insert(self, payload):
        if self.table_name in self.fail_tables:
            raise PostgresNulRejected("simulated storage outage")
        _assert_no_nul(payload)
        self._payload = payload
        self._mode = "insert"
        return self

    def update(self, payload):
        _assert_no_nul(payload)
        self._payload = payload
        self._mode = "update"
        return self

    def upsert(self, payload, on_conflict=None):
        _assert_no_nul(payload)
        self._payload = payload
        self._mode = "upsert"
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _key, desc=False):
        return self

    def execute(self):
        rows = self.db.setdefault(self.table_name, [])
        if self._mode == "select":
            result = list(rows)
            for key, value in self.filters.items():
                result = [row for row in result if row.get(key) == value]
            return SimpleNamespace(data=result)
        if self._mode == "insert":
            inserted = self._payload if isinstance(self._payload, list) else [self._payload]
            stored = []
            for item in inserted:
                copy = json.loads(json.dumps(item))
                # 模拟 Postgres 自动生成主键
                copy.setdefault("id", f"{self.table_name}-row-{len(rows) + len(stored) + 1}")
                stored.append(copy)
            rows.extend(stored)
            return SimpleNamespace(data=list(stored))
        if self._mode in {"update", "upsert"}:
            for row in rows:
                if all(row.get(key) == value for key, value in self.filters.items()):
                    row.update(json.loads(json.dumps(self._payload)))
            return SimpleNamespace(data=rows)
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, db, fail_tables=()):
        self.db = db
        self.fail_tables = fail_tables

    def table(self, table_name):
        return FakeQuery(table_name, self.db, self.fail_tables)


def test_strip_null_bytes_recursively():
    payload = {
        "text": "a\x00b",
        "nested": {"inner": ["x\x00", {"deep": "\x00\x00"}], "keep": 1},
        "number": 0.5,
        "flag": True,
        "none": None,
    }
    cleaned = strip_null_bytes(payload)
    assert "\x00" not in _serialized(cleaned)
    assert cleaned["text"] == "ab"
    assert cleaned["nested"]["inner"][0] == "x"
    assert cleaned["nested"]["inner"][1]["deep"] == ""
    assert cleaned["nested"]["keep"] == 1
    assert cleaned["number"] == 0.5
    assert cleaned["flag"] is True
    assert cleaned["none"] is None


def test_decode_text_bytes_strips_nul_before_truncation():
    decoded = decode_text_bytes(b"a\x00b\x00c")
    assert decoded["text"] == "abc"
    # 先剥离再截断：max_chars 统计的是可用字符而非原始字节位置
    decoded = decode_text_bytes(b"a\x00" * 10, max_chars=5)
    assert decoded["text"] == "aaaaa"


def test_build_report_row_strips_nul_and_keeps_hash_consistent():
    verdict = {
        "verdict": "suspicious",
        "confidence": 0.712,
        "analysis_summary": "摘要\x00含NUL",
        "llm_ruling": "### 最终裁决结论\n可疑\x00",
        "key_evidence": [{"type": "file", "source": "video\x00.mp4", "confidence": 0.8}],
        "recommendations": ["建议\x00复核"],
    }
    row = analysis_persistence.build_report_row("task-1", verdict)
    assert "\x00" not in _serialized(row)
    assert row["summary"] == "摘要含NUL"
    # report_hash 必须与实际入库（已清洗）内容一致
    assert row["report_hash"] == build_report_hash(row)


def test_build_analysis_state_and_log_rows_strip_nul():
    updates = {
        "current_round": 1,
        "detection_run_id": "run-1",
        "forensics_result": {"confidence": 0.6, "llm_analysis": "forensics\x00"},
        "osint_result": {"confidence": 0.8, "threat_score": 0.2},
        "challenger_feedback": None,
        "final_verdict": None,
        "evidence_board": [{"source": "video\x00.mp4"}],
        "challenges": [],
        "timeline_events": [{"content": "event\x00"}],
        "logs": [{"agent": "forensics", "type": "action", "content": "log\x00", "round": 1}],
    }
    state_row = analysis_persistence.build_analysis_state_row("task-1", "forensics", updates)
    log_rows = analysis_persistence.build_agent_log_rows("task-1", "forensics", updates)
    assert "\x00" not in _serialized(state_row)
    assert "\x00" not in _serialized(log_rows)
    assert log_rows[0]["content"] == "log"


def test_persist_update_and_mark_completed_survive_nul_payload():
    """模拟 Postgres 22P05 拒写：清洗后整条检测流程收尾必须成功。"""
    db = {"tasks": [{"id": "task-1", "status": "analyzing"}]}
    service = analysis_persistence.AnalysisPersistenceService(client=FakeSupabase(db))
    final_verdict = {
        "verdict": "suspicious",
        "confidence": 0.712,
        "analysis_summary": "ok\x00",
        "llm_ruling": "### 最终裁决结论\n可疑\x00",
        "key_evidence": [{"type": "file", "source": "a\x00.mp4", "confidence": 0.9}],
        "recommendations": ["rec\x00"],
    }
    updates = {
        "current_round": 1,
        "detection_run_id": "run-1",
        "forensics_result": {
            "confidence": 0.6,
            "llm_analysis": "forensics\x00",
            "tool_results": [{"tool": "reality_defender", "summary": "s\x00"}],
        },
        "osint_result": None,
        "challenger_feedback": None,
        "final_verdict": final_verdict,
        "evidence_board": [{"type": "file", "source": "video\x00.mp4", "confidence": 0.8}],
        "logs": [{"agent": "commander", "type": "conclusion", "content": "log\x00", "round": 1}],
    }

    service.persist_update("task-1", "commander", updates)
    service.mark_task_completed("task-1", analysis_persistence.normalize_final_verdict(final_verdict))

    assert db["reports"], "reports 行必须写入成功"
    assert db["analysis_states"], "analysis_states 行必须写入成功"
    assert db["agent_logs"], "agent_logs 行必须写入成功"
    assert db["tasks"][0]["status"] == "completed"
    for table in ("reports", "analysis_states", "agent_logs", "tasks"):
        assert "\x00" not in _serialized(db[table]), f"{table} 中仍残留 NUL"


def test_upsert_report_does_not_audit_when_write_fails(monkeypatch):
    db = {}
    service = analysis_persistence.AnalysisPersistenceService(
        client=FakeSupabase(db, fail_tables={"reports"})
    )
    audit_calls = []
    monkeypatch.setattr(analysis_persistence, "record_audit_event", lambda **kwargs: audit_calls.append(kwargs))

    service.upsert_report("task-1", {"verdict": "suspicious", "confidence": 0.7})

    assert audit_calls == [], "写入失败时不得记录 report_generated 审计"


def test_audit_row_metadata_strips_nul():
    row = audit_log.build_audit_log_row(
        action="commander.verdict",
        task_id="task-1",
        agent="commander",
        metadata={"llm_ruling": "text\x00", "nested": {"k": "\x00"}},
    )
    assert "\x00" not in _serialized(row)


@pytest.mark.asyncio
async def test_experience_confirm_strips_nul_before_insert_and_index(monkeypatch):
    from app.services import experience_library

    monkeypatch.setattr(
        experience_library, "_existing_experiences", lambda client, user_id, agents: []
    )

    async def fake_embed(text):
        assert "\x00" not in text, "进入 embedding 的文本也必须已清洗"
        return {"status": "success", "embedding": [0.1] * 8, "model": "fake"}

    monkeypatch.setattr(experience_library, "embed_text", fake_embed)

    db: dict = {}
    client = FakeSupabase(db)  # FakeQuery 见 NUL 即抛 PostgresNulRejected
    draft = {
        "title": "含 NUL 的标题",
        "target_agents": ["forensics"],
        "problem_pattern": "问题模式\x00",
        "recommended_method": "推荐方法\x00",
        "evidence_to_check": [],
        "when_to_escalate": "",
        "limitations": "",
    }
    result = await experience_library.confirm_experience_drafts(
        client=client, user_id="u1", task_id="t1", session_id="s1", drafts=[draft],
    )
    assert result["status"] == "ok", result
    assert result["inserted"] == 1
    assert result["indexed_chunks"] >= 1
    assert "\x00" not in _serialized(db.get("experience_library_entries", []))
    assert "\x00" not in _serialized(db.get("experience_library_rag_chunks", []))


@pytest.mark.asyncio
async def test_case_library_entry_insert_strips_nul(monkeypatch):
    from app.services import case_library

    monkeypatch.setattr(case_library, "find_duplicate_case", lambda client, files, prompt: None)

    async def fake_title(task, report, llm, *, client=None):
        return ("案例标题", "案例摘要")

    monkeypatch.setattr(case_library, "generate_case_title_and_summary", fake_title)

    db: dict = {}
    client = FakeSupabase(db)
    task = {
        "id": "task-1",
        "input_type": "video_text",
        "description": "检测诉求含 NUL",
        "metadata": {
            "share_to_casebase": True,
            "case_prompt": "cp\x00",
            "files": [{"name": "v.mp4", "modality": "video", "sha256": "f" * 64}],
        },
        "result": {"verdict": "suspicious", "confidence_overall": 0.712},
    }
    report = {
        "task_id": "task-1",
        "verdict": "suspicious",
        "confidence_overall": 0.712,
        "summary": "摘要\x00",
        "key_evidence": [],
        "recommendations": [],
        "generated_at": "2026-08-15T12:00:00+00:00",
        "verdict_payload": {"verdict": "suspicious", "llm_ruling": "ruling\x00"},
    }
    result = await case_library.ensure_case_library_entry(
        client, task, report, report_markdown="# 报告含 NUL\n\n正文"
    )
    assert result["status"] == "created", result
    assert db.get("case_library_entries"), "案例条目必须写入成功"
    assert "\x00" not in _serialized(db["case_library_entries"])


@pytest.mark.asyncio
async def test_case_rag_index_strips_nul(monkeypatch):
    from app.services import case_rag

    async def fake_embed(text):
        assert "\x00" not in text
        return {"status": "success", "embedding": [0.1] * 8, "model": "fake"}

    monkeypatch.setattr(case_rag, "embed_text", fake_embed)

    db: dict = {}
    client = FakeSupabase(db)
    row = {
        "id": "case-1",
        "title": "标题\x00",
        "media_category": "video_forgery",
        "verdict": "suspicious",
        "report_markdown": "# 标题\n\n段落含 NUL 字符",
        "published_at": "2026-08-15T12:00:00+00:00",
        "task_id": "task-1",
    }
    result = await case_rag.index_case_record(client, row, source_kind="public")
    assert result["chunks"] >= 1
    assert result["indexed"] == result["chunks"], result
    assert result["errors"] == []
    assert "\x00" not in _serialized(db.get("case_library_rag_chunks", []))