import os
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_sync_coroutine(coro):
    try:
        coro.send(None)
    except StopIteration as stop:
        return stop.value
    raise RuntimeError("coroutine unexpectedly awaited")


def import_with_asyncio_fallback(module_name: str):
    try:
        return importlib.import_module(module_name)
    except OSError as exc:
        if "WinError 10106" not in str(exc):
            raise
        for key in list(sys.modules):
            if key == "asyncio" or key.startswith("asyncio."):
                del sys.modules[key]
        fake_asyncio = types.ModuleType("asyncio")

        async def sleep(_delay=0):
            return None

        async def to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        fake_asyncio.sleep = sleep
        fake_asyncio.to_thread = to_thread
        sys.modules["asyncio"] = fake_asyncio
        return importlib.import_module(module_name)


class AuthConfigurationTests(unittest.TestCase):
    def test_production_requires_a_real_supabase_jwt_secret(self):
        from app.services.auth_config import validate_auth_configuration

        with self.assertRaises(RuntimeError):
            validate_auth_configuration(environment="production", jwt_secret="NOT_SET")

        self.assertFalse(validate_auth_configuration(environment="development", jwt_secret="NOT_SET"))
        self.assertTrue(validate_auth_configuration(environment="production", jwt_secret="real-secret"))


class BackendErrorVisibilityTests(unittest.TestCase):
    def test_list_tasks_exposes_database_failures_instead_of_empty_lists(self):
        from app.api.v1 import tasks as tasks_module

        class BrokenSupabase:
            def table(self, _table_name):
                raise RuntimeError("database unavailable")

        request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))

        original_supabase = tasks_module.supabase
        tasks_module.supabase = BrokenSupabase()
        try:
            with self.assertRaises(HTTPException) as ctx:
                run_sync_coroutine(tasks_module.list_tasks(request))
        finally:
            tasks_module.supabase = original_supabase

        self.assertEqual(ctx.exception.status_code, 503)

    def test_dashboard_collects_data_source_warnings(self):
        from app.api.v1 import dashboard as dashboard_module

        class BrokenSupabase:
            def table(self, _table_name):
                raise RuntimeError("database unavailable")

        warnings: list[dict[str, str]] = []
        original_supabase = dashboard_module.supabase
        dashboard_module.supabase = BrokenSupabase()
        try:
            rows = dashboard_module._select_rows("tasks", "id,status", warnings)
        finally:
            dashboard_module.supabase = original_supabase

        self.assertEqual(rows, [])
        self.assertEqual(warnings[0]["table"], "tasks")
        self.assertIn("数据源读取失败", warnings[0]["message"])


class TextUploadValidationTests(unittest.TestCase):
    def test_text_plain_validation_rejects_binary_content_and_unsafe_extension(self):
        from app.services.text_validation import validate_text_plain_file

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(b"hello\x00\x01\x02binary")
            binary_path = tmp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write("这是可解码的中文文本\nhttps://example.com".encode("gb18030"))
            text_path = tmp.name

        try:
            self.assertFalse(validate_text_plain_file(binary_path, "evidence.txt"))
            self.assertFalse(validate_text_plain_file(text_path, "payload.exe"))
            self.assertTrue(validate_text_plain_file(text_path, "evidence.txt"))
        finally:
            os.unlink(binary_path)
            os.unlink(text_path)


class StableFallbackTests(unittest.TestCase):
    def test_deepfake_mock_uses_stable_hashing_instead_of_random(self):
        source = (PROJECT_ROOT / "app" / "agents" / "tools" / "deepfake_api.py").read_text(encoding="utf-8")

        self.assertIn("hashlib.sha256", source)
        self.assertNotIn("random.", source)

    def test_url_mock_uses_sha256_instead_of_python_hash_seed(self):
        source = (PROJECT_ROOT / "app" / "agents" / "tools" / "threat_intel.py").read_text(encoding="utf-8")

        self.assertIn("hashlib.sha256", source)
        self.assertNotIn("hash(url)", source)


class PdfFallbackTests(unittest.TestCase):
    def test_pdf_generation_falls_back_when_weasyprint_system_libs_are_unavailable(self):
        report_generator = import_with_asyncio_fallback("app.services.report_generator")

        original_generate_markdown_report = report_generator.generate_markdown_report
        original_import_module = report_generator.importlib.import_module

        async def fake_generate_markdown_report(_task_id):
            return "# TruthSeeker 报告\n\n中文内容可导出。"

        def fake_import_module(name):
            if name == "weasyprint":
                raise OSError("cannot load library 'libgobject-2.0-0'")
            return original_import_module(name)

        report_generator.generate_markdown_report = fake_generate_markdown_report
        report_generator.importlib.import_module = fake_import_module
        try:
            pdf_bytes = run_sync_coroutine(report_generator.generate_pdf_report("task-1"))
        finally:
            report_generator.generate_markdown_report = original_generate_markdown_report
            report_generator.importlib.import_module = original_import_module

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)


