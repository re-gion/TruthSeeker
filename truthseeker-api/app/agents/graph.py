"""LangGraph State Machine Workflow - Layer 2: 四 Agent 完整辩论拓扑（稳定串行版）

拓扑结构：
START → Forensics → OSINT → Challenger → 条件边
        ↑                       │
        └────────────────────── ┘ (打回重审，round+1，最多1次)
                                    │
                               Commander → END
"""
from langgraph.graph import StateGraph, START, END
from app.agents.state import TruthSeekerState
from app.agents.nodes.forensics import forensics_node
from app.agents.nodes.osint import osint_node
from app.agents.nodes.challenger import challenger_node
from app.agents.nodes.commander import commander_node
from app.agents.edges.conditions import challenger_route


def build_graph():
    """
    构建 Layer 2 四 Agent 工作流拓扑（串行稳定版）：
    
    START → Forensics → OSINT → Challenger →[条件边]
                ↑                  │ proceed_to_commander
                │                  └──→ Commander → END
                └── return_to_forensics (打回, round 递增)
    """
    graph = StateGraph(TruthSeekerState)

    # ─── 添加节点 ───
    graph.add_node("forensics", forensics_node)
    graph.add_node("osint", osint_node)
    graph.add_node("challenger", challenger_node)
    graph.add_node("commander", commander_node)

    # ─── 定义串行流程 ───
    # START → Forensics → OSINT → Challenger
    graph.add_edge(START, "forensics")
    graph.add_edge("forensics", "osint")
    graph.add_edge("osint", "challenger")

    # Challenger → 条件路由
    graph.add_conditional_edges(
        "challenger",
        challenger_route,
        {
            "proceed_to_commander": "commander",   # ✅ 通过审查，提交裁决
            "return_to_forensics": "forensics",    # ⟳ 打回法医重审（round+1 后自动收敛）
            "return_to_osint": "osint",            # ⟳ 打回 OSINT 重审
        },
    )

    # Commander → END
    graph.add_edge("commander", END)

    return graph.compile()


# 编译后的工作流（单例）
compiled_graph = build_graph()
