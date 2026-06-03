from app.agents.nodes import osint as osint_module


def test_osint_first_round_ignores_forensics_challenger_feedback():
    context = osint_module._build_reinforcement_context(
        {
            "challenger_feedback": {
                "phase": "forensics",
                "target_agent": "forensics",
                "llm_cross_validation": "forensics 质询内容",
                "issues_found": [
                    {"agent": "forensics", "severity": "high", "description": "取证缺少来源"}
                ],
            },
            "confirmed_consultation_summary": {
                "confirmed_summary": "专家意见针对取证阶段",
                "target_agent": "forensics",
            },
        },
        "osint",
        {},
    )

    assert context is None
