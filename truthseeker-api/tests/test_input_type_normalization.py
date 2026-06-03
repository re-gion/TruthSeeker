from __future__ import annotations

import importlib
import sys
import types


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


def _file(modality: str, index: int = 1) -> dict:
    return {
        "id": f"{modality}-{index}",
        "name": f"{modality}-{index}",
        "mime_type": f"{modality}/unknown" if modality != "text" else "text/plain",
        "size_bytes": 1,
        "modality": modality,
    }


def test_input_type_catalog_has_all_single_double_triple_and_quad_modalities():
    input_types = import_with_asyncio_fallback("app.services.input_types")

    assert input_types.INPUT_TYPE_VALUES == (
        "text",
        "image",
        "audio",
        "video",
        "text_image",
        "text_audio",
        "text_video",
        "image_audio",
        "image_video",
        "audio_video",
        "text_image_audio",
        "text_image_video",
        "text_audio_video",
        "image_audio_video",
        "text_image_audio_video",
    )


def test_derive_input_type_returns_specific_combination_instead_of_mixed():
    evidence_files = import_with_asyncio_fallback("app.services.evidence_files")

    assert evidence_files.derive_input_type([_file("image"), _file("text")]) == "text_image"
    assert evidence_files.derive_input_type([_file("video"), _file("audio")]) == "audio_video"
    assert evidence_files.derive_input_type([_file("text"), _file("image"), _file("video")]) == "text_image_video"
    assert evidence_files.derive_input_type([
        _file("text"),
        _file("image"),
        _file("audio"),
        _file("video"),
    ]) == "text_image_audio_video"


def test_display_input_type_labels_legacy_mixed_as_image_text():
    input_types = import_with_asyncio_fallback("app.services.input_types")
    dashboard = import_with_asyncio_fallback("app.api.v1.dashboard")

    assert input_types.display_input_type("mixed") == "图文混合"
    assert input_types.display_input_type("text_image") == "图文混合"
    assert input_types.display_input_type("text_audio_video") == "文本+音频+视频"
    assert dashboard._display_input_type("mixed") == "图文混合"


def test_markdown_report_uses_display_input_type_and_agent_display_names():
    report_generator = import_with_asyncio_fallback("app.services.report_generator")

    async def fake_fetch_task_data(_task_id):
        return {
            "task": {
                "id": "task-1",
                "title": "图文测试",
                "input_type": "mixed",
                "status": "completed",
                "created_at": "2026-06-03T00:00:00+00:00",
                "updated_at": "2026-06-03T00:01:00+00:00",
                "result": {"verdict": "suspicious", "confidence": 0.7},
            },
            "report": {"generated_at": "2026-06-03T00:02:00+00:00", "verdict_payload": {}},
            "analysis_states": [
                {
                    "result_snapshot": {
                        "forensics": {
                            "degraded": True,
                            "tool_summary": {"success": 0, "total": 1, "degraded": 1, "failed": 0},
                        }
                    }
                }
            ],
            "agent_logs": [],
            "audit_logs": [],
            "consultation_sessions": [],
            "consultation_messages": [],
        }

    original_fetch = report_generator._fetch_task_data
    report_generator._fetch_task_data = fake_fetch_task_data
    try:
        markdown = import_with_asyncio_fallback("asyncio").new_event_loop().run_until_complete(
            report_generator.generate_markdown_report("task-1")
        )
    finally:
        report_generator._fetch_task_data = original_fetch

    assert "| 输入类型 | 图文混合 |" in markdown
    assert "电子取证 Agent 降级" in markdown
    assert "## 三、电子取证 Agent 分析" in markdown
    assert "Forensics 取证" not in markdown
    assert "法医" not in markdown
    assert report_generator._agent_display_name("forensics") == "电子取证 Agent"
    assert report_generator._agent_display_name("osint") == "情报溯源 Agent"


def test_task_create_constraint_error_mentions_pending_input_type_migration():
    tasks = import_with_asyncio_fallback("app.api.v1.tasks")
    exc = RuntimeError({
        "message": 'new row for relation "tasks" violates check constraint "tasks_input_type_check"',
        "code": "23514",
        "details": "Failing row contains (..., text_image, ...)",
    })

    assert tasks._is_input_type_constraint_error(exc) is True
    assert "20260603_input_type_combinations.sql" in tasks._task_create_error_detail(exc)
