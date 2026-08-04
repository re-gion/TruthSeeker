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

    Stable reasoning requires Δ(t) < threshold and confidence > 0.8.
    round_count >= max_rounds is a hard guard to stop repeated retries.
    """
    if round_count >= max_rounds:
        return {
            "is_stable": False,
            "force_max_rounds": True,
            "reason": f"达到最大质询轮次 {max_rounds}，强制结束本阶段",
        }

    stable_delta = quality_delta is not None and quality_delta < threshold
    high_confidence = confidence > 0.8
    is_stable = bool(stable_delta and high_confidence)
    return {
        "is_stable": is_stable,
        "force_max_rounds": False,
        "stable_delta": stable_delta,
        "high_confidence": high_confidence,
        "reason": (
            "满足 Δ(t) 和置信度要求，推理趋于稳定"
            if is_stable
            else "未同时满足稳定收敛条件"
        ),
    }


def challenger_route(state: TruthSeekerState) -> str:
    """
    质询官路由：按当前阶段决定下一步。

    外部协议 key 仍是 forensics/osint/challenger/commander，但拓扑已从旧并行
    变为阶段式：forensics → challenger → osint → challenger → commander → end。
    """
    feedback = state.get("challenger_feedback") or {}
    phase = state.get("analysis_phase") or "forensics"

    if feedback.get("requires_more_evidence", False):
        target_agent = feedback.get("target_agent") or phase
        return target_agent if target_agent in PHASE_SEQUENCE and target_agent != "complete" else "forensics"

    return PHASE_SEQUENCE.get(phase, "osint")
