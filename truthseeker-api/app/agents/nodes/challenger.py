"""Challenger Agent - 逻辑质询Agent，负责审视证据充分性和逻辑矛盾"""
import asyncio
from datetime import datetime, timezone
from app.agents.state import TruthSeekerState, AgentLog


async def challenger_node(state: TruthSeekerState) -> dict:
    """
    逻辑质询Agent Agent：
    1. 审查 Forensics + OSINT 证据的一致性
    2. 检查置信度是否达到阈值
    3. 发现矛盾点时触发质疑，要求补充证据
    4. 判定是否需要打回重审或提交 Commander
    """
    round_num = state.get("current_round", 1)
    forensics = state.get("forensics_result") or {}
    osint = state.get("osint_result") or {}
    evidence_board = state.get("evidence_board", [])

    logs: list[AgentLog] = []
    challenges: list[dict] = []

    def log(log_type: str, content: str) -> AgentLog:
        entry: AgentLog = {
            "agent": "challenger",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(entry)
        return entry

    log("thinking", f"⚖️  逻辑质询Agent Agent 启动（第 {round_num} 轮）...")
    log("thinking", f"📋 接收到 {len(evidence_board)} 条证据，开始交叉验证...")

    await asyncio.sleep(0.3)

    # 提取评分
    forensics_conf = forensics.get("confidence", 0.5)
    forensics_deepfake_prob = forensics.get("deepfake_probability", 0.5)
    forensics_is_deepfake = forensics.get("is_deepfake", False)
    osint_threat_score = osint.get("threat_score", 0.0)
    osint_conf = osint.get("confidence", 0.75)

    log("action", f"🔬 法医置信度: {forensics_conf:.1%} | OSINT 威胁: {osint_threat_score:.1%}")

    await asyncio.sleep(0.4)

    # 质疑逻辑
    issues_found = []
    requires_more_evidence = False
    target_agent = None

    # 检查 1: 法医置信度过低（< 0.65）
    if forensics_conf < 0.65:
        issue = {
            "type": "low_confidence",
            "agent": "forensics",
            "description": f"法医分析置信度偏低（{forensics_conf:.1%}），需要更多帧或更多模态数据",
            "severity": "high",
        }
        issues_found.append(issue)
        log("challenge", f"❓ 质疑法医结论：置信度 {forensics_conf:.1%} 低于阈值 65%，证据支撑不足")

    # 检查 2: Forensics 与 OSINT 结论明显矛盾
    if forensics_is_deepfake and osint_threat_score < 0.2:
        # 法医说是伪造，但 OSINT 没有发现威胁 - 可能是假阳性
        issue = {
            "type": "contradiction",
            "agents": ["forensics", "osint"],
            "description": "法医判定伪造，但 OSINT 未发现关联威胁情报，存在矛盾",
            "severity": "medium",
        }
        issues_found.append(issue)
        log("challenge", "⚡ 发现矛盾：法医认定伪造，但 OSINT 情报未见异常，需进一步核查")

    elif not forensics_is_deepfake and osint_threat_score > 0.7:
        # 法医说是真实，但 OSINT 发现高威胁 - 需要核查
        issue = {
            "type": "contradiction",
            "agents": ["forensics", "osint"],
            "description": "法医未检测伪造，但 OSINT 发现高度威胁情报，存在矛盾",
            "severity": "high",
        }
        issues_found.append(issue)
        log("challenge", "🚨 严重矛盾：法医未发现伪造，但 OSINT 高度可疑！需重新审查法医报告")

    # 检查 3: 第一轮且只有一种模态证据
    visual_evidence = [e for e in evidence_board if e.get("type") in ("visual", "audio")]
    if round_num == 1 and len(visual_evidence) < 2 and forensics_conf < 0.8:
        issue = {
            "type": "insufficient_evidence",
            "agent": "forensics",
            "description": "证据维度不足，建议补充音频/图像分析",
            "severity": "low",
        }
        issues_found.append(issue)
        log("challenge", "📊 证据维度有限，建议扩充分析维度以提升判断可靠性")

    await asyncio.sleep(0.3)

    # 决定是否打回
    high_severity_issues = [i for i in issues_found if i["severity"] == "high"]
    medium_severity_issues = [i for i in issues_found if i["severity"] == "medium"]

    # 只有第一轮且有高严重度问题时打回（最多打回 1 次避免死循环）
    if round_num == 1 and len(high_severity_issues) >= 1:
        requires_more_evidence = True
        target_agent = high_severity_issues[0].get("agent", "forensics")
        log("challenge", f"⛔ 质询决定：证据不足，打回 {target_agent} 重审")
    else:
        requires_more_evidence = False
        if issues_found:
            log("action", f"📝 记录 {len(issues_found)} 个质疑点，但选择提交指挥官综合裁决")
        else:
            log("action", "✅ 证据审查通过，无重大矛盾，提交指挥官作出最终裁决")

    for issue in issues_found[:3]:
        challenges.append({
            "round": round_num,
            "issue": issue,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # 质询结论
    challenger_feedback = {
        "round": round_num,
        "issues_found": issues_found,
        "requires_more_evidence": requires_more_evidence,
        "target_agent": target_agent,
        "issue_count": len(issues_found),
        "high_severity_count": len(high_severity_issues),
        "medium_severity_count": len(medium_severity_issues),
        "quality_score": max(0.0, 1.0 - len(high_severity_issues) * 0.3 - len(medium_severity_issues) * 0.15),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    verdict_text = "打回重审" if requires_more_evidence else "通过审查"
    log("conclusion", f"⚖️  质询完成：{verdict_text} | 发现问题 {len(issues_found)} 个 | 证据质量: {challenger_feedback['quality_score']:.1%}")

    return {
        "challenger_feedback": challenger_feedback,
        "challenges": challenges,
        "logs": logs,
        # 轮次加 1
        "current_round": round_num + (1 if requires_more_evidence else 0),
    }
