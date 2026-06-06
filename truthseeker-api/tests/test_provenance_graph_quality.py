import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_graph_cites_files_tools_external_sources_and_rag_chunks():
    from app.agents.tools.provenance_graph import build_provenance_graph

    graph = build_provenance_graph(
        task_id="task-graph",
        evidence_files=[
            {
                "id": "file-1",
                "name": "notice.txt",
                "modality": "text",
                "mime_type": "text/plain",
                "sha256": "abc123",
            }
        ],
        forensics_result={
            "tool_results": [
                {
                    "tool": "ai_text_detector",
                    "target": "uploaded_text",
                    "status": "success",
                    "confidence": 0.82,
                    "summary": "内部文本 AIGC 概率 78%",
                    "result": {"provider": "internal_text_detector", "ai_probability": 0.78},
                }
            ]
        },
        osint_result={
            "search_results": [
                {
                    "title": "Halifax phishing analysis",
                    "url": "https://example.invalid/halifax",
                    "summary": "公开来源说明 Halifax 品牌钓鱼手法。",
                    "score": 0.74,
                }
            ],
            "tool_results": [
                {
                    "tool": "virustotal_osint_ioc",
                    "target": "https://halifax.example.invalid",
                    "status": "success",
                    "confidence": 0.88,
                    "summary": "VirusTotal 标记为恶意 URL",
                    "result": {"threat_score": 0.91},
                },
                {
                    "tool": "case_rag_search",
                    "target": "halifax phishing",
                    "status": "success",
                    "summary": "命中 1 个公开案例 RAG 片段",
                    "matches": [
                        {
                            "case_id": "case-1",
                            "title": "相似品牌钓鱼案例",
                            "chunk_id": "chunk-1",
                            "snippet": "相似案例包含伪装安全验证页面。",
                            "score": 0.66,
                            "source_kind": "public",
                        }
                    ],
                },
                {
                    "tool": "experience_rag_search",
                    "target": "halifax phishing",
                    "status": "success",
                    "summary": "命中 1 条个人经验库条目",
                    "matches": [
                        {
                            "entry_id": "exp-1",
                            "title": "品牌钓鱼补证路径",
                            "chunk_id": "exp-chunk-1",
                            "snippet": "先核验域名注册与品牌官方域名关系。",
                            "score": 0.71,
                        }
                    ],
                },
            ],
            "model_claims": [
                {
                    "id": "claim-1",
                    "label": "文本包含伪装 Halifax 的安全验证诱导。",
                    "confidence": 0.7,
                    "citation_ids": [],
                }
            ],
        },
        challenger_feedback={"quality_score": 0.72, "issues_found": []},
    )

    citations = graph["citations"]
    assert {item.get("source_kind") for item in citations} >= {
        "uploaded_file",
        "tool_result",
        "external_source",
        "case_rag",
        "experience_rag",
    }

    claim_nodes = [node for node in graph["nodes"] if node.get("type") == "claim"]
    assert claim_nodes
    assert all(node.get("citation_ids") for node in claim_nodes)
    assert graph["quality"]["citation_coverage"] >= 0.60
    assert graph["quality"]["model_inferred_ratio"] <= 0.35
