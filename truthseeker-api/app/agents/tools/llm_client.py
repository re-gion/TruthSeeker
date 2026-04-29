"""LLM client wrapper for TruthSeeker multi-agent deepfake detection system.

Wraps the selected Kimi API endpoint (OpenAI-compatible) using langchain-openai's ChatOpenAI.
Each agent-specific function builds a prompt chain and invokes the LLM asynchronously.
On failure, gracefully degrades to a local rule-based fallback string.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import resolve_kimi_runtime, settings
from app.services.audit_log import record_audit_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM connection pool – module-level singleton cache keyed by active endpoint
# ---------------------------------------------------------------------------
_llm_cache: dict[tuple[str, str, str], ChatOpenAI] = {}


def get_llm(model_name: str | None = None) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance configured for the selected Kimi endpoint."""
    runtime = resolve_kimi_runtime()
    name = model_name or runtime["model"]
    cache_key = (runtime["provider"], runtime["base_url"], name)
    if cache_key not in _llm_cache:
        # Kimi K2 系列只支持 temperature=1，其他模型可用 0.3
        temperature = 1.0 if name.startswith("kimi-k2") else 0.3
        _llm_cache[cache_key] = ChatOpenAI(
            model=name,
            base_url=runtime["base_url"],
            api_key=runtime["api_key"],
            temperature=temperature,
            max_tokens=2048,
            request_timeout=120.0,
            max_retries=1,
        )
    return _llm_cache[cache_key]


def build_sample_references(evidence_files: list[dict] | None) -> list[dict]:
    """Build sanitized multimodal sample references for agent prompts."""
    references: list[dict] = []
    for index, item in enumerate(evidence_files or [], 1):
        if not isinstance(item, dict):
            continue
        references.append({
            "id": item.get("id") or f"file-{index}",
            "name": item.get("name") or f"evidence-{index}",
            "modality": item.get("modality") or "unknown",
            "mime_type": item.get("mime_type"),
            "size_bytes": item.get("size_bytes"),
            "signed_url": item.get("file_url"),
            "storage_path": item.get("storage_path"),
        })
    return references


def _sample_references_text(sample_refs: list[dict] | None) -> str:
    if not sample_refs:
        return "无可用样本引用。"
    safe_refs = []
    for ref in sample_refs:
        safe_refs.append({
            "id": ref.get("id"),
            "name": ref.get("name"),
            "modality": ref.get("modality"),
            "mime_type": ref.get("mime_type"),
            "size_bytes": ref.get("size_bytes"),
            "has_signed_url": bool(ref.get("signed_url")),
            "storage_path": ref.get("storage_path"),
        })
    return json.dumps(safe_refs, ensure_ascii=False, indent=2)


