import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 报告渲染：代码围栏闭合
# ---------------------------------------------------------------------------

def test_balance_code_fences_closes_unclosed_fence():
    from app.services.report_generator import _balance_code_fences

    text = "正文\n```mermaid\nA --> B"
    balanced = _balance_code_fences(text)
    assert balanced.endswith("```")
    assert balanced.count("```") == 2


def test_balance_code_fences_keeps_balanced_text():
    from app.services.report_generator import _balance_code_fences

    text = "正文\n```\ncode\n```\n结尾"
    assert _balance_code_fences(text) == text


def test_balance_code_fences_handles_tilde_and_length():
    from app.services.report_generator import _balance_code_fences

    # 未闭合的 ~~~ 围栏应以同长度 ~~~ 闭合
    text = "~~~\ncontent"
    assert _balance_code_fences(text).endswith("~~~")
    # 更长的闭合围栏可以关闭较短的开围栏
    text2 = "````\ncontent\n````"
    assert _balance_code_fences(text2) == text2


def test_balance_code_fences_ignores_over_indented_fence():
    from app.services.report_generator import _balance_code_fences

    # 缩进超过 3 格不是围栏，不应触发补齐
    text = "正文\n    ```\n    缩进内容"
    assert _balance_code_fences(text) == text


def test_balance_code_fences_closes_before_next_heading():
    from app.services.report_generator import _balance_code_fences

    # 围栏未闭合但后文出现新标题：应在标题前闭合，让后续小节回到正文
    text = "```mermaid\nA --> B\n\n### 关联风险与复核建议\n\n- 建议人工复核"
    balanced = _balance_code_fences(text)
    assert balanced.count("```") == 2
    assert balanced.index("```", 3) < balanced.index("### 关联风险与复核建议")
    # 标题后没有再开围栏，整体围栏数为偶数且标题在后
    lines = balanced.split("\n")
    heading_index = lines.index("### 关联风险与复核建议")
    assert all(not line.startswith("```") for line in lines[heading_index:])


def test_render_markdown_field_truncation_keeps_fences_balanced():
    from app.services.report_generator import _render_markdown_field

    # 构造一个超长字段：开头开围栏，截断点落在围栏内部之后
    long_body = "x" * 6000
    value = f"```\n{long_body}"
    rendered = _render_markdown_field("llm_analysis", value)
    # 截断后必须补齐闭合围栏，围栏数量为偶数
    assert rendered.count("```") % 2 == 0


# ---------------------------------------------------------------------------
# Forensics / OSINT prompt 载荷有界摘要
# ---------------------------------------------------------------------------

def _big_forensics_payload():
    return {
        "is_aigc": True,
        "aigc_probability": 0.91,
        "confidence": 0.88,
        "degraded": False,
        "tool_matrix": [
            {
                "tool": "reality_defender",
                "target": "video.mp4",
                "status": "success",
                "degraded": False,
                "summary": "检测范围=仅视频音轨 aigc_probability=0.90",
                "result": {
                    "aigc_probability": 0.9,
                    "detection_scope": "audio_video_manipulation",
                    "analysis_scope": "audio_track_only",
                    "raw_response": {"blob": "y" * 200000},
                    "frame_inferences": [{"i": i} for i in range(500)],
                },
            },
            {
                "tool": "case_rag_search",
                "target": "forensics",
                "status": "success",
                "summary": "命中 1 个公开案例 RAG 片段",
                "result": {},
            },
        ],
        "text_samples": [{"name": "a.txt", "content": "z" * 9000}],
        "audio_transcripts": [{"target": "video.mp4", "text": "w" * 9000, "char_count": 9000}],
        "case_rag": {
            "status": "success",
            "summary": "命中",
            "matches": [{"title": "案例", "snippet": "s" * 900, "score": 0.8}],
        },
        "experience_rag": None,
        "timestamp": "2026-08-17T07:00:00+00:00",
    }


def test_forensics_prompt_summary_drops_raw_response_and_bounds_fields():
    from app.agents.tools.llm_client import _summarize_forensics_for_prompt

    summary = _summarize_forensics_for_prompt(_big_forensics_payload())
    # raw_response / frame_inferences 不得进入 prompt
    serialized = str(summary)
    assert "y" * 1000 not in serialized
    # 检测范围标注必须保留
    rd_tool = summary["tool_matrix"][0]
    assert rd_tool["result"]["analysis_scope"] == "audio_track_only"
    assert "仅视频音轨" in rd_tool["summary"]
    # RAG 工具不在工具列表重复（由顶层 case_rag 字段携带）
    assert all(item["tool"] != "case_rag_search" for item in summary["tool_matrix"])
    assert summary["case_rag"]["match_count"] == 1
    # 各文本字段被限长
    assert len(summary["text_samples"][0]["content"]) <= 4000
    assert len(summary["audio_transcripts"][0]["text"]) <= 3000
    assert len(summary["case_rag"]["matches"][0]["snippet"]) <= 400


def test_forensics_prompt_summary_is_small():
    import json

    from app.agents.tools.llm_client import _summarize_forensics_for_prompt

    summary = _summarize_forensics_for_prompt(_big_forensics_payload())
    # 原始 payload 约 20 万字符，摘要后应远小于 prompt 上限（18 万）
    assert len(json.dumps(summary, ensure_ascii=False, default=str)) < 20000


def test_osint_prompt_summary_bounds_whois_and_drops_raw():
    import json

    from app.agents.tools.llm_client import _summarize_osint_for_prompt

    payload = {
        "threat_score": 0.8,
        "confidence": 0.85,
        "degraded": False,
        "domain_provenance_summary": [
            {
                "domain": "evil.example",
                "status": "success",
                "summary": "新注册域名",
                "whois": {"raw": "w" * 50000, "createdDate": "2026-08-01"},
                "dns": {"a": ["1.2.3.4"]},
            }
        ],
        "tool_results": [
            {
                "tool": "whoisxml_domain_provenance",
                "target": "evil.example",
                "status": "success",
                "degraded": False,
                "summary": "域名溯源成功",
                "result": {"raw_response": {"blob": "v" * 100000}},
            }
        ],
        "virustotal_summary": [{"threat_score": 0.7, "indicators": ["恶意"] * 20}],
        "search_results": [{"title": "t", "url": "u", "summary": "s" * 900}],
        "timestamp": "2026-08-17T07:00:00+00:00",
    }
    summary = _summarize_osint_for_prompt(payload)
    serialized = json.dumps(summary, ensure_ascii=False, default=str)
    assert "w" * 1000 not in serialized
    assert "v" * 1000 not in serialized
    assert len(serialized) < 12000
    dp = summary["domain_provenance_summary"][0]
    assert dp["domain"] == "evil.example"
    # whois 被截断为有限长度
    assert len(str(dp["whois"])) <= 410
