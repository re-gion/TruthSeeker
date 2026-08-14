"""Commander Agent - 研判指挥Agent，负责综合所有证据做出最终裁决 + LLM 推理"""
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.agents.state import TruthSeekerState, EvidenceItem, AgentLog
from app.agents.skills.loader import finalize_skill_execution, load_agent_skill
from app.agents.tools.llm_client import (
    build_sample_references,
    commander_ruling,
    enforce_temporal_consistency,
)
from app.agents.tools.provenance_graph import build_provenance_graph
from app.services.audit_log import record_audit_event
from app.services.consultation_workflow import build_timeline_event, filter_human_consultation_messages


def _enforce_deterministic_verdict_section(
    report: str, verdict_cn: str, *, strip_preamble: bool = False
) -> str:
    """Keep narrative generation while making the hard-rule verdict authoritative."""
    report = re.sub(r"(?<!\n)(### 最终裁决结论)", r"\n\1", str(report or ""), count=1)
    heading = re.search(r"(?m)^### 最终裁决结论\s*$", report)
    if strip_preamble and heading:
        report = report[heading.start():]
    replacement = f"### 最终裁决结论\n{verdict_cn}\n\n"
    pattern = re.compile(r"(?ms)^### 最终裁决结论\s*\n.*?(?=^###\s)")
    if pattern.search(report):
        report = pattern.sub(replacement, report, count=1)
    else:
        report = replacement + report.lstrip()
    explicit_claim = re.compile(
        r"(最终(?:裁决|判定|结论)\s*(?:为|是|：|:)\s*(?:\*\*)?)"
        r"(?:伪造|可疑|真实|无法判定)(?:\*\*)?"
    )
    return explicit_claim.sub(lambda match: f"{match.group(1)}{verdict_cn}", report)


_CONFIDENCE_COMPONENT_LABELS = {
    "forensics": "电子取证 Agent",
    "osint": "情报溯源 Agent",
    "challenger": "交叉质询 Agent",
}


def _enforce_deterministic_confidence_section(
    report: str,
    confidence_overall: float,
    confidence_components: dict,
) -> str:
    """Replace model-written aggregate confidence with Commander's calculation."""
    component_lines: list[str] = []
    weighted_terms: list[str] = []
    for agent in ("forensics", "osint", "challenger"):
        component = confidence_components.get(agent) if isinstance(confidence_components, dict) else None
        component = component if isinstance(component, dict) else {}
        confidence = float(component.get("confidence") or 0.0)
        weight = float(component.get("weight") or 0.0)
        weighted = float(component.get("weighted") or 0.0)
        weighted_text = f"{weighted:.1%}"
        component_lines.append(
            f"- {_CONFIDENCE_COMPONENT_LABELS[agent]}："
            f"{confidence:.1%} × {weight:.1%} = {weighted_text}"
        )
        weighted_terms.append(weighted_text)

    deterministic_intro = "\n".join([
        f"**研判指挥 Agent 综合置信度：{confidence_overall:.1%}**",
        "",
        "计算过程（由研判指挥 Agent 汇总）：",
        *component_lines,
        f"- 合计：{' + '.join(weighted_terms)} = {confidence_overall:.1%}",
    ])

    section_pattern = re.compile(
        r"(?ms)(^### 置信度与证据链\s*\n)(.*?)(?=^###\s)"
    )
    match = section_pattern.search(report or "")
    if not match:
        return str(report or "")

    model_formula_line = re.compile(
        r"^\s*(?:[-*]\s*)?(?:"
        r"计算过程(?:（[^）]*）)?\s*[:：]?|"
        r"(?:电子取证|情报溯源|交叉质询)\s*Agent\s*[:：].*(?:×|\*)\s*[^=]+=[^=]+|"
        r"合计\s*[:：].*=.*"
        r")\s*$"
    )
    retained_lines = [
        line
        for line in match.group(2).splitlines()
        if "综合置信度" not in line
        and "final_verdict.confidence_overall" not in line
        and "forensics_score" not in line
        and not model_formula_line.match(line)
    ]
    retained_body = "\n".join(retained_lines).strip()
    body = deterministic_intro
    if retained_body:
        body += "\n\n" + retained_body
    replacement = f"{match.group(1)}{body}\n\n"
    return report[:match.start()] + replacement + report[match.end():]