def _clamp_unit(value: Any, default: float = 0.5) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(1.0, parsed))


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "y"}:
            return True
        if lowered in {"false", "no", "0", "n"}:
            return False
    return default


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_issue_list(value: Any, phase: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    issues: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            description = str(item.get("description") or item.get("issue") or item.get("summary") or "").strip()
            if not description:
                continue
            severity = str(item.get("severity") or "medium").lower()
            if severity not in {"high", "medium", "low"}:
                severity = "medium"
            issues.append({
                "type": str(item.get("type") or "model_challenge"),
                "description": description,
                "severity": severity,
                "agent": str(item.get("agent") or item.get("target_agent") or phase),
            })
        elif isinstance(item, str) and item.strip():
            issues.append({
                "type": "model_challenge",
                "description": item.strip(),
                "severity": "medium",
                "agent": phase,
            })
    return issues


def _default_challenger_markdown(
    *,
    phase: str,
    confidence: float,
    requires_more_evidence: bool,
    target_agent: str | None,
    issues: list[dict[str, Any]],
    residual_risks: list[dict[str, Any]],
) -> str:
    issue_lines = [
        f"- {issue.get('severity', 'medium')}: {issue.get('description', issue.get('type', '未命名质询点'))}"
        for issue in issues[:6]
    ] or ["- 暂未发现新的阻断性质询点。"]
    risk_lines = [
        f"- {risk.get('description') or risk.get('reason') or risk}"
        for risk in residual_risks[:4]
    ] or ["- 暂无新增残留风险；仍建议保留人工复核入口。"]
    suggestion = (
        f"建议打回 {target_agent or phase} 继续补证。"
        if requires_more_evidence
        else "建议放行至下一阶段，并在报告中保留限制说明。"
    )
    return "\n".join([
        "### 质询对象与本轮置信度",
        f"- 质询对象: {target_agent or phase}",
        f"- 本轮置信度: {confidence:.1%}",
        "",
        "### 主要质询点",
        *issue_lines,
        "",
        "### 打回/放行建议",
        f"- {suggestion}",
        "",
        "### 收敛依据",
        *risk_lines,
    ])


_MAX_INLINE_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


async def _fetch_image_base64(url: str) -> str | None:
    """Download image from URL and return a base64 data URI.

    Returns None on failure or if image exceeds size limit.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            data = resp.content
            if len(data) > _MAX_INLINE_IMAGE_BYTES:
                logger.warning(
                    "图片大小 %.2f MB 超过 %d MB 上限，跳过 base64 内联",
                    len(data) / 1024 / 1024,
                    _MAX_INLINE_IMAGE_BYTES // 1024 // 1024,
                )
                return None
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                ext = url.split("?")[0].split(".")[-1].lower()
                content_type = {
                    "png": "image/png",
                    "gif": "image/gif",
                    "webp": "image/webp",
                    "bmp": "image/bmp",
                }.get(ext, "image/jpeg")
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{content_type};base64,{b64}"
    except Exception as exc:
        logger.warning("下载图片转 base64 失败 (%s): %s", type(exc).__name__, exc)
        return None


def _build_multimodal_parts(text: str, sample_refs: list[dict] | None) -> list[dict]:
    """Create OpenAI-compatible content parts with signed URL references when possible."""
    parts: list[dict] = [{"type": "text", "text": text}]
    for ref in sample_refs or []:
        url = ref.get("signed_url")
        modality = ref.get("modality")
        name = ref.get("name") or ref.get("id") or "evidence"
        if not isinstance(url, str) or not url:
            continue
        if modality == "image":
            parts.append({
                "type": "image_url",
                "image_url": {"url": url},
            })
        else:
            parts.append({
                "type": "text",
                "text": f"样本引用: {name} ({modality}) signed_url={url}",
            })
    return parts


# ---------------------------------------------------------------------------
# Shared LLM invocation helper
# ---------------------------------------------------------------------------

async def _invoke_llm(
    system_prompt: str,
    human_template: str,
    variables: dict,
    fallback_text: str,
) -> str:
    """Common LLM call pattern: build chain → invoke → fallback on error."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_template),
    ])

    runtime = resolve_kimi_runtime()
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()
    try:
        return await chain.ainvoke(variables)
    except Exception as exc:
        logger.exception("Kimi %s 模型 %s 调用失败: %s", runtime["provider"], runtime["model"], exc)
        record_audit_event(
            action="llm.degraded",
            agent="llm_client",
            metadata={
                "error": f"{type(exc).__name__}: {exc}",
                "provider": runtime["provider"],
                "model": runtime["model"],
                "base_url": runtime["base_url"],
            },
        )
        return f"[降级模式: LLM不可用] {fallback_text}"


async def _invoke_multimodal_llm(
    system_prompt: str,
    human_text: str,
    sample_refs: list[dict] | None,
    fallback_text: str,
) -> str:
    """Invoke Kimi with multimodal content parts, then degrade to text-only prompt."""
    # 将图片引用转为 base64 data URI，避免模型无法访问 signed URL
    resolved_refs: list[dict] | None = None
    if sample_refs:
        resolved_refs = []
        for ref in sample_refs:
            ref_copy = dict(ref)
            if ref_copy.get("modality") == "image" and ref_copy.get("signed_url"):
                b64_url = await _fetch_image_base64(ref_copy["signed_url"])
                if b64_url:
                    ref_copy["signed_url"] = b64_url
            resolved_refs.append(ref_copy)

    runtime = resolve_kimi_runtime()
    llm = get_llm()
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=_build_multimodal_parts(human_text, resolved_refs)),
        ]
        response = await llm.ainvoke(messages)
        content = getattr(response, "content", "")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Kimi %s 多模态模型 %s 调用失败，改用同模型文本摘要重试: %s", runtime["provider"], runtime["model"], exc)

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"{human_text}\n\n样本引用摘要：\n{_sample_references_text(sample_refs)}"),
        ]
        response = await llm.ainvoke(messages)
        content = getattr(response, "content", "")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
    except Exception as exc:
        logger.exception("Kimi %s 文本摘要重试模型 %s 调用失败: %s", runtime["provider"], runtime["model"], exc)
        record_audit_event(
            action="llm.degraded",
            agent="llm_client",
            metadata={
                "error": f"{type(exc).__name__}: {exc}",
                "provider": runtime["provider"],
                "model": runtime["model"],
                "base_url": runtime["base_url"],
                "multimodal": True,
            },
        )
    return f"[降级模式: LLM不可用] {fallback_text}"


