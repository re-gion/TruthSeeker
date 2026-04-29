"""条件边逻辑 - 收敛判断与阶段路由"""
from app.agents.state import TruthSeekerState

PHASE_SEQUENCE = {
    "forensics": "osint",
    "osint": "commander",
    "commander": "end",
    "complete": "end",
}


def evaluate_phase_convergence(
    *,
    quality_delta: float | None,
    confidence: float,
    round_count: int,
    max_rounds: int,
    threshold: float,
) -> dict:
    """Evaluate the Challenger phase-stability gate.

    Stable reasoning requires all three user-visible gates:
    Δ(t) < threshold, confidence > 0.8, and round_count >= 2.
    round_count >= max_rounds is a hard guard to stop repeated retries.
    """
    if round_count >= max_rounds:
        return {
            "is_stable": False,
            "force_max_rounds": True,
            "reason": f"达到最大质询轮次 {max_rounds}，强制结束本阶段",
        }

    stable_delta = quality_delta is not None and quality_delta < threshold
    enough_rounds = round_count >= 2
    high_confidence = confidence > 0.8
    is_stable = bool(stable_delta and high_confidence and enough_rounds)
    return {
        "is_stable": is_stable,
        "force_max_rounds": False,
        "stable_delta": stable_delta,
        "high_confidence": high_confidence,
        "enough_rounds": enough_rounds,
        "reason": (
            "满足 Δ(t)、置信度和最小轮次要求，推理趋于稳定"
            if is_stable
            else "未同时满足稳定收敛条件"
        ),
    }


# NOTE: should_converge 当前未被 challenger_route 或 graph 使用（收敛逻辑由 commander 节点内联处理）。
# 保留此函数供未来 graph 重构时启用。
def should_converge(state: TruthSeekerState) -> str:
    """
    判断是否达到收敛条件：
    - "converge": 停止辩论，进入 Commander 裁决
    - "continue": 继续下一轮辩论
    返回值用于 LangGraph conditional edge routing
    """
    current_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 3)
    convergence_threshold = state.get("convergence_threshold", 0.08)
    confidence_history = state.get("confidence_history", [])
    current_weights = state.get("agent_weights", {})
    previous_weights = state.get("previous_weights", {})

    # 最大轮数兜底
    if current_round >= max_rounds:
        return "converge"

    # 强制至少运行 2 轮（如果质询官决定打回）
    if current_round < 2 and state.get("challenger_feedback", {}).get("requires_more_evidence"):
        return "continue"

    # 置信度历史收敛检查
    if len(confidence_history) >= 2:
        prev = confidence_history[-2].get("scores", {})
        curr = confidence_history[-1].get("scores", {})
        if prev and curr:
            deltas = [
                abs(curr.get(k, 0) - prev.get(k, 0))
                for k in set(prev) | set(curr)
            ]
            max_delta = max(deltas) if deltas else 1.0
            if max_delta < convergence_threshold and current_round >= 2:
                return "converge"

    # 权重变化收敛检查
    if current_weights and previous_weights:
        weight_deltas = [
            abs(current_weights.get(a, 0) - previous_weights.get(a, 0))
            for a in set(current_weights) | set(previous_weights)
        ]
        max_weight_delta = max(weight_deltas) if weight_deltas else 1.0
        if max_weight_delta < convergence_threshold and current_round >= 2:
            return "converge"

    return "continue"


def challenger_route(state: TruthSeekerState) -> str:
    """
    质询官路由：按当前阶段决定下一步。

    外部协议 key 仍是 forensics/osint/challenger/commander，但拓扑已从旧并行
    变为阶段式：forensics → challenger → osint → challenger → commander → challenger → end。
    """
    feedback = state.get("challenger_feedback") or {}
    phase = state.get("analysis_phase") or "forensics"

    if feedback.get("requires_more_evidence", False):
        target_agent = feedback.get("target_agent") or phase
        return target_agent if target_agent in PHASE_SEQUENCE and target_agent != "complete" else "forensics"

    return PHASE_SEQUENCE.get(phase, "osint")
