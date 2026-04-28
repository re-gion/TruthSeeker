"""LLM client wrapper for TruthSeeker multi-agent deepfake detection system.

Wraps the Kimi/Moonshot API (OpenAI-compatible) using langchain-openai's ChatOpenAI.
Each agent-specific function builds a prompt chain and invokes the LLM asynchronously.
On failure, gracefully degrades to a rule-based fallback string.
"""
from __future__ import annotations

import base64
import json
import logging

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.services.audit_log import record_audit_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM connection pool – module-level singleton cache keyed by model name
# ---------------------------------------------------------------------------
_llm_cache: dict[str, ChatOpenAI] = {}


def get_llm(model_name: str | None = None) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance configured for Kimi/Moonshot API."""
    name = model_name or settings.KIMI_MODEL
    if name not in _llm_cache:
        # Kimi K2 系列只支持 temperature=1，其他模型可用 0.3
        temperature = 1.0 if name.startswith("kimi-k2") else 0.3
        _llm_cache[name] = ChatOpenAI(
            model=name,
            base_url=settings.KIMI_BASE_URL,
            api_key=settings.KIMI_API_KEY,
            temperature=temperature,
            max_tokens=2048,
            request_timeout=120.0,
            max_retries=1,
        )
    return _llm_cache[name]


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

    # 首选模型
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()
    try:
        return await chain.ainvoke(variables)
    except Exception as exc:
        logger.warning("首选模型 %s 调用失败: %s", settings.KIMI_MODEL, exc)

    # fallback 模型
    fallback_llm = get_llm(settings.KIMI_FALLBACK_MODEL)
    fallback_chain = prompt | fallback_llm | StrOutputParser()
    try:
        return await fallback_chain.ainvoke(variables)
    except Exception as exc:
        logger.exception("Fallback 模型 %s 也调用失败: %s", settings.KIMI_FALLBACK_MODEL, exc)
        record_audit_event(
            action="llm.degraded",
            agent="llm_client",
            metadata={"error": f"{type(exc).__name__}: {exc}", "fallback_model": settings.KIMI_FALLBACK_MODEL},
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
        logger.warning("多模态模型 %s 调用失败: %s", settings.KIMI_MODEL, exc)

    fallback_llm = get_llm(settings.KIMI_FALLBACK_MODEL)
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"{human_text}\n\n样本引用摘要：\n{_sample_references_text(sample_refs)}"),
        ]
        response = await fallback_llm.ainvoke(messages)
        content = getattr(response, "content", "")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
    except Exception as exc:
        logger.exception("Fallback 模型 %s 也调用失败: %s", settings.KIMI_FALLBACK_MODEL, exc)
        record_audit_event(
            action="llm.degraded",
            agent="llm_client",
            metadata={"error": f"{type(exc).__name__}: {exc}", "fallback_model": settings.KIMI_FALLBACK_MODEL, "multimodal": True},
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
) -> str:
    """Let the LLM interpret raw forensic detection results into professional analysis."""
    system_prompt = (
            "你是一位专攻深度伪造检测的取证分析专家。"
            "你需要在同一上下文中综合样本引用、全局检测目标、Reality Defender 和 VirusTotal 等工具结果，"
            "撰写结构清晰、术语准确的中文电子取证报告。"
            "报告应包含：1) 检材概况；2) 工具矩阵与等待结果；3) 跨模态取证鉴伪结论；"
            "4) 关键证据、限制和后续复核建议。"
            "如果工具结果标记 degraded、analysis_available=false 或 method=local_fallback_no_external_verdict，"
            "只能写成外部工具未取得真实结论，不得把降级占位字段解释为真实检测通过、面部自然或无伪影。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
    )
    human_text = (
        f"全局检测目标/案件背景：{case_prompt or '用户未补充额外提示。'}\n\n"
        f"输入类型：{input_type}\n\n"
        f"样本引用摘要：\n{_sample_references_text(sample_refs)}\n\n"
        f"原始检测结果：\n{json.dumps(raw_api_result, ensure_ascii=False, indent=2)}"
    )
    return await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=(
            f"基于规则推断: 检测对象类型={input_type}, "
            f"是否伪造={raw_api_result.get('is_deepfake', False)}, "
            f"置信度/概率={raw_api_result.get('deepfake_probability', raw_api_result.get('confidence', 'N/A'))}。"
            f"原始数据如下: {json.dumps(raw_api_result, ensure_ascii=False)}"
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
            "报告应包含：1) 威胁等级判定；2) 关键指标与异常信号分析；"
            "3) 来源可信度评估；4) 关联风险、溯源线索和图谱质量限制。"
            "如果 VirusTotal 或 Exa 标记 degraded，只能说明外部情报不可用或需复核，"
            "不得把未实际调用的结果写成安全厂商未检出。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
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
            f"基于规则推断: 威胁评分={raw_intel.get('threat_score', 'N/A')}, "
            f"关键指标数={len(indicators) if isinstance(indicators, list) else 'N/A'}。"
            f"原始数据如下: {json.dumps(raw_intel, ensure_ascii=False)}"
        ),
    )


# ---------------------------------------------------------------------------
# Challenger Agent
# ---------------------------------------------------------------------------

async def challenger_cross_validate(
    forensics: dict,
    osint: dict,
    challenges: list,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
) -> str:
    """Let the LLM cross-validate evidence from forensics and OSINT agents."""
    system_prompt = (
            "你是一位批判性思维挑战者，职责是交叉验证多个智能体的证据。"
            "你需要仔细比对取证分析与情报评估的结论，找出其中的矛盾、"
            "薄弱证据、逻辑漏洞，或在证据一致时予以确认。"
            "请撰写结构化的中文交叉验证报告，包含："
            "1) 证据一致性总览；2) 矛盾与差异点；3) 薄弱环节与不确定性；"
            "4) 需要进一步调查的问题；5) 整体证据链强度评级(强/中/弱)。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
    )
    human_text = (
        f"【全局检测目标/案件背景】\n{case_prompt or '用户未补充额外提示。'}\n\n"
        f"【样本引用摘要】\n{_sample_references_text(sample_refs)}\n\n"
        f"【取证分析结果】\n{json.dumps(forensics, ensure_ascii=False, indent=2)}\n\n"
        f"【情报评估结果】\n{json.dumps(osint, ensure_ascii=False, indent=2)}\n\n"
        f"【已有质疑记录】\n{json.dumps(challenges, ensure_ascii=False, indent=2)}"
    )
    return await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=(
            "基于规则推断: "
            f"取证结论={json.dumps(forensics, ensure_ascii=False)[:200]}, "
            f"情报结论={json.dumps(osint, ensure_ascii=False)[:200]}, "
            f"已有质疑数={len(challenges) if isinstance(challenges, list) else 'N/A'}。"
            "交叉验证未能执行，建议人工复核。"
        ),
    )


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
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
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