# ---------------------------------------------------------------------------
# Forensics Agent
# ---------------------------------------------------------------------------

async def forensics_interpret(
    raw_api_result: dict,
    input_type: str,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
    text_contents: list[dict] | None = None,
) -> str:
    """Let the LLM interpret raw forensic detection results into professional analysis."""
    system_prompt = (
            "你是一位专攻深度伪造检测的取证分析专家。"
            "你需要在同一上下文中综合样本引用、全局检测目标、Reality Defender 和 VirusTotal 等工具结果，"
            "撰写结构清晰、术语准确的中文电子取证 Markdown 报告。"
            "必须使用以下二级内小标题，且标题原样保留："
            "### 自主检材观察；### 外部检测结果解读；### 融合判断；### 限制与复核建议。"
            "自主检材观察必须融合你对可访问图片、文本内容和样本摘要的直接观察；"
            "若视频、音频或文件本体无法直接读取，要明确说明可见输入边界，不能只复述外部 API。"
            "如果工具结果标记 degraded、analysis_available=false 或 method=local_fallback_no_external_verdict，"
            "只能写成外部工具未取得真实结论，不得把降级占位字段解释为真实检测通过、面部自然或无伪影。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出 Markdown 正文，不要用代码块包裹。"
    )
    text_section = ""
    if text_contents:
        text_section = "\n\n文本检材内容摘要：\n"
        for i, tc in enumerate(text_contents, 1):
            name = tc.get("name", f"text-{i}")
            content = tc.get("content", "")
            text_section += f"--- {name} ---\n{content}\n\n"
    human_text = (
        f"全局检测目标/案件背景：{case_prompt or '用户未补充额外提示。'}\n\n"
        f"输入类型：{input_type}\n\n"
        f"样本引用摘要：\n{_sample_references_text(sample_refs)}\n\n"
        f"原始检测结果：\n{json.dumps(raw_api_result, ensure_ascii=False, indent=2)}"
        f"{text_section}"
    )
    return await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=(
            "### 自主检材观察\n"
            f"- 降级模式下无法调用 Kimi 完成自主图像/文本复核；当前仅能读取样本类型 {input_type} 与工具摘要。\n\n"
            "### 外部检测结果解读\n"
            f"- 是否伪造: {raw_api_result.get('is_deepfake', False)}\n"
            f"- 置信度/概率: {raw_api_result.get('deepfake_probability', raw_api_result.get('confidence', 'N/A'))}\n\n"
            "### 融合判断\n"
            "- 当前判断主要来自规则化工具摘要，不能替代多模态模型复核。\n\n"
            "### 限制与复核建议\n"
            f"- 原始数据摘要: {json.dumps(raw_api_result, ensure_ascii=False)[:800]}"
        ),
    )


# ---------------------------------------------------------------------------
# OSINT Agent
# ---------------------------------------------------------------------------

