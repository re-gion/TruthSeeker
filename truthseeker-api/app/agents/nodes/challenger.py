"""Challenger Agent - 逻辑质询Agent，负责审视证据充分性和逻辑矛盾 + LLM 交叉验证"""
import asyncio
from datetime import datetime, timezone

from app.agents.state import TruthSeekerState, AgentLog
from app.agents.tools.llm_client import challenger_cross_validate
from app.utils.supabase_client import supabase

try:
    from langgraph.types import interrupt
except ImportError:  # pragma: no cover - only used when LangGraph is installed
    interrupt = None


async def challenger_node(state: TruthSeekerState) -> dict:
    """
    逻辑质询Agent Agent：
    1. 审查 Forensics + OSINT 证据的一致性（规则检查 + LLM 推理）
    2. 检查置信度是否达到阈值
    3. 发现矛盾点时触发质疑，要求补充证据
    4. 判定是否需要打回重审或提交 Commander
    """
    task_id = state["task_id"]
    round_num = state.get("current_round", 1)
    forensics = state.get("forensics_result") or {}
    osint = state.get("osint_result") or {}
    evidence_board = state.get("evidence_board", [])
    existing_challenges = state.get("challenges", [])
    expert_messages = state.get("expert_messages", [])
    case_prompt = state.get("case_prompt", "")

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
    if case_prompt:
        log("thinking", f"🎯 全局检测目标: {case_prompt[:120]}")

    # 如果有专家消息，体现出来
    if expert_messages:
        log("thinking", f"💬 检测到 {len(expert_messages)} 条专家意见，将纳入交叉验证")

    # 从 Supabase 读取新的专家会诊消息（除了 state 中已有的）
    try:
        known_ids = {m.get("id") for m in expert_messages if m.get("id")}
        resp = supabase.table("consultation_messages").select("*").eq("task_id", task_id).order("created_at", desc=False).execute()
        new_expert_messages = [
            m for m in (resp.data or [])
            if m.get("id") not in known_ids
        ]
        if new_expert_messages:
            all_expert = expert_messages + new_expert_messages
            log("thinking", f"💬 从数据库读取到 {len(new_expert_messages)} 条新专家意见")
            for m in new_expert_messages[:3]:
                log("finding", f"💬 专家意见 [{m.get('role', 'expert')}]: {m.get('message', '')[:80]}...")
            expert_messages = all_expert
    except Exception as e:
        log("action", f"⚠️  读取专家意见失败: {e}")

    # 提取评分
    forensics_conf = forensics.get("confidence", 0.5)
    forensics_deepfake_prob = forensics.get("deepfake_probability", 0.5)
    forensics_is_deepfake = forensics.get("is_deepfake", False)
    osint_threat_score = osint.get("threat_score", 0.0)
    osint_conf = osint.get("confidence", 0.75)

    log("action", f"🔬 法医置信度: {forensics_conf:.1%} | OSINT 威胁: {osint_threat_score:.1%}")

    # === 规则检查（快速、确定性） ===
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
        issue = {
            "type": "contradiction",
            "agents": ["forensics", "osint"],
            "description": "法医判定伪造，但 OSINT 未发现关联威胁情报，存在矛盾",
            "severity": "medium",
        }
        issues_found.append(issue)
        log("challenge", "⚡ 发现矛盾：法医认定伪造，但 OSINT 情报未见异常，需进一步核查")

    elif not forensics_is_deepfake and osint_threat_score > 0.7:
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

    # === LLM 深度交叉验证 ===
    llm_cross_validation = ""
    if forensics and osint:
        log("action", "🧠 正在调用大模型进行深度交叉验证...")
        try:
            llm_cross_validation = await challenger_cross_validate(
                forensics, osint, existing_challenges, case_prompt
            )
            if llm_cross_validation.startswith("[LLM降级]"):
                log("action", "⚠️  LLM 交叉验证不可用，仅依赖规则检查")
            else:
                log("finding", f"🧠 LLM 交叉验证完成，生成 {len(llm_cross_validation)} 字分析报告")
                # LLM 可能发现额外的矛盾或异常
                # 检查是否 LLM 提到了新的矛盾点
                if any(kw in llm_cross_validation for kw in ["矛盾", "不一致", "冲突", "异常"]):
                    if not any(i["type"] == "llm_contradiction" for i in issues_found):
                        issues_found.append({
                            "type": "llm_contradiction",
                            "agent": "challenger",
                            "description": "LLM 交叉验证发现潜在矛盾或不一致，需要关注",
                            "severity": "medium",
                        })
                        log("finding", "🧠 LLM 发现了规则检查未覆盖的潜在矛盾")
        except Exception as e:
            llm_cross_validation = f"[LLM降级] 交叉验证异常: {e}"
            log("action", f"⚠️  LLM 交叉验证异常: {e}")

    # 决定是否打回
    high_severity_issues = [i for i in issues_found if i["severity"] == "high"]
    medium_severity_issues = [i for i in issues_found if i["severity"] == "medium"]
    consultation_required = bool(round_num == 1 and high_severity_issues)
    consultation_resumed = False
    consultation_resume_payload = None

    if consultation_required and interrupt is not None:
        consultation_payload = {
            "type": "consultation_required",
            "task_id": task_id,
            "round": round_num,
            "reason": high_severity_issues[0].get("description", "发现高冲突证据，需要专家会诊"),
            "issues": high_severity_issues,
            "case_prompt": case_prompt,
        }
        log("challenge", "🧑‍⚖️  高冲突证据触发专家会诊，等待主持人恢复研判")
        consultation_resume_payload = interrupt(consultation_payload)
        consultation_resumed = True
        if isinstance(consultation_resume_payload, dict):
            resumed_messages = consultation_resume_payload.get("expert_messages")
            if isinstance(resumed_messages, list) and resumed_messages:
                known_ids = {m.get("id") for m in expert_messages if m.get("id")}
                expert_messages = expert_messages + [
                    m for m in resumed_messages
                    if not m.get("id") or m.get("id") not in known_ids
                ]
            log("thinking", f"✅ 会诊已恢复，恢复指令: {consultation_resume_payload.get('action', 'resume')}")
    elif consultation_required:
        log("action", "⚠️  当前 LangGraph 运行时不可用 interrupt，继续使用普通重审流程")

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
        "llm_cross_validation": llm_cross_validation,
        "consultation_required": consultation_required,
        "consultation_resumed": consultation_resumed,
        "consultation_resume_payload": consultation_resume_payload if isinstance(consultation_resume_payload, dict) else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    verdict_text = "打回重审" if requires_more_evidence else "通过审查"
    log("conclusion", f"⚖️  质询完成：{verdict_text} | 发现问题 {len(issues_found)} 个 | 证据质量: {challenger_feedback['quality_score']:.1%}")

    return {
        "challenger_feedback": challenger_feedback,
        "challenges": challenges,
        "logs": logs,
        "expert_messages": expert_messages,
        # 轮次加 1
        "current_round": round_num + (1 if requires_more_evidence else 0),
    }
