import unittest


class RebuiltWorkflowContractTests(unittest.TestCase):
    def test_normalize_final_verdict_preserves_provenance_graph(self):
        from app.services.analysis_persistence import normalize_final_verdict

        graph = {
            "nodes": [{"id": "artifact:file-1", "type": "artifact", "label": "clip.mp4"}],
            "edges": [],
            "citations": [{"id": "file:file-1", "source_name": "上传检材"}],
            "quality": {"completeness": 0.8},
        }

        normalized = normalize_final_verdict(
            {
                "verdict": "suspicious",
                "confidence": 0.72,
                "llm_ruling": "存在跨模态疑点",
                "provenance_graph": graph,
            }
        )

        self.assertEqual(normalized["provenance_graph"], graph)
        self.assertEqual(normalized["total_evidence"], 0)

    def test_build_provenance_graph_marks_model_inferred_edges(self):
        from app.agents.tools.provenance_graph import build_provenance_graph

        graph = build_provenance_graph(
            task_id="task-1",
            evidence_files=[
                {
                    "id": "file-1",
                    "name": "claim.txt",
                    "modality": "text",
                    "mime_type": "text/plain",
                    "size_bytes": 120,
                    "storage_path": "cases/claim.txt",
                }
            ],
            forensics_result={
                "tool_results": [
                    {
                        "tool": "virustotal_file_hash",
                        "status": "success",
                        "target": "claim.txt",
                        "result": {"hash": "abc123", "scan_available": False},
                    }
                ]
            },
            osint_result={
                "search_results": [
                    {
                        "title": "公开报道",
                        "url": "https://example.invalid/report",
                        "summary": "与声明相关的公开信息",
                        "retrieved_at": "2026-04-28T00:00:00+00:00",
                    }
                ],
                "model_claims": [
                    {
                        "id": "claim-1",
                        "label": "样本疑似引用公开报道",
                        "confidence": 0.61,
                        "citation_ids": [],
                    }
                ],
            },
            challenger_feedback={"quality_score": 0.78, "issues_found": []},
        )

        self.assertGreaterEqual({node["type"] for node in graph["nodes"]}, {"artifact", "source", "claim"})
        self.assertEqual(graph["citations"][0]["source_name"], "上传检材")
        self.assertTrue(any(edge.get("model_inferred") for edge in graph["edges"]))
        self.assertGreaterEqual(graph["quality"]["model_inferred_edges"], 1)


if __name__ == "__main__":
    unittest.main()
