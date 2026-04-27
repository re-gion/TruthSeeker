"""LangGraph State Machine Workflow - 阶段式四 Agent 拓扑。

拓扑结构：
START → Forensics → Challenger → OSINT → Challenger → Commander → Challenger → END

Challenger 可按当前 phase 打回同一阶段重跑；Commander 阶段只允许重写最终报告，
不再重新打开取证或 OSINT 工具链。
"""
from langgraph.graph import StateGraph, START, END

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:  # pragma: no cover - LangGraph minor-version compatibility
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver

from app.agents.state import TruthSeekerState
from app.agents.nodes.forensics import forensics_node
from app.agents.nodes.osint import osint_node
from app.agents.nodes.challenger import challenger_node
from app.agents.nodes.commander import commander_node
from app.agents.edges.conditions import challenger_route


checkpointer = MemorySaver()


def build_graph():
    """
    构建阶段式四 Agent 工作流拓扑。
    """
    graph = StateGraph(TruthSeekerState)

    # ─── 添加节点 ───
    graph.add_node("forensics", forensics_node)
    graph.add_node("osint", osint_node)
    graph.add_node("challenger", challenger_node)
    graph.add_node("commander", commander_node)

    # ─── 定义阶段流程 ───
    graph.add_edge(START, "forensics")
    graph.add_edge("forensics", "challenger")
    graph.add_edge("osint", "challenger")
    graph.add_edge("commander", "challenger")

    # Challenger → 条件路由。
    graph.add_conditional_edges(
        "challenger",
        challenger_route,
        {
            "forensics": "forensics",
            "osint": "osint",
            "commander": "commander",
            "end": END,
        },
    )

    return graph.compile(checkpointer=checkpointer)


# 编译后的工作流（单例）
compiled_graph = build_graph()
