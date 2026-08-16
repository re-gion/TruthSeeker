"""逻辑质询时间线排序回归测试。

背景：analysis_states 的 round_number 是“进度水位线”而非“本行所属轮次”
（forensics/osint 行恒为 1，challenger 打回行写的是下一轮编号），
且表上唯一索引是 (task_id, round_number)。因此 Supabase 在无 ORDER BY 时
返回的行顺序未定义，报告里会出现第 2 轮排在第 1 轮前面。

这些测试直接喂乱序行，确认渲染层按 (阶段序, 阶段轮次, 时间) 稳定重排。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _challenger_state(phase: str, phase_round: int, created_at: str, *, released: bool) -> dict:
    return {
        "created_at": created_at,
        # 刻意复现真实写入行为：打回行的 round_number 是“下一轮”，因此并列/错位。
        "round_number": phase_round if released else phase_round + 1,
        "current_agent": "challenger",
        "result_snapshot": {
            "detection_run_id": "run-order",
            "challenger": {
                "phase": phase,
                "phase_round": phase_round,
                "confidence": 0.88 if released else 0.80,
                "issue_count": 0 if released else 2,
                "high_severity_count": 0,
                "requires_more_evidence": not released,
                "next_action": "release" if released else "return_for_reinforcement",
                "action_reason": ("放行进入下一阶段。" if released else "打回针对性补强。"),
                "timestamp": created_at,
            },
        },
        "evidence_board": {"detection_run_id": "run-order", "timeline_events": []},
    }


def _round_headings(sections: list[str]) -> list[str]:
    return [line for line in sections if line.startswith("### 逻辑质询Agent")]


def test_timeline_sorts_rounds_ascending_even_when_rows_arrive_scrambled():
    from app.services import report_generator

    # 数据库以乱序返回：第 2 轮在前，第 1 轮在后。
    scrambled = [
        _challenger_state("forensics", 2, "2026-08-14T15:14:57+00:00", released=True),
        _challenger_state("forensics", 1, "2026-08-14T15:13:22+00:00", released=False),
    ]

    sections = report_generator._build_challenger_timeline_sections(scrambled, [])
    headings = _round_headings(sections)

    assert len(headings) == 2
    assert "第 1 轮" in headings[0]
    assert "第 2 轮" in headings[1]


def test_timeline_orders_phases_by_runtime_topology_not_row_order():
    from app.services import report_generator

    # osint 行排在最前，但拓扑固定 forensics -> osint -> commander。
    scrambled = [
        _challenger_state("osint", 1, "2026-08-14T15:20:00+00:00", released=True),
        _challenger_state("forensics", 2, "2026-08-14T15:14:57+00:00", released=True),
        _challenger_state("forensics", 1, "2026-08-14T15:13:22+00:00", released=False),
    ]

    headings = _round_headings(report_generator._build_challenger_timeline_sections(scrambled, []))

    assert len(headings) == 3
    forensics_label = report_generator._agent_display_name("forensics")
    osint_label = report_generator._agent_display_name("osint")
    assert forensics_label in headings[0] and "第 1 轮" in headings[0]
    assert forensics_label in headings[1] and "第 2 轮" in headings[1]
    assert osint_label in headings[2] and "第 1 轮" in headings[2]


def test_timeline_double_digit_rounds_sort_numerically():
    from app.services import report_generator

    # 字符串排序会把“第 10 轮”排到“第 2 轮”前面，确认走的是数值序。
    scrambled = [
        _challenger_state("forensics", 10, "2026-08-14T15:30:00+00:00", released=True),
        _challenger_state("forensics", 2, "2026-08-14T15:14:57+00:00", released=False),
    ]

    headings = _round_headings(report_generator._build_challenger_timeline_sections(scrambled, []))

    assert "第 2 轮" in headings[0]
    assert "第 10 轮" in headings[1]


def test_legacy_agent_log_fallback_is_also_sorted():
    from app.services import report_generator

    # 旧数据只有 agent_logs 时同样必须有序。
    logs = [
        {
            "timestamp": "2026-08-14T15:14:57+00:00",
            "content": "逻辑质询Agent 启动：phase=forensics, phase_round=2/5",
        },
        {
            "timestamp": "2026-08-14T15:13:22+00:00",
            "content": "逻辑质询Agent 启动：phase=forensics, phase_round=1/5",
        },
    ]

    headings = _round_headings(report_generator._build_challenger_timeline_sections([], logs))

    assert len(headings) == 2
    assert "第 1 轮" in headings[0]
    assert "第 2 轮" in headings[1]


def test_sort_rows_by_time_drops_non_dict_rows_and_orders_ascending():
    from app.services import report_generator

    rows = [
        {"created_at": "2026-08-14T15:14:57+00:00", "tag": "later"},
        "not-a-row",
        {"created_at": "2026-08-14T15:13:22+00:00", "tag": "earlier"},
    ]

    ordered = report_generator._sort_rows_by_time(rows)

    assert [row["tag"] for row in ordered] == ["earlier", "later"]


@pytest.mark.asyncio
async def test_markdown_report_renders_rounds_in_order_from_unordered_fetch(monkeypatch):
    from app.services import report_generator

    async def fake_fetch_task_data(_task_id):
        return {
            "task": {
                "id": "task-order",
                "title": "乱序快照任务",
                "input_type": "image",
                "status": "completed",
                "result": {
                    "detection_run_id": "run-order",
                    "verdict": "authentic",
                    "confidence": 0.9,
                },
            },
            "report": {
                "task_id": "task-order",
                "generated_at": "2026-08-14T15:25:00+00:00",
                "verdict_payload": {
                    "detection_run_id": "run-order",
                    "verdict": "authentic",
                    "confidence": 0.9,
                },
            },
            # 与生产一致：查询未排序，最新一轮可能排在最前。
            "analysis_states": [
                _challenger_state("forensics", 2, "2026-08-14T15:14:57+00:00", released=True),
                _challenger_state("forensics", 1, "2026-08-14T15:13:22+00:00", released=False),
            ],
            "agent_logs": [],
            "audit_logs": [],
            "consultation_sessions": [],
            "consultation_messages": [],
        }

    monkeypatch.setattr(report_generator, "_fetch_task_data", fake_fetch_task_data)

    markdown = await report_generator.generate_markdown_report("task-order")

    first = markdown.index("逻辑质询Agent ↔ 电子取证 Agent 第 1 轮")
    second = markdown.index("逻辑质询Agent ↔ 电子取证 Agent 第 2 轮")
    assert first < second, "第 1 轮必须排在第 2 轮之前"