def _conclusion_table_cell(text: str) -> str:
    return str(text).replace("|", "／").replace("\n", " ").strip() or "—"


def _enforce_agent_conclusion_table(
    report: str,
    forensics: dict,
    osint: dict,
    challenger: dict,
) -> str:
    """在“Agent 结论与关键分歧”小节确定性注入结论对照表。

    表格来自各 Agent 的结构化结论，保证分享报告第一部分稳定呈现表格；
    模型若自行写了表格行会被移除以避免重复，其余叙述保留在表格之后。
    """
    section_pattern = re.compile(
        r"(?ms)(^### Agent 结论与关键分歧\s*\n)(.*?)(?=^###\s|\Z)"
    )
    match = section_pattern.search(str(report or ""))
    if not match:
        return str(report or "")

    aigc_probability = float(
        forensics.get("aigc_probability", forensics.get("deepfake_probability", 0.0)) or 0.0
    )
    forensics_is_aigc = bool(forensics.get("is_aigc", forensics.get("is_deepfake", False)))
    forensics_conf = float(forensics.get("confidence", 0.0) or 0.0)
    forensics_conclusion = (
        f"AIGC 概率 {aigc_probability:.1%}，判定为{'AI 生成' if forensics_is_aigc else '非 AI 生成'}内容"
        if forensics
        else "未取得取证结论"
    )
    forensics_status = "外部工具降级" if forensics.get("degraded") else "正常"

    threat_score = float(osint.get("threat_score", 0.0) or 0.0)
    osint_conf = float(osint.get("confidence", 0.0) or 0.0)
    if osint.get("is_malicious"):
        osint_conclusion = f"威胁评分 {threat_score:.1%}，判定为恶意/虚假内容"
    elif osint.get("is_suspicious"):
        osint_conclusion = f"威胁评分 {threat_score:.1%}，判定为可疑内容"
    elif osint:
        osint_conclusion = f"威胁评分 {threat_score:.1%}，未发现明确威胁线索"
    else:
        osint_conclusion = "未取得情报溯源结论"
    osint_status = "外部情报降级" if osint.get("degraded") else "正常"

    issue_count = int(challenger.get("issue_count", 0) or 0)
    high_count = int(challenger.get("high_severity_count", 0) or 0)
    challenger_conf = float(challenger.get("confidence", challenger.get("quality_score", 0.0)) or 0.0)
    challenger_conclusion = (
        f"质询 {issue_count} 个问题（高严重度 {high_count} 个），"
        f"{'存在未解决分歧' if high_count else '无阻断性分歧'}"
    )
    if challenger.get("collaboration_required", challenger.get("consultation_required")):
        challenger_status = "已触发人机协同"
    elif challenger.get("max_rounds_release"):
        challenger_status = "轮次上限放行"
    else:
        challenger_status = "正常收敛"

    table_lines = [
        "| Agent | 核心结论 | 置信度 | 状态说明 |",
        "|---|---|---|---|",
        f"| 电子取证 Agent | {_conclusion_table_cell(forensics_conclusion)} | {forensics_conf:.1%} | {forensics_status} |",
        f"| 情报溯源 Agent | {_conclusion_table_cell(osint_conclusion)} | {osint_conf:.1%} | {osint_status} |",
        f"| 逻辑质询 Agent | {_conclusion_table_cell(challenger_conclusion)} | {challenger_conf:.1%} | {challenger_status} |",
    ]

    retained_lines = [
        line
        for line in match.group(2).splitlines()
        if not line.lstrip().startswith("|")
    ]
    retained_body = "\n".join(retained_lines).strip()
    body = "\n".join(table_lines)
    if retained_body:
        body += "\n\n" + retained_body
    replacement = f"{match.group(1)}\n{body}\n\n"
    return report[: match.start()] + replacement + report[match.end():]


