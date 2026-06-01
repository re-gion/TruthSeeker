import asyncio


def test_forensics_records_case_rag_tool_result(monkeypatch):
    from app.agents.nodes import forensics as forensics_module

    async def fake_rag(*args, **kwargs):
        return {
            "tool": "case_rag_search",
            "status": "success",
            "degraded": False,
            "summary": "命中 1 个公开案例",
            "matches": [{"case_id": "builtin-audio-scam", "title": "董事长语音诈骗", "score": 0.86}],
        }

    async def fake_interpret(*args, **kwargs):
        return "### 自主检材观察\n类案仅作参考。"

    monkeypatch.setattr(forensics_module, "case_rag_search", fake_rag)
    monkeypatch.setattr(forensics_module, "forensics_interpret", fake_interpret)
    monkeypatch.setattr(forensics_module, "record_audit_event", lambda *args, **kwargs: None)

    updates = asyncio.run(forensics_module.forensics_node(
        {
            "task_id": "task-1",
            "input_type": "audio",
            "case_prompt": "核验高管语音转账诈骗",
            "current_round": 1,
            "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
            "evidence_files": [],
            "tool_results": {},
            "confidence_history": [],
        }
    ))

    rag_tools = [item for item in updates["tool_results"]["forensics"] if item.get("tool") == "case_rag_search"]
    assert rag_tools
    assert updates["forensics_result"]["case_rag"]["matches"][0]["case_id"] == "builtin-audio-scam"


def test_osint_records_case_rag_tool_result(monkeypatch):
    from app.agents.nodes import osint as osint_module

    async def fake_rag(*args, **kwargs):
        return {
            "tool": "case_rag_search",
            "status": "success",
            "degraded": False,
            "summary": "命中 1 个公开案例",
            "matches": [{"case_id": "builtin-mixed-phishing", "title": "钓鱼链接+伪造截图", "score": 0.81}],
        }

    async def fake_settle_tool(**kwargs):
        coro = kwargs.get("coro")
        if hasattr(coro, "close"):
            coro.close()
        return {
            "tool": kwargs["tool"],
            "target": kwargs["target"],
            "status": "success",
            "degraded": False,
            "result": {"results": []},
            "summary": "工具完成",
        }

    async def fake_interpret(*args, **kwargs):
        return "### 自主情报推理\n类案仅作参考。"

    monkeypatch.setattr(osint_module, "case_rag_search", fake_rag)
    monkeypatch.setattr(osint_module, "_settle_tool", fake_settle_tool)
    monkeypatch.setattr(osint_module, "osint_interpret", fake_interpret)
    monkeypatch.setattr(osint_module, "record_audit_event", lambda *args, **kwargs: None)

    updates = asyncio.run(osint_module.osint_node(
        {
            "task_id": "task-1",
            "input_type": "mixed",
            "case_prompt": "核验聊天截图和钓鱼链接",
            "current_round": 1,
            "phase_rounds": {"forensics": 1, "osint": 1, "commander": 1},
            "evidence_files": [],
            "forensics_result": {},
            "challenger_feedback": {},
            "tool_results": {},
        }
    ))

    rag_tools = [item for item in updates["tool_results"]["osint"] if item.get("tool") == "case_rag_search"]
    assert rag_tools
    assert updates["osint_result"]["case_rag"]["matches"][0]["case_id"] == "builtin-mixed-phishing"
