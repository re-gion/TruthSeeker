def test_report_renders_case_rag_success_section():
    from app.services.report_generator import _build_case_rag_sections

    sections = _build_case_rag_sections(
        {
            "tool": "case_rag_search",
            "status": "success",
            "matches": [
                {
                    "case_id": "builtin-audio-scam",
                    "title": "董事长语音诈骗",
                    "score": 0.86,
                    "source_kind": "builtin",
                    "snippet": "历史案例中出现高管语音克隆与转账诱导。",
                }
            ],
        },
        {
            "tool": "case_rag_search",
            "status": "success",
            "matches": [],
            "summary": "未命中相似公开案例",
        },
    )

    text = "\n".join(sections)
    assert "公开案例 RAG 仅作类案参考" in text
    assert "董事长语音诈骗" in text
    assert "仅作类案参考" in text
    assert "未命中相似公开案例" in text


def test_report_renders_case_rag_degraded_section():
    from app.services.report_generator import _build_case_rag_sections

    sections = _build_case_rag_sections(
        {
            "tool": "case_rag_search",
            "status": "degraded",
            "degraded": True,
            "summary": "Embedding 服务不可用",
            "matches": [],
        },
        None,
    )

    text = "\n".join(sections)
    assert "Embedding 服务不可用" in text
    assert "不影响当前检材的独立鉴伪与溯源流程" in text
