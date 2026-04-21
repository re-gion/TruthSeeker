"""LangGraph State Machine Workflow - Layer 2: 四 Agent 完整辩论拓扑

拓扑结构：
START → Forensics ┐
                  ├→ Challenger → 条件边
START → OSINT ────┘       │
        ↑                 │
        └─────────────────┘ (打回重审，round+1)
                           │
                      Commander → END
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
    构建 Layer 2 四 Agent 工作流拓扑：
    
    START → Forensics ┐
                      ├→ Challenger →[条件边]
    START → OSINT ────┘      │ proceed_to_commander
              ↑              └──→ Commander → END
              └── return_to_* (打回, round 递增)
    """
    graph = StateGraph(TruthSeekerState)

    # ─── 添加节点 ───
    graph.add_node("forensics", forensics_node)
    graph.add_node("osint", osint_node)
    graph.add_node("challenger", challenger_node)
    graph.add_node("commander", commander_node)

    # ─── 定义并行流程 ───
    # START 同时进入 Forensics 与 OSINT，二者完成后进入 Challenger。
    graph.add_edge(START, "forensics")
    graph.add_edge(START, "osint")
    graph.add_edge(["forensics", "osint"], "challenger")

    # Challenger → 条件路由（返回节点名直接路由，支持 list 做 fan-out）
    graph.add_conditional_edges("challenger", challenger_route)

    # Commander → END
    graph.add_edge("commander", END)

    return graph.compile(checkpointer=checkpointer)


# 编译后的工作流（单例）
compiled_graph = build_graph()
