"""Commander Agent - 研判指挥Agent，负责综合所有证据做出最终裁决 + LLM 推理"""
from datetime import datetime, timezone

from app.agents.state import TruthSeekerState, EvidenceItem, AgentLog
from app.agents.tools.llm_client import build_sample_references, commander_ruling
from app.agents.tools.provenance_graph import build_provenance_graph
from app.services.audit_log import record_audit_event


async def commander_node(state: TruthSeekerState) -> dict:
    """
    研判指挥Agent：
    1. 综合所有 Agent 的评估结果
    2. 计算加权置信度
    3. 使用 LLM 生成专业裁决报告
    4. 生成最终判决
    """
    task_id = state["task_id"]
    round_num = state.get("current_round", 1)
    forensics = state.get("forensics_result") or {}
    osint = state.get("osint_result") or {}
    challenger = state.get("challenger_feedback") or {}
    evidence_board = state.get("evidence_board", [])
    expert_messages = state.get("expert_messages", [])
    confirmed_consultation_summary = state.get("confirmed_consultation_summary")
    case_prompt = state.get("case_prompt", "")
    sample_refs = build_sample_references(state.get("evidence_files") or [])
    phase_residual_risks = list(state.get("phase_residual_risks") or [])

    logs: list[AgentLog] = []
    timeline_events: list[dict] = []

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

    log("thinking", f"👑 研判指挥Agent 启动，开始综合电子取证、情报图谱和质询过程...")
    log("thinking", f"📊 证据板共 {len(evidence_board)} 条，质询官报告 {challenger.get('issue_count', 0)} 个问题")
    if case_prompt:
        log("thinking", f"🎯 全局检测目标: {case_prompt[:120]}")
    if expert_messages:
        log("thinking", f"💬 纳入 {len(expert_messages)} 条专家会诊意见")
    if confirmed_consultation_summary:
        summary_text = confirmed_consultation_summary.get("confirmed_summary") if isinstance(confirmed_consultation_summary, dict) else None
        if summary_text:
            log("thinking", f"🧑‍⚖️ 纳入用户确认的会诊摘要: {summary_text[:160]}")

    # === 加权计算（保留数值计算的确定性） ===
    forensics_conf = forensics.get("confidence", 0.5)
    forensics_deepfake_prob = forensics.get("deepfake_probability", 0.5)
    forensics_is_deepfake = forensics.get("is_deepfake", False)
    osint_threat = osint.get("threat_score", 0.0)
    osint_risk = max(osint_threat, osint.get("text_risk_score", 0.0), osint.get("social_engineering_score", 0.0))
    osint_conf = osint.get("confidence", 0.75)
    quality_score = challenger.get("quality_score", 0.8)

    # 动态权重：依据各 Agent 的置信度和降级状态调整
    forensics_weight = 0.45 if not forensics.get("degraded") else 0.25
    osint_weight = 0.30 if not osint.get("degraded") else 0.15
    challenger_weight = 1.0 - forensics_weight - osint_weight

    agent_weights = {
        "forensics": forensics_weight,
        "osint": osint_weight,
        "challenger": challenger_weight,
    }

    # 综合评分
    deepfake_score = (
        forensics_deepfake_prob * forensics_weight
        + osint_risk * osint_weight
    )
    overall_risk_score = max(deepfake_score, osint_risk)

    # 质询官调节：质量问题降低置信度
    confidence_adjustment = quality_score
    overall_confidence = (
        (forensics_conf * forensics_weight + osint_conf * osint_weight)
        * confidence_adjustment
    )

    log("action", f"⚖️  权重配置: 法医={forensics_weight:.0%} | OSINT={osint_weight:.0%} | 质询={challenger_weight:.0%}")
    log("action", f"📈 伪造评分: {deepfake_score:.1%} | 综合风险: {overall_risk_score:.1%} | 综合置信度: {overall_confidence:.1%} | 证据质量: {quality_score:.1%}")

    # 判决逻辑
    if (deepfake_score > 0.65 and overall_confidence > 0.6) or (
        osint_risk > 0.75 and osint_conf > 0.5 and quality_score > 0.45
    ):
        verdict = "forged"
        verdict_cn = "伪造"
    elif (
        deepfake_score > 0.4
        or osint_risk > 0.4
        or osint.get("is_suspicious", False)
        or (forensics_is_deepfake and overall_confidence > 0.5)
    ):
        verdict = "suspicious"
        verdict_cn = "可疑"
    elif overall_confidence > 0.5:
        verdict = "authentic"
        verdict_cn = "真实"
    else:
        verdict = "inconclusive"
        verdict_cn = "无法判定"

    log("finding", f"🏁 初步裁决: {verdict_cn}，综合置信度: {overall_confidence:.1%}")

    # === LLM 最终裁决报告 ===
    llm_ruling = ""
    log("action", "🧠 正在调用大模型生成最终裁决报告...")
    try:
        enriched_challenger = {
            **challenger,
            "expert_messages": expert_messages[:10],
            "confirmed_consultation_summary": confirmed_consultation_summary,
        }
        llm_ruling = await commander_ruling(forensics, osint, enriched_challenger, agent_weights, case_prompt, sample_refs)
        if llm_ruling.startswith("[LLM降级]"):
            log("action", "⚠️  LLM 裁决不可用，使用规则推断")
        else:
            log("finding", f"🧠 LLM 裁决报告生成完成，{len(llm_ruling)} 字")
    except Exception as e:
        llm_ruling = f"[LLM降级] 裁决推理异常: {e}"
        log("action", f"⚠️  LLM 裁决异常: {e}")

    provenance_graph = osint.get("provenance_graph") or state.get("provenance_graph") or {}

    # 构建最终裁决
    final_verdict = {
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "confidence": overall_confidence,
        "deepfake_score": deepfake_score,
        "risk_score": overall_risk_score,
        "quality_score": quality_score,
        "agent_weights": agent_weights,
        "forensics_summary": {
            "is_deepfake": forensics_is_deepfake,
            "confidence": forensics_conf,
            "model_used": forensics.get("model_used", "unknown"),
            "degraded": forensics.get("degraded", False),
        },
        "osint_summary": {
            "threat_score": osint_threat,
            "risk_score": osint_risk,
            "social_engineering_score": osint.get("social_engineering_score", 0.0),
            "confidence": osint_conf,
            "is_malicious": osint.get("is_malicious", False),
            "is_suspicious": osint.get("is_suspicious", False),
            "degraded": osint.get("degraded", False),
        },
        "challenger_summary": {
            "issue_count": challenger.get("issue_count", 0),
            "quality_score": quality_score,
            "consultation_required": challenger.get("consultation_required", False),
            "consultation_resumed": challenger.get("consultation_resumed", False),
        },
        "provenance_graph": provenance_graph,
        "provenance_summary": {
            "node_count": len(provenance_graph.get("nodes") or []) if isinstance(provenance_graph, dict) else 0,
            "edge_count": len(provenance_graph.get("edges") or []) if isinstance(provenance_graph, dict) else 0,
            "citation_count": len(provenance_graph.get("citations") or []) if isinstance(provenance_graph, dict) else 0,
            "quality": provenance_graph.get("quality") if isinstance(provenance_graph, dict) else {},
        },
        "residual_risks": phase_residual_risks + (challenger.get("residual_risks") or []),
        "case_prompt": case_prompt,
        "expert_message_count": len(expert_messages),
        "consultation_summary": confirmed_consultation_summary,
        "consultation_key_quotes": (
            confirmed_consultation_summary.get("key_quotes", [])
            if isinstance(confirmed_consultation_summary, dict)
            else []
        ),
        "key_evidence": [
            {"type": e.get("type"), "source": e.get("source"), "confidence": e.get("confidence")}
            for e in evidence_board[:5]
        ],
        "recommendations": _generate_recommendations(verdict, forensics, osint, challenger),
        "llm_ruling": llm_ruling,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    final_graph = build_provenance_graph(
        task_id=task_id,
        evidence_files=state.get("evidence_files") or [],
        forensics_result=forensics,
        osint_result=osint,
        challenger_feedback=challenger,
        final_verdict=final_verdict,
    )
    final_verdict["provenance_graph"] = final_graph
    final_verdict["provenance_summary"] = {
        "node_count": len(final_graph.get("nodes") or []),
        "edge_count": len(final_graph.get("edges") or []),
        "citation_count": len(final_graph.get("citations") or []),
        "quality": final_graph.get("quality") or {},
    }

    log("conclusion", f"👑 最终裁决: 【{verdict_cn}】 综合置信度 {overall_confidence:.1%}")
    record_audit_event(
        action="commander.verdict",
        task_id=task_id,
        agent="commander",
        metadata={
            "verdict": verdict,
            "confidence": overall_confidence,
            "deepfake_score": deepfake_score,
            "forensics_degraded": forensics.get("degraded", False),
            "osint_degraded": osint.get("degraded", False),
        },
    )
    log("conclusion", f"📋 裁决报告已存档，任务 {task_id} 分析完成")

    # 时间轴关键事件
    timeline_events.append({
        "round": round_num,
        "agent": "commander",
        "event_type": "verdict",
        "summary": f"最终裁决: {verdict_cn} (置信度 {overall_confidence:.1%})",
    })

    return {
        "final_verdict": final_verdict,
        "analysis_phase": "commander",
        "provenance_graph": final_graph,
        "agent_weights": agent_weights,
        "previous_weights": state.get("agent_weights", {}),
        "evidence_board": [],
        "logs": logs,
        "is_converged": True,
        "termination_reason": "commander_ruling",
        "timeline_events": timeline_events,
    }


def _generate_recommendations(
    verdict: str, forensics: dict, osint: dict, challenger: dict
) -> list[str]:
    """基于裁决结果生成建议"""
    recs = []

    if verdict == "forged":
        recs.append("建议立即下架该媒体内容并启动溯源调查")
        recs.append("建议提取原始文件进行逆向分析，追踪生成工具")
        if forensics.get("audio_score") is not None:
            recs.append("音频轨道存在异常，建议单独进行声纹比对分析")
    elif verdict == "suspicious":
        recs.append("建议进行人工复核，结合上下文进一步验证")
        recs.append("建议使用不同检测工具交叉验证")
        if challenger.get("issue_count", 0) > 0:
            recs.append("质询官发现证据不足之处，建议补充更多检测维度")
    elif verdict == "authentic":
        recs.append("媒体内容经多维度检测判定为真实，可正常使用")
        recs.append("建议定期复检以应对新型伪造技术")
    else:
        recs.append("当前证据不足以做出明确判定，建议人工专家介入")
        recs.append("建议收集更多样本数据进行对比分析")

    if forensics.get("degraded"):
        recs.append("⚠️ 法医分析处于降级模式，结果可靠性降低，建议重新检测")
    if osint.get("degraded"):
        recs.append("⚠️ 情报溯源处于降级模式，外部威胁情报未完整获取，建议网络恢复后复检")

    return recs
