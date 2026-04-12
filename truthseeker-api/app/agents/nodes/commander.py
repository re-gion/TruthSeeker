"""Commander Agent - 研判指挥Agent（终局裁决，支持四 Agent 全权重）"""
import asyncio
from datetime import datetime, timezone
from app.agents.state import TruthSeekerState, AgentLog


async def commander_node(state: TruthSeekerState) -> dict:
    """
    研判指挥Agent Agent（Layer 2 版本）：
    1. 汇总 Forensics + OSINT + Challenger 所有证据
    2. 动态权重评估（根据证据质量自适应调整）
    3. 生成最终裁决（真/假/存疑）
    4. 输出 agent_weights 用于收敛检测
    """
    round_num = state.get("current_round", 1)
    forensics = state.get("forensics_result") or {}
    osint = state.get("osint_result") or {}
    challenger = state.get("challenger_feedback") or {}
    evidence_board = state.get("evidence_board", [])
    previous_weights = state.get("agent_weights", {})  # 上一轮作为 previous

    logs: list[AgentLog] = []

    def log(log_type: str, content: str) -> AgentLog:
        entry: AgentLog = {
            "agent": "commander",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(entry)
        return entry

    await asyncio.sleep(0.3)
    log("thinking", f"🏛️  研判指挥Agent启动（第 {round_num} 轮终局裁决）...")
    log("thinking", f"📊 接收到 {len(evidence_board)} 条证据，开始四维权重综合评估...")

    await asyncio.sleep(0.8)

    # ─── 提取各 Agent 的评分 ───
    forensics_confidence = forensics.get("confidence", 0.5)
    forensics_is_deepfake = forensics.get("is_deepfake", False)
    deepfake_prob = forensics.get("deepfake_probability", 0.5)

    osint_threat_score = osint.get("threat_score", 0.0)
    osint_confidence = osint.get("confidence", 0.75)
    osint_is_malicious = osint.get("is_malicious", False)

    challenger_quality = challenger.get("quality_score", 1.0)
    challenger_issue_count = challenger.get("issue_count", 0)

    # ─── 动态权重计算 ───
    # 基础权重
    base_forensics_w = 0.55
    base_osint_w = 0.30
    base_challenger_w = 0.15

    # 根据质询官质量分数调整法医权重
    if challenger_quality < 0.6:
        # 质询官发现了较多问题，降低法医权重
        forensics_w = base_forensics_w * challenger_quality
        osint_w = base_osint_w + (base_forensics_w - forensics_w) * 0.7
        challenger_w = base_challenger_w + (base_forensics_w - forensics_w) * 0.3
    else:
        forensics_w = base_forensics_w
        osint_w = base_osint_w
        challenger_w = base_challenger_w

    # 归一化
    total_w = forensics_w + osint_w + challenger_w
    forensics_w /= total_w
    osint_w /= total_w
    challenger_w /= total_w

    log("action", f"⚖️  动态权重 → 法医: {forensics_w:.1%} | OSINT: {osint_w:.1%} | 质询: {challenger_w:.1%}")

    await asyncio.sleep(0.5)

    # ─── 综合评分 ───
    # Forensics 贡献：deepfake 概率 * 法医权重
    forensics_contribution = deepfake_prob * forensics_w

    # OSINT 贡献：威胁分数 * osint 权重
    osint_contribution = osint_threat_score * osint_w

    # 质询官贡献：问题数量（越多问题，综合可疑度越高）
    challenger_contribution = min(0.3, challenger_issue_count * 0.1) * challenger_w

    # 综合可疑分数
    combined_suspicion = forensics_contribution + osint_contribution + challenger_contribution
    overall_confidence = max(0.5, 1 - abs(combined_suspicion - 0.5))

    log("action", f"📈 综合可疑分 = {combined_suspicion:.3f} (法医:{forensics_contribution:.3f} OSINT:{osint_contribution:.3f})")

    await asyncio.sleep(0.3)

    # ─── 最终裁决 ───
    # 法医和 OSINT 联合判断
    both_suspicious = forensics_is_deepfake and osint_is_malicious
    forensics_strong = forensics_is_deepfake and deepfake_prob > 0.75
    osint_strong = osint_is_malicious and osint_threat_score > 0.7

    if both_suspicious or combined_suspicion > 0.7:
        verdict = "forged"
        verdict_label = "⛔ 确认伪造"
        verdict_cn = "多维度证据一致表明：内容为 AI 生成/深度伪造，具有高可信度"
        overall_confidence = max(0.75, combined_suspicion)
    elif forensics_strong or osint_strong or combined_suspicion > 0.5:
        verdict = "suspicious"
        verdict_label = "⚠️  存疑"
        verdict_cn = "存在伪造嫌疑，部分关键指标异常，建议人工复核"
        overall_confidence = max(0.6, combined_suspicion)
    elif not forensics_is_deepfake and forensics_confidence > 0.75 and osint_threat_score < 0.3:
        verdict = "authentic"
        verdict_label = "✅ 确认真实"
        verdict_cn = "法医与情报分析均未发现伪造痕迹，来源可信度高"
        overall_confidence = forensics_confidence
    else:
        verdict = "inconclusive"
        verdict_label = "❓ 无法判定"
        verdict_cn = "现有证据不足以作出确定性判断，建议获取更多样本"
        overall_confidence = 0.5

    # ─── 生成关键证据列表 ───
    key_evidence = []
    if forensics:
        key_evidence.append(f"法医鉴定：Deepfake 概率 {deepfake_prob:.1%}（置信度 {forensics_confidence:.1%}）")
    if osint:
        key_evidence.append(f"OSINT 溯源：威胁评分 {osint_threat_score:.1%}，{'发现恶意指标' if osint_is_malicious else '未见明显威胁'}")
    if challenger.get("issues_found"):
        key_evidence.append(f"质询记录：{challenger_issue_count} 个质疑点，证据质量 {challenger_quality:.1%}")

    # ─── 当前权重（用于下一轮收敛检查）───
    current_weights = {
        "forensics": forensics_w,
        "osint": osint_w,
        "challenger": challenger_w,
        "combined_suspicion": combined_suspicion,
    }

    # ─── 日志 ───
    log("finding", f"📊 综合可疑度: {combined_suspicion:.1%} | 综合置信度: {overall_confidence:.1%}")
    log("finding", f"🔍 Deepfake 概率: {deepfake_prob:.1%} | 威胁评分: {osint_threat_score:.1%}")

    await asyncio.sleep(0.3)

    final_verdict = {
        "verdict": verdict,
        "verdict_label": verdict_label,
        "verdict_cn": verdict_cn,
        "confidence_overall": overall_confidence,
        "combined_suspicion": combined_suspicion,
        "deepfake_probability": deepfake_prob,
        "threat_score": osint_threat_score,
        "key_evidence": key_evidence,
        "recommendations": _generate_recommendations(verdict, challenger),
        "agent_weights_used": current_weights,
        "forensics_verdict": forensics.get("is_deepfake"),
        "osint_verdict": osint.get("is_malicious"),
        "round_completed": round_num,
        "total_evidence": len(evidence_board),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 置信度历史
    confidence_scores = {
        "forensics": forensics_confidence,
        "osint": osint_confidence,
        "combined": overall_confidence,
    }

    log("conclusion", f"🏛️  最终裁决：{verdict_label}")
    log("conclusion", f"📋 {verdict_cn}")
    log("conclusion", f"🔒 综合置信度: {overall_confidence:.1%} | 辩论轮次: {round_num}")
    log("conclusion", "✨ 全维度分析完成，报告已生成。")

    return {
        "final_verdict": final_verdict,
        "agent_weights": current_weights,
        "previous_weights": previous_weights,
        "is_converged": True,
        "termination_reason": f"commander_verdict_round_{round_num}",
        "logs": logs,
        "confidence_history": [
            {"round": round_num, "scores": confidence_scores}
        ],
    }


def _generate_recommendations(verdict: str, challenger: dict) -> list[str]:
    """根据裁决结果生成建议"""
    recs = []
    if verdict == "forged":
        recs.append("立即停止传播，向平台举报该内容")
        recs.append("保留原始文件与分析报告，以备法律取证")
    elif verdict == "suspicious":
        recs.append("建议人工专家复核，核实来源渠道")
        recs.append("对照可信来源进行二次核查")
    elif verdict == "authentic":
        recs.append("内容通过多维度验证，可正常使用")
    else:
        recs.append("获取更多样本进行对比分析")
        recs.append("考虑引入专家人工鉴别")

    if challenger.get("high_severity_count", 0) > 0:
        recs.append("注意：质询官发现高严重度争议点，请参阅详细报告")

    return recs
