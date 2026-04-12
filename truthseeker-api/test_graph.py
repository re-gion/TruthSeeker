"""Quick test for Layer 2 四 Agent LangGraph execution"""
import asyncio
import sys
sys.path.insert(0, '.')


async def test():
    from app.agents.graph import compiled_graph

    state = {
        "task_id": "test-layer2-001",
        "user_id": "test",
        "input_files": {"primary": "mock://test.mp4"},
        "input_type": "video",
        "priority_focus": "balanced",
        "current_round": 1,
        "max_rounds": 3,
        "convergence_threshold": 0.05,
        "forensics_result": None,
        "osint_result": None,
        "challenger_feedback": None,
        "final_verdict": None,
        "agent_weights": {},
        "previous_weights": {},
        "evidence_board": [],
        "confidence_history": [],
        "challenges": [],
        "logs": [],
        "is_converged": False,
        "termination_reason": None,
    }

    print("=== Layer 2 四 Agent 辩论测试 ===\n")
    node_order = []

    async for chunk in compiled_graph.astream(state, stream_mode="updates"):
        for node, updates in chunk.items():
            node_order.append(node)
            print(f"\n[NODE:{node.upper()}]")
            for log in updates.get("logs", []):
                print(f"  [{log['agent']:10}] [{log['type']:10}] {log['content'][:80]}")

            if updates.get("forensics_result"):
                r = updates["forensics_result"]
                print(f"  >> 法医结果: deepfake={r.get('is_deepfake')} prob={r.get('deepfake_probability', 0):.1%}")

            if updates.get("osint_result"):
                r = updates["osint_result"]
                print(f"  >> OSINT结果: threat={r.get('threat_score', 0):.1%} malicious={r.get('is_malicious')}")

            if updates.get("challenger_feedback"):
                r = updates["challenger_feedback"]
                print(f"  >> 质询结果: issues={r.get('issue_count')} requires_review={r.get('requires_more_evidence')}")

            if updates.get("final_verdict"):
                v = updates["final_verdict"]
                print(f"\n  ===== FINAL VERDICT =====")
                print(f"  裁决: {v.get('verdict_label')}")
                print(f"  置信度: {v.get('confidence_overall', 0):.1%}")
                print(f"  说明: {v.get('verdict_cn')}")
                print(f"  证据数: {v.get('total_evidence', 0)}")
                weights = v.get("agent_weights_used", {})
                if weights:
                    print(f"  权重: 法医={weights.get('forensics', 0):.1%} OSINT={weights.get('osint', 0):.1%}")
                print(f"  =========================")

    print(f"\n✅ 完成，节点执行顺序: {' → '.join(node_order)}")


asyncio.run(test())