def _enforce_domain_tool_recommendation_boundaries(report: str, osint: dict) -> str:
    """Do not present an already completed WHOIS lookup as pending work."""
    completed_domains: set[str] = set()
    for item in osint.get("domain_provenance_summary") or []:
        if not isinstance(item, dict) or not item.get("whois"):
            continue
        if item.get("status") not in {"success", "partial"}:
            continue
        domain = str(item.get("domain") or "").strip().lower()
        if domain:
            completed_domains.add(domain)
    if not completed_domains:
        return str(report or "")

    action_pattern = re.compile(r"(?:执行|进行|补充|补做|查询).{0,12}WHOIS|WHOIS\s*查询", re.IGNORECASE)
    corrected: list[str] = []
    for line in str(report or "").splitlines():
        domain = next((value for value in completed_domains if value in line.lower()), None)
        if domain is None or not action_pattern.search(line):
            corrected.append(line)
            continue
        prefix = "- " if line.lstrip().startswith(("-", "*", "+")) else ""
        history_match = re.search(
            r"(?:历史\s*IP\s*追踪|DNS\s*History|历史\s*DNS\s*查询)(?P<tail>.*)$",
            line,
            re.IGNORECASE,
        )
        if history_match:
            tail = history_match.group("tail").strip(" 、,，;；。")
            suffix = "；历史 IP 追踪未在默认查询范围内，如确有需要，应另行启用并授权 DNS History 后复核。"
            if tail:
                suffix += f" 其他复核动作仍保留：{tail}。"
        else:
            whois_tail = line[action_pattern.search(line).end():].strip(" 、,，;；。")
            suffix = "。" + (f" 其他复核动作仍保留：{whois_tail}。" if whois_tail else "")
        corrected.append(f"{prefix}OSINT 工具状态：{domain} 的 WHOIS 已完成，无需重复查询{suffix}")
    return "\n".join(corrected)


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
    expert_messages = filter_human_consultation_messages(state.get("expert_messages", []))
    confirmed_consultation_summary = state.get("confirmed_collaboration_summary") or state.get("confirmed_consultation_summary")
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

    log("thinking", f"研判Agent 启动，开始综合电子取证、情报图谱和质询过程...")
    skill_load = load_agent_skill("commander", "final_adjudication")
    skill_initial = skill_load.execution
    if skill_initial.get("load_status") == "loaded":
        log("thinking", f"核心 Skill {skill_initial['skill_name']} v{skill_initial['skill_version']} 已加载，工作流 final_adjudication")
    else:
        reason = "；".join(skill_initial.get("limitations") or ["未知原因"])
        log("action", f"核心 Skill 未加载，继续使用系统提示词与确定性裁决；原因：{reason}")
    record_audit_event(
        action=f"skill.{skill_initial.get('load_status', 'degraded')}",
        task_id=task_id,
        agent="commander",
        metadata=skill_initial,
    )
    log("thinking", f"证据板共 {len(evidence_board)} 条，质询官报告 {challenger.get('issue_count', 0)} 个问题")
    if case_prompt:
        log("thinking", f"全局检测目标: {case_prompt[:120]}")
    if expert_messages:
        log("thinking", f"纳入 {len(expert_messages)} 条人机协同意见")
    if confirmed_consultation_summary:
        summary_text = confirmed_consultation_summary.get("confirmed_summary") if isinstance(confirmed_consultation_summary, dict) else None
        if summary_text:
            log("thinking", f"纳入用户确认的协同摘要: {summary_text[:160]}")

    # === 加权计算（保留数值计算的确定性） ===
    forensics_conf = forensics.get("confidence", 0.5)
    forensics_aigc_prob = forensics.get("aigc_probability", forensics.get("deepfake_probability", 0.5))
    forensics_is_aigc = forensics.get("is_aigc", forensics.get("is_deepfake", False))
    osint_threat = osint.get("threat_score", 0.0)
    osint_risk = max(osint_threat, osint.get("text_risk_score", 0.0), osint.get("social_engineering_score", 0.0))
    osint_conf = osint.get("confidence", 0.75)
    quality_score = challenger.get("quality_score", challenger.get("confidence", 0.8))
    challenger_conf = challenger.get("confidence", quality_score)

    # 动态权重：依据各 Agent 的置信度和降级状态调整
    forensics_weight = 0.45 if not forensics.get("degraded") else 0.25
    osint_weight = 0.30 if not osint.get("degraded") else 0.15
    challenger_weight = 1.0 - forensics_weight - osint_weight

    agent_weights = {
        "forensics": forensics_weight,
        "osint": osint_weight,
        "challenger": challenger_weight,
    }

    def weighted_component(confidence: float, weight: float) -> float:
        return float(
            (Decimal(str(confidence)) * Decimal(str(weight))).quantize(
                Decimal("0.001"),
                rounding=ROUND_HALF_UP,
            )
        )

    # 综合评分
    aigc_score = (
        forensics_aigc_prob * forensics_weight
        + osint_risk * osint_weight
    )
    overall_risk_score = max(aigc_score, osint_risk)

    confidence_components = {
        "forensics": {
            "confidence": forensics_conf,
            "weight": forensics_weight,
            "weighted": weighted_component(forensics_conf, forensics_weight),
        },
        "osint": {
            "confidence": osint_conf,
            "weight": osint_weight,
            "weighted": weighted_component(osint_conf, osint_weight),
        },
        "challenger": {
            "confidence": challenger_conf,
            "weight": challenger_weight,
            "weighted": weighted_component(challenger_conf, challenger_weight),
        },
    }
    overall_confidence = float(
        sum(Decimal(str(item["weighted"])) for item in confidence_components.values()).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )
    )
    confidence_context = {
        "confidence_overall": overall_confidence,
        "formula": "forensics_confidence * forensics_weight + osint_confidence * osint_weight + challenger_confidence * challenger_weight",
        "components": confidence_components,
    }

    log("action", f"权重配置: 法医={forensics_weight:.0%} | OSINT={osint_weight:.0%} | 质询={challenger_weight:.0%}")
    log("action", f"AIGC 风险评分: {aigc_score:.1%} | 综合风险: {overall_risk_score:.1%} | 综合置信度: {overall_confidence:.1%} | 证据质量: {quality_score:.1%}")

    # 判决逻辑
    if (aigc_score > 0.65 and overall_confidence > 0.6) or (
        osint_risk > 0.75 and osint_conf > 0.5 and quality_score > 0.45
    ):
        verdict = "forged"
        verdict_cn = "伪造"
    elif (
        aigc_score > 0.4
        or osint_risk > 0.4
        or osint.get("is_suspicious", False)
        or (forensics_is_aigc and overall_confidence > 0.5)
    ):
        verdict = "suspicious"
        verdict_cn = "可疑"
    elif overall_confidence > 0.5:
        verdict = "authentic"
        verdict_cn = "真实"
    else:
        verdict = "inconclusive"
        verdict_cn = "无法判定"

    log("finding", f"初步裁决: {verdict_cn}，综合置信度: {overall_confidence:.1%}")

    # === LLM 最终裁决报告 ===
    llm_ruling = ""
    llm_status: dict = {}
    log("action", "正在调用大模型生成最终裁决报告...")
    try:
        enriched_challenger = {
            **challenger,
            "expert_messages": expert_messages[:10],
            "confirmed_collaboration_summary": confirmed_consultation_summary,
            "confirmed_consultation_summary": confirmed_consultation_summary,
        }
        llm_ruling = await commander_ruling(
            forensics,
            osint,
            enriched_challenger,
            agent_weights,
            case_prompt,
            sample_refs,
            confidence_context=confidence_context,
            skill_context=skill_load.prompt_context,
            expected_verdict_cn=verdict_cn,
            llm_status=llm_status,
        )
        if llm_status.get("status") != "success":
            log("action", "LLM 裁决不可用，使用规则推断")
    except Exception as e:
        llm_status.update({"status": "degraded", "mode": "node_exception", "reason": f"Commander LLM 裁决异常：{type(e).__name__}"})
        llm_ruling = f"[LLM降级] 裁决推理异常: {e}"
        log("action", f"LLM 裁决异常: {e}")

    llm_ruling = _enforce_deterministic_verdict_section(
        llm_ruling,
        verdict_cn,
        strip_preamble=llm_status.get("status") == "success",
    )
    llm_ruling = _enforce_deterministic_confidence_section(
        llm_ruling,
        overall_confidence,
        confidence_components,
    )
    llm_ruling = _enforce_agent_conclusion_table(llm_ruling, forensics, osint, challenger)
    temporal_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text_samples": [
            *list(forensics.get("text_samples") or []),
            *list(osint.get("text_samples") or []),
        ],
    }
    llm_ruling = enforce_temporal_consistency(llm_ruling, temporal_payload)
    llm_ruling = _enforce_domain_tool_recommendation_boundaries(llm_ruling, osint)
    if llm_status.get("status") == "success":
        log("finding", f"LLM 裁决报告生成完成，{len(llm_ruling)} 字")

    skill_execution = finalize_skill_execution(
        skill_load,
        llm_ruling,
        llm_status=llm_status,
        contract_context={
            "expected_verdict_cn": verdict_cn,
            "expected_confidence_overall": overall_confidence,
        },
    )
    skill_status = str(skill_execution.get("execution_status") or "skipped")
    if skill_status == "applied":
        log("finding", "核心 Skill 已应用，Commander 最终裁决输出契约检查通过")
    elif skill_status == "check_failed":
        log("action", "核心 Skill 已注入，但 Commander 最终裁决输出契约检查未通过")
    elif skill_execution.get("load_status") == "loaded":
        log("action", "LLM 已降级或未执行，本轮无法证明实际采用核心 Skill")
    record_audit_event(
        action=f"skill.{skill_status}",
        task_id=task_id,
        agent="commander",
        metadata=skill_execution,
    )

    provenance_graph = osint.get("provenance_graph") or state.get("provenance_graph") or {}

    # 构建最终裁决
    final_verdict = {
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "confidence": overall_confidence,
        "confidence_overall": overall_confidence,
        "confidence_components": confidence_components,
        "aigc_score": aigc_score,
        "risk_score": overall_risk_score,
        "quality_score": quality_score,
        "agent_weights": agent_weights,
        "forensics_summary": {
            "is_aigc": forensics_is_aigc,
            "aigc_probability": forensics_aigc_prob,
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
            "collaboration_required": challenger.get("collaboration_required", challenger.get("consultation_required", False)),
            "collaboration_resumed": challenger.get("collaboration_resumed", challenger.get("consultation_resumed", False)),
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
        "collaboration_summary": confirmed_consultation_summary,
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
        "skill_execution": skill_execution,
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

    log("conclusion", f"最终裁决: 【{verdict_cn}】 综合置信度 {overall_confidence:.1%}")
    record_audit_event(
        action="commander.verdict",
        task_id=task_id,
        agent="commander",
        metadata={
            "verdict": verdict,
            "confidence": overall_confidence,
            "aigc_score": aigc_score,
            "forensics_degraded": forensics.get("degraded", False),
            "osint_degraded": osint.get("degraded", False),
        },
    )
    log("conclusion", f"裁决报告已存档，任务 {task_id} 分析完成")

    # 时间轴关键事件
    timeline_events.append(build_timeline_event(
        round_number=round_num,
        agent="commander",
        event_type="verdict",
        source_kind="agent",
        from_phase="commander",
        target_agent="system",
        content=f"最终裁决: {verdict_cn} (置信度 {overall_confidence:.1%})",
    ))

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
        "degradation_status": {"skill.commander": skill_status},
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
        recs.append("电子取证与情报溯源结论已完成跨 Agent 交叉验证，建议结合传播渠道、发布账号等上下文进一步核实")
        if challenger.get("issue_count", 0) > 0:
            recs.append("逻辑质询发现证据不足之处，建议人工补充相关背景信息")
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