class RealityDefenderDiagnosticsTests(unittest.TestCase):
    def test_mock_deepfake_result_records_fallback_reason_and_key_presence(self):
        deepfake_api = import_with_asyncio_fallback("app.agents.tools.deepfake_api")

        result = run_sync_coroutine(
            deepfake_api.mock_deepfake_analysis(
                "mock://image-1",
                "image",
                fallback_reason="network_unavailable",
                api_key_configured=True,
            )
        )

        self.assertTrue(result["degraded"])
        self.assertEqual(result["details"]["fallback_reason"], "network_unavailable")
        self.assertTrue(result["details"]["api_key_configured"])


class ReportPersistenceTests(unittest.TestCase):
    def test_upsert_report_updates_existing_report_without_requiring_task_id_unique_constraint(self):
        from app.services.analysis_persistence import AnalysisPersistenceService

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

            def update(self, payload):
                self.operation = "update"
                self.payload = payload
                return self

            def execute(self):
                table = self.db.setdefault(self.table_name, [])
                if self.operation == "insert":
                    table.append(self.payload)
                    return SimpleNamespace(data=[self.payload])
                if self.operation == "update":
                    for row in table:
                        if all(row.get(k) == v for k, v in self.filters.items()):
                            row.update(self.payload)
                            return SimpleNamespace(data=[row])
                    return SimpleNamespace(data=[])

                rows = table
                for key, value in self.filters.items():
                    rows = [row for row in rows if row.get(key) == value]
                return SimpleNamespace(data=rows)

        class FakeClient:
            def __init__(self):
                self.db = {
                    "reports": [
                        {
                            "id": "report-1",
                            "task_id": "task-1",
                            "share_token": "keep-token",
                            "summary": "old",
                        }
                    ],
                    "audit_logs": [],
                }

            def table(self, table_name):
                return FakeQuery(table_name, self.db)

        client = FakeClient()
        service = AnalysisPersistenceService(client=client)
        service.upsert_report("task-1", {"verdict": "suspicious", "confidence": 0.81, "llm_ruling": "new"})

        reports = client.db["reports"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["share_token"], "keep-token")
        self.assertEqual(reports[0]["summary"], "new")
        self.assertTrue(reports[0]["report_hash"])


class ConsultationResumeRecoveryTests(unittest.TestCase):
    def test_resume_state_rebuilds_last_agent_snapshots_and_expert_messages(self):
        from app.services.analysis_persistence import build_resume_state_from_rows

        state = build_resume_state_from_rows(
            task_id="11111111-1111-1111-1111-111111111111",
            user_id="user-1",
            input_files={"files": []},
            input_type="video",
            priority_focus="balanced",
            case_prompt="核验来源",
            evidence_files=[],
            max_rounds=3,
            expert_messages=[{"role": "expert", "message": "建议人工复核"}],
            rows=[
                {
                    "round_number": 1,
                    "current_agent": "forensics",
                    "result_snapshot": {"forensics": {"confidence": 0.8}},
                    "evidence_board": {"evidence": [{"type": "visual"}], "timeline_events": [{"summary": "取证完成"}]},
                },
                {
                    "round_number": 1,
                    "current_agent": "osint",
                    "result_snapshot": {"osint": {"confidence": 0.7, "threat_score": 0.2}},
                    "evidence_board": {"evidence": [{"type": "osint"}]},
                },
                {
                    "round_number": 1,
                    "current_agent": "challenger",
                    "result_snapshot": {"challenger": {"quality_score": 0.6, "consultation_required": True}},
                    "evidence_board": {"challenges": [{"issue": "conflict"}]},
                },
            ],
        )

        self.assertEqual(state["forensics_result"]["confidence"], 0.8)
        self.assertEqual(state["osint_result"]["threat_score"], 0.2)
        self.assertTrue(state["challenger_feedback"]["consultation_required"])
        self.assertEqual(len(state["evidence_board"]), 2)
        self.assertEqual(state["expert_messages"][0]["message"], "建议人工复核")
        self.assertEqual(state["consultation_resume"]["action"], "resume_from_persistence")


class ForensicsMaintenanceTests(unittest.TestCase):
    def test_forensics_agent_no_longer_contains_unreachable_text_detection_branch(self):
        source = (PROJECT_ROOT / "app" / "agents" / "nodes" / "forensics.py").read_text(encoding="utf-8")

        self.assertNotIn("analyze_text", source)
        self.assertNotIn("文本检测通道", source)


if __name__ == "__main__":
    unittest.main()