async def osint_interpret(
    raw_intel: dict,
    input_type: str,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
) -> str:
    """Let the LLM interpret raw OSINT intelligence into a professional assessment."""
    indicators = raw_intel.get("indicators", [])
    system_prompt = (
            "你是一位专攻威胁评估的开源情报(OSINT)分析师。"
            "你需要对传入的原始情报数据、Exa 检索结果、VirusTotal 结果和样本引用进行专业研判，"
            "并说明情报溯源图谱的关键节点、关系和引用覆盖情况。"
            "必须输出 Markdown，并原样保留这些小标题："
            "### 自主情报推理；### 外部情报结果解读；### 来源可信度与图谱质量；### 关联风险与复核建议。"
            "自主情报推理要基于案件提示、样本摘要、实体关系和文本线索进行推断，"
            "外部情报结果解读再汇总 Exa、VirusTotal 等 API 证据。"
            "如果 VirusTotal 或 Exa 标记 degraded，只能说明外部情报不可用或需复核，"
            "不得把未实际调用的结果写成安全厂商未检出。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出 Markdown 正文，不要用代码块包裹。"
    )
    human_text = (
        f"全局检测目标/案件背景：{case_prompt or '用户未补充额外提示。'}\n\n"
        f"输入类型：{input_type}\n\n"
        f"样本引用摘要：\n{_sample_references_text(sample_refs)}\n\n"
        f"原始情报数据：\n{json.dumps(raw_intel, ensure_ascii=False, indent=2)}"
    )
    return await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=(
            "### 自主情报推理\n"
            "- 降级模式下无法调用 Kimi 深度推理；当前仅能基于已抽取指标和图谱摘要做保守判断。\n\n"
            "### 外部情报结果解读\n"
            f"- 威胁评分: {raw_intel.get('threat_score', 'N/A')}\n"
            f"- 关键指标数: {len(indicators) if isinstance(indicators, list) else 'N/A'}\n\n"
            "### 来源可信度与图谱质量\n"
            "- 需复核 Exa/VirusTotal 是否实际返回可引用证据。\n\n"
            "### 关联风险与复核建议\n"
            f"- 原始情报摘要: {json.dumps(raw_intel, ensure_ascii=False)[:800]}"
        ),
    )


# ---------------------------------------------------------------------------
# Challenger Agent
# ---------------------------------------------------------------------------

