from datetime import datetime, timezone

from app.services.analysis_persistence import (
    build_agent_log_rows,
    build_analysis_state_row,
    build_report_row,
    normalize_final_verdict,
)


def test_normalize_final_verdict_adds_compatibility_aliases():
    verdict = {
        "verdict": "forged",
        "verdict_cn": "伪造",
        "confidence": 0.91,
        "key_evidence": [
            {"type": "visual", "source": "forensics", "confidence": 0.87},
            {"type": "osint", "source": "osint", "confidence": 0.75},
        ],
        "recommendations": ["立即下架"],
        "llm_ruling": "综合判断为伪造",
        "agent_weights": {"forensics": 0.45, "osint": 0.3, "challenger": 0.25},
    }

    normalized = normalize_final_verdict(verdict)

    assert normalized["confidence"] == 0.91
    assert normalized["confidence_overall"] == 0.91
    assert normalized["verdict"] == "forged"
    assert normalized["verdict_label"] == "forged"
    assert normalized["analysis_summary"] == "综合判断为伪造"
    assert normalized["agent_weights_used"]["forensics"] == 0.45
    assert normalized["total_evidence"] == 2


def test_build_report_row_uses_canonical_fields_and_share_defaults():
    verdict = normalize_final_verdict(
        {
            "verdict": "suspicious",
            "verdict_cn": "可疑",
            "confidence": 0.66,
            "key_evidence": [{"type": "audio", "source": "forensics", "confidence": 0.8}],
            "recommendations": ["人工复核"],
            "llm_ruling": "存在明显异常",
            "agent_weights": {"forensics": 0.45, "osint": 0.3, "challenger": 0.25},
        }
    )

    row = build_report_row("task-1", verdict, generated_at="2026-04-16T00:00:00+00:00")

    assert row["task_id"] == "task-1"
    assert row["verdict"] == "suspicious"
    assert row["confidence_overall"] == 0.66
    assert row["summary"] == "存在明显异常"
    assert row["recommendations"] == ["人工复核"]
    assert row["share_token"] is None


def test_build_agent_log_rows_maps_round_and_metadata():
    updates = {
        "logs": [
            {
                "agent": "forensics",
                "round": 2,
                "type": "finding",
                "content": "检测到异常",
                "timestamp": "2026-04-16T01:02:03+00:00",
            }
        ]
    }

    rows = build_agent_log_rows("task-2", "forensics", updates)

    assert rows == [
        {
            "task_id": "task-2",
            "round_number": 2,
            "agent_name": "forensics",
            "log_type": "finding",
            "content": "检测到异常",
            "metadata": {"node": "forensics"},
            "timestamp": "2026-04-16T01:02:03+00:00",
        }
    ]


def test_build_analysis_state_row_collects_round_scores_and_results():
    now = datetime.now(timezone.utc).isoformat()
    updates = {
        "current_round": 2,
        "forensics_result": {"confidence": 0.82, "deepfake_probability": 0.77},
        "osint_result": {"confidence": 0.61, "threat_score": 0.28},
        "challenger_feedback": {"quality_score": 0.73},
        "evidence_board": [{"type": "visual", "source": "forensics", "description": "异常", "confidence": 0.8, "metadata": {}}],
        "challenges": [{"issue": {"type": "contradiction"}}],
        "timeline_events": [{"summary": "forensics done"}],
        "termination_reason": "commander_ruling",
        "is_converged": True,
    }

    row = build_analysis_state_row("task-3", "commander", updates, created_at=now)

    assert row["task_id"] == "task-3"
    assert row["round_number"] == 2
    assert row["current_agent"] == "commander"
    assert row["forensics_score"] == 0.82
    assert row["osint_score"] == 0.61
    assert row["is_converged"] is True
    assert row["termination_reason"] == "commander_ruling"
    assert row["evidence_board"]["evidence"][0]["type"] == "visual"
    assert row["result_snapshot"]["challenger"]["quality_score"] == 0.73