async def challenger_model_review(
    forensics: dict,
    osint: dict,
    challenges: list,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
    *,
    phase: str = "forensics",
    phase_round: int = 1,
    base_confidence: float = 0.5,
    deterministic_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Let Kimi produce structured challenger reasoning and a Markdown report."""
    base_confidence = _clamp_unit(base_confidence)
    deterministic_issues = deterministic_issues or []
    system_prompt = (
            "你是一位批判性思维挑战者，职责是交叉验证多个智能体的证据。"
            "你需要主动审阅当前 phase 对应的 Forensics、OSINT 或 Commander 结果，"
            "给出阶段置信度、是否建议打回、建议打回的目标 Agent、主要质询点、残留风险，"
            "并撰写 Markdown 逻辑质询报告。"
            "输出必须是 JSON 对象，不要用代码块包裹，字段如下："
            "confidence: 0 到 1 的数字；requires_more_evidence: 布尔值；"
            "target_agent: forensics/osint/commander/null；issues: 数组，每项含 type、description、severity、agent；"
            "residual_risks: 数组；markdown: Markdown 字符串。"
            "markdown 必须原样保留这些小标题："
            "### 质询对象与本轮置信度；### 主要质询点；### 打回/放行建议；### 收敛依据。"
            "模型可以建议打回，但代码会另外用 Δ(t)<0.08、置信度>0.8、最少 2 轮、最多 5 轮兜底。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
    )
    human_text = (
        f"【全局检测目标/案件背景】\n{case_prompt or '用户未补充额外提示。'}\n\n"
        f"【当前质询阶段】\nphase={phase}, phase_round={phase_round}, base_confidence={base_confidence}\n\n"
        f"【样本引用摘要】\n{_sample_references_text(sample_refs)}\n\n"
        f"【取证分析结果】\n{json.dumps(forensics, ensure_ascii=False, indent=2)}\n\n"
        f"【情报评估结果】\n{json.dumps(osint, ensure_ascii=False, indent=2)}\n\n"
        f"【代码侧已发现的问题】\n{json.dumps(deterministic_issues, ensure_ascii=False, indent=2)}\n\n"
        f"【已有质疑记录】\n{json.dumps(challenges, ensure_ascii=False, indent=2)}"
    )
    fallback_payload = {
        "confidence": base_confidence,
        "requires_more_evidence": False,
        "target_agent": phase,
        "issues": [],
        "residual_risks": [{"reason": "Kimi 结构化质询不可用，使用代码侧硬门槛继续判定"}],
        "markdown": _default_challenger_markdown(
            phase=phase,
            confidence=base_confidence,
            requires_more_evidence=False,
            target_agent=phase,
            issues=deterministic_issues,
            residual_risks=[{"reason": "Kimi 结构化质询不可用，需人工复核代码侧质询结果"}],
        ),
    }
    raw = await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=json.dumps(fallback_payload, ensure_ascii=False),
    )
    parsed = _extract_json_object(raw) or {}
    confidence = _clamp_unit(parsed.get("confidence"), base_confidence)
    issues = _normalize_issue_list(parsed.get("issues"), phase)
    residual_risks = parsed.get("residual_risks") if isinstance(parsed.get("residual_risks"), list) else []
    target_agent_raw = parsed.get("target_agent")
    target_agent = str(target_agent_raw) if target_agent_raw in {"forensics", "osint", "commander"} else phase
    requires_more_evidence = _coerce_bool(parsed.get("requires_more_evidence"), False)
    markdown = parsed.get("markdown") if isinstance(parsed.get("markdown"), str) else ""
    if not markdown.strip():
        markdown = _default_challenger_markdown(
            phase=phase,
            confidence=confidence,
            requires_more_evidence=requires_more_evidence,
            target_agent=target_agent,
            issues=issues or deterministic_issues,
            residual_risks=residual_risks,
        )
    return {
        "confidence": confidence,
        "requires_more_evidence": requires_more_evidence,
        "target_agent": target_agent,
        "issues": issues,
        "residual_risks": residual_risks,
        "markdown": markdown,
        "raw_response": raw,
    }


async def challenger_cross_validate(
    forensics: dict,
    osint: dict,
    challenges: list,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
) -> str:
    """Compatibility wrapper returning only the Markdown challenger report."""
    review = await challenger_model_review(
        forensics,
        osint,
        challenges,
        case_prompt,
        sample_refs,
    )
    return str(review.get("markdown") or "")


# ---------------------------------------------------------------------------
# Commander Agent
# ---------------------------------------------------------------------------

async def commander_ruling(
    forensics: dict,
    osint: dict,
    challenger_feedback: dict,
    agent_weights: dict,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
) -> str:
    """Let the LLM produce a final ruling based on all agent evidence."""
    system_prompt = (
            "你是一位资深指挥官，负责基于全部智能体证据做出最终裁决。"
            "你需要综合取证分析、情报评估和交叉验证三个维度的结论，"
            "结合各智能体的权重配置，撰写权威的中文最终裁决报告。"
            "报告必须包含：1) 最终裁决结论（伪造/真实/无法判定）；"
            "2) 置信度评估与证据链完整性分析；3) 各智能体结论对比与权重考量；"
            "4) 关键分歧点及处理意见；5) 后续取证建议与风险提示。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出分析文本，不要用代码块包裹。"
    )
    human_text = (
        f"【全局检测目标/案件背景】\n{case_prompt or '用户未补充额外提示。'}\n\n"
        f"【样本引用摘要】\n{_sample_references_text(sample_refs)}\n\n"
        f"【取证分析结果】\n{json.dumps(forensics, ensure_ascii=False, indent=2)}\n\n"
        f"【情报评估结果】\n{json.dumps(osint, ensure_ascii=False, indent=2)}\n\n"
        f"【交叉验证反馈】\n{json.dumps(challenger_feedback, ensure_ascii=False, indent=2)}\n\n"
        f"【智能体权重配置】\n{json.dumps(agent_weights, ensure_ascii=False, indent=2)}"
    )
    return await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=(
            "基于规则推断: 综合所有智能体证据，"
            f"权重={json.dumps(agent_weights, ensure_ascii=False)}，"
            "裁决未能由 LLM 完成。"
            f"取证={json.dumps(forensics, ensure_ascii=False)[:150]}, "
            f"情报={json.dumps(osint, ensure_ascii=False)[:150]}, "
            f"挑战={json.dumps(challenger_feedback, ensure_ascii=False)[:150]}。"
            "建议人工审核所有证据后做出最终判定。"
        ),
    )
