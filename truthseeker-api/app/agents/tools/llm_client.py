"""LLM client wrapper for TruthSeeker multi-agent malicious AIGC detection system.

Wraps the selected Agent LLM endpoint (OpenAI-compatible) using langchain-openai's ChatOpenAI.
Each agent-specific function builds a prompt chain and invokes the LLM asynchronously.
On failure, gracefully degrades to a local rule-based fallback string.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

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
_llm_cache: dict[tuple[str, str, str, str], ChatOpenAI] = {}


def get_llm(model_name: str | None = None) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance configured for the selected Agent LLM endpoint."""
    runtime = resolve_kimi_runtime()
    name = model_name or runtime["model"]
    cache_key = (runtime["provider"], runtime["base_url"], name, runtime["api_key"])
    if cache_key not in _llm_cache:
        # Kimi K2.5 在关闭 thinking 后固定 temperature=0.6。
        temperature = 0.6 if name.startswith("kimi-k2.5") else 0.3
        extra_body = {"thinking": {"type": "disabled"}} if name.startswith("kimi-k2.5") else None
        default_headers = {"api-key": runtime["api_key"]} if runtime["provider"] == "mimo" else None
        # Xiaomi MiMo Token Plan 的全模态模型默认使用 mimo-v2.5。
        # mimo-v2.5 支持显式 thinking enabled/disabled；thinking enabled 时官方不支持自定义 temperature。
        if runtime["provider"] == "mimo":
            thinking_mode = runtime.get("thinking") or "enabled"
            extra_body = {"thinking": {"type": thinking_mode}}
            temperature = 1.0 if thinking_mode == "enabled" else 0.3
        max_output_tokens = int(runtime.get("max_output_tokens") or settings.AGENT_LLM_MAX_OUTPUT_TOKENS)
        _llm_cache[cache_key] = ChatOpenAI(
            model=name,
            base_url=runtime["base_url"],
            api_key=runtime["api_key"],
            temperature=temperature,
            max_tokens=max_output_tokens,
            request_timeout=120.0,
            max_retries=1,
            extra_body=extra_body,
            default_headers=default_headers,
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
_IMAGE_FETCH_TIMEOUT = 60.0  # Supabase signed URL 下载较慢，给足时间
_IMAGE_FETCH_MAX_RETRIES = 2
_CN_TZ = ZoneInfo("Asia/Shanghai")
_TEMPORAL_PATTERN = re.compile(
    r"(?P<label>[\u4e00-\u9fffA-Za-z0-9_·/\-]{0,16}时间)?"
    r"[：:\s]*"
    r"(?P<date>20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)"
    r"(?:[ T　]*(?P<time>\d{1,2}:\d{2}(?::\d{2})?))?"
)


async def _fetch_image_base64(url: str) -> str | None:
    """Download image from URL and return a base64 data URI.

    Returns None on failure or if image exceeds size limit.
    """
    last_error = None
    for attempt in range(1 + _IMAGE_FETCH_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_IMAGE_FETCH_TIMEOUT) as client:
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
            last_error = exc
            if attempt < _IMAGE_FETCH_MAX_RETRIES:
                logger.debug("下载图片转 base64 第 %d 次重试 (%s): %s", attempt + 1, type(exc).__name__, exc)
    logger.warning("下载图片转 base64 失败（共 %d 次尝试）(%s): %s", 1 + _IMAGE_FETCH_MAX_RETRIES, type(last_error).__name__, last_error)
    return None


def _build_multimodal_parts(text: str, sample_refs: list[dict] | None) -> list[dict]:
    """Create OpenAI-compatible content parts with signed URL references when possible."""
    parts: list[dict] = [{"type": "text", "text": text}]
    for ref in sample_refs or []:
        url = ref.get("signed_url")
        modality = ref.get("modality")
        name = ref.get("name") or ref.get("id") or "evidence"
        if not isinstance(url, str) or not url:
            if modality in ("image", "image_unavailable"):
                parts.append({"type": "text", "text": f"图片样本引用: {name}（图片下载失败，无法直接分析图像内容）"})
            continue
        if modality == "image":
            # 只传 base64 data URI，不传外部 URL（Kimi 不支持外部图片 URL）
            if url.startswith("data:"):
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": url},
                })
            else:
                parts.append({"type": "text", "text": f"图片样本引用: {name}（图片需 base64 内联，当前 URL 不可用）"})
        else:
            parts.append({
                "type": "text",
                "text": f"样本引用: {name} ({modality}) signed_url={url}",
            })
    return parts


def _parse_reference_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_CN_TZ)
    return parsed.astimezone(_CN_TZ)


def _parse_sample_time(date_part: str, time_part: str | None) -> datetime | None:
    normalized = (
        date_part.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    pieces = normalized.split("-")
    if len(pieces) != 3:
        return None
    try:
        year, month, day = (int(piece) for piece in pieces)
        if time_part:
            time_pieces = [int(piece) for piece in time_part.split(":")]
            hour = time_pieces[0]
            minute = time_pieces[1]
            second = time_pieces[2] if len(time_pieces) > 2 else 0
        else:
            hour = minute = second = 0
        return datetime(year, month, day, hour, minute, second, tzinfo=_CN_TZ)
    except ValueError:
        return None


def _iter_text_sample_contents(payload: dict[str, Any]) -> list[tuple[str, str]]:
    contents: list[tuple[str, str]] = []
    for key in ("text_samples", "text_contents"):
        for index, item in enumerate(payload.get(key) or [], 1):
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("text")
            if not isinstance(content, str) or not content.strip():
                continue
            name = str(item.get("name") or f"{key}-{index}")
            contents.append((name, content))
    return contents


def _build_temporal_fact_table(payload: dict[str, Any]) -> str:
    """Build deterministic sample-time facts so LLM summaries cannot invert dates."""
    reference = (
        _parse_reference_time(payload.get("timestamp"))
        or _parse_reference_time(payload.get("analysis_time"))
        or _parse_reference_time(payload.get("generated_at"))
        or datetime.now(timezone.utc).astimezone(_CN_TZ)
    )
    rows: list[str] = []
    seen: set[tuple[str, str]] = set()
    for name, content in _iter_text_sample_contents(payload):
        for match in _TEMPORAL_PATTERN.finditer(content):
            parsed = _parse_sample_time(match.group("date"), match.group("time"))
            if parsed is None:
                continue
            original = match.group(0).strip(" ：:")
            key = (name, original)
            if key in seen:
                continue
            seen.add(key)
            if parsed > reference:
                relation = "晚于分析时间，是未来日期"
                guard = "可称为未来日期，但必须说明比较基准"
            elif parsed < reference:
                relation = "早于分析时间，不是未来日期"
                guard = "不得称为未来日期"
            else:
                relation = "等于分析时间，不是未来日期"
                guard = "不得称为未来日期"
            rows.append(
                f"- {name}: {original} -> {parsed.strftime('%Y-%m-%d %H:%M:%S')}，"
                f"{relation}；{guard}。"
            )
    if not rows:
        return ""
    return "\n".join([
        "确定性时间校验（由代码生成，优先级高于模型推断）:",
        f"- 分析时间（北京时间）: {reference.strftime('%Y-%m-%d %H:%M:%S')}",
        *rows,
    ])


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
        error_str = f"{type(exc).__name__}: {exc}"
        is_rate_limit = "429" in error_str or "rate_limit" in error_str.lower()
        if is_rate_limit:
            logger.warning(
                "Kimi %s 模型 %s 触发速率限制(TPD): %s",
                runtime["provider"], runtime["model"], exc,
            )
        else:
            logger.exception("Kimi %s 模型 %s 调用失败: %s", runtime["provider"], runtime["model"], exc)
        record_audit_event(
            action="llm.degraded",
            agent="llm_client",
            metadata={
                "error": error_str,
                "provider": runtime["provider"],
                "model": runtime["model"],
                "base_url": runtime["base_url"],
                "rate_limited": is_rate_limit,
            },
        )
        hint = "（TPD 速率限制已超限，请等待重置或更换账号）" if is_rate_limit else ""
        return f"[降级模式: LLM不可用{hint}] {fallback_text}"


async def _invoke_multimodal_llm(
    system_prompt: str,
    human_text: str,
    sample_refs: list[dict] | None,
    fallback_text: str,
) -> str:
    """Invoke Kimi with multimodal content parts, then degrade to text-only prompt."""
    # 将图片引用转为 base64 data URI，避免模型无法访问 signed URL
    resolved_refs: list[dict] | None = None
    has_any_image = False
    has_any_base64 = False
    if sample_refs:
        resolved_refs = []
        for ref in sample_refs:
            ref_copy = dict(ref)
            if ref_copy.get("modality") == "image" and ref_copy.get("signed_url"):
                has_any_image = True
                b64_url = await _fetch_image_base64(ref_copy["signed_url"])
                if b64_url:
                    ref_copy["signed_url"] = b64_url
                    has_any_base64 = True
                else:
                    ref_copy["modality"] = "image_unavailable"
            resolved_refs.append(ref_copy)

    runtime = resolve_kimi_runtime()
    llm = get_llm()

    # 有图片但全部 base64 转换失败时，跳过多模态调用直接走文本
    if has_any_image and not has_any_base64:
        logger.warning(
            "所有图片 base64 转换失败，跳过多模态调用，直接使用文本模式"
        )
    else:
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
        error_str = f"{type(exc).__name__}: {exc}"
        # 检测速率限制
        is_rate_limit = "429" in error_str or "rate_limit" in error_str.lower()
        log_level = logger.warning if is_rate_limit else logger.exception
        log_level("Kimi %s 文本摘要重试模型 %s 调用失败: %s", runtime["provider"], runtime["model"], exc)
        record_audit_event(
            action="llm.degraded",
            agent="llm_client",
            metadata={
                "error": error_str,
                "provider": runtime["provider"],
                "model": runtime["model"],
                "base_url": runtime["base_url"],
                "multimodal": True,
                "rate_limited": is_rate_limit,
            },
        )
    hint = "（TPD 速率限制已超限，请等待重置或更换账号）" if is_rate_limit else ""
    return f"[降级模式: LLM不可用{hint}] {fallback_text}"


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
            "你是一位专攻恶意 AIGC 检测的取证分析专家。"
            "你需要在同一上下文中综合样本引用、全局检测目标、Sightengine 图片 AIGC 检测、Reality Defender 音视频合成/篡改检测和 VirusTotal 等工具结果，"
            "撰写结构清晰、术语准确的中文电子取证 Markdown 报告。"
            "必须使用以下二级内小标题，且标题原样保留："
            "### 自主检材观察；### 外部检测结果解读；### 融合判断；### 限制与复核建议。"
            "自主检材观察必须融合你对可访问图片、文本内容和样本摘要的直接观察；"
            "若视频、音频或文件本体无法直接读取，要明确说明可见输入边界，不能只复述外部 API。"
            "如果工具结果标记 degraded、analysis_available=false 或 method=local_fallback_no_external_verdict，"
            "只能写成外部工具未取得真实结论，不得把降级占位字段解释为真实检测通过、面部自然或无伪影。"
            "如果传入 case_rag_search 或 case_rag 字段，相似公开案例只能作为类案参考和复核方向，"
            "不得写成当前检材事实，也不得替代本轮样本、Sightengine、Reality Defender 或 VirusTotal 证据。"
            "如果传入 experience_rag_search 或 experience_rag 字段，个人经验只能作为用户私有的方法参考和检查清单，"
            "不得写成当前检材事实，不得直接改变取证分数或替代本轮证据。"
            "如果传入 reinforcement_context，必须优先回应 Challenger 打回原因、残留风险和会诊摘要，只补强被指出的缺口，不重复上一轮完整报告。"
            "如果输入包含“确定性时间校验”，必须以该校验为准，不得输出与其相反的日期先后判断。"
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
    temporal_facts = _build_temporal_fact_table(raw_api_result)
    temporal_section = f"\n\n{temporal_facts}" if temporal_facts else ""
    human_text = (
        f"全局检测目标/案件背景：{case_prompt or '用户未补充额外提示。'}\n\n"
        f"输入类型：{input_type}\n\n"
        f"样本引用摘要：\n{_sample_references_text(sample_refs)}\n\n"
        f"原始检测结果：\n{json.dumps(raw_api_result, ensure_ascii=False, indent=2)}"
        f"{text_section}"
        f"{temporal_section}"
    )
    return await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=(
            "### 自主检材观察\n"
            f"- 降级模式下无法调用 Kimi 完成自主图像/文本复核；当前仅能读取样本类型 {input_type} 与工具摘要。\n\n"
            "### 外部检测结果解读\n"
            f"- 是否存在 AIGC 风险线索: {raw_api_result.get('is_aigc', raw_api_result.get('is_deepfake', False))}\n"
            f"- AIGC 风险概率: {raw_api_result.get('aigc_probability', raw_api_result.get('ai_generated_probability', raw_api_result.get('deepfake_probability', raw_api_result.get('confidence', 'N/A'))))}\n\n"
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
            "你需要对传入的原始情报数据、Exa 检索结果、VirusTotal、WhoisXML 域名注册/当前DNS/IP归属结果和样本引用进行专业研判，"
            "并说明情报溯源图谱的关键节点、关系和引用覆盖情况。"
            "必须输出 Markdown，并原样保留这些小标题："
            "### 自主情报推理；### 外部情报结果解读；### 来源可信度与图谱质量；### 关联风险与复核建议。"
            "自主情报推理要基于案件提示、样本摘要、实体关系和文本线索进行推断，"
            "外部情报结果解读再汇总 Exa、VirusTotal、WhoisXML 等 API 证据。"
            "如果 VirusTotal、WhoisXML 或 Exa 标记 degraded，只能说明外部情报不可用或需复核，"
            "不得把未实际调用的结果写成安全厂商未检出。"
            "如果传入 case_rag_search 或 case_rag 字段，相似公开案例只能作为攻击模式和溯源路径参考，"
            "不能替代当前 URL、域名、样本或外部来源的独立核验。"
            "如果传入 experience_rag_search 或 experience_rag 字段，个人经验只能作为用户私有的溯源方法参考，"
            "不得写成当前案件事实，不得直接改变威胁分数或替代当前 URL、域名、样本与外部来源核验。"
            "如果传入 reinforcement_context，必须优先回应 Challenger 打回原因、残留风险和会诊摘要，只补强被指出的缺口，不重复上一轮完整报告。"
            "如果输入包含“确定性时间校验”，必须以该校验为准，不得输出与其相反的日期先后判断。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出 Markdown 正文，不要用代码块包裹。"
    )
    temporal_facts = _build_temporal_fact_table(raw_intel)
    temporal_section = f"\n\n{temporal_facts}" if temporal_facts else ""
    human_text = (
        f"全局检测目标/案件背景：{case_prompt or '用户未补充额外提示。'}\n\n"
        f"输入类型：{input_type}\n\n"
        f"样本引用摘要：\n{_sample_references_text(sample_refs)}\n\n"
        f"原始情报数据：\n{json.dumps(raw_intel, ensure_ascii=False, indent=2)}"
        f"{temporal_section}"
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
            "- 需复核 Exa/VirusTotal/WhoisXML 是否实际返回可引用证据。\n\n"
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
            "模型可以建议打回，但代码会另外用 Δ(t)<0.08、置信度>0.8、阻断性 high issue 和最多 5 轮兜底。"
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
# Commander consultation moderation
# ---------------------------------------------------------------------------

def _normalize_help_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip() if isinstance(item, str) else ""
        if not text:
            continue
        key = re.sub(r"\s+", "", text.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(text[:400])
    return result


def _help_tokens(text: str) -> set[str]:
    normalized = text.lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", normalized))
    chars = set(re.findall(r"[\u4e00-\u9fff]", normalized))
    return words | chars


def _help_similarity(left: str, right: str) -> float:
    left_tokens = _help_tokens(left)
    right_tokens = _help_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _generic_dedupe_help_items(items: list[str], *, limit: int = 5) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if any(_help_similarity(item, existing) >= 0.62 for existing in deduped):
            continue
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _normalize_expert_tasks(value: Any, help_needed: list[str], trigger: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if isinstance(value, list):
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if not question:
                continue
            severity = str(item.get("severity") or "high").lower()
            if severity not in {"high", "medium", "low"}:
                severity = "high"
            tasks.append({
                "id": str(item.get("id") or f"expert-task-{index}"),
                "target_agent": str(item.get("target_agent") or trigger.get("target_agent") or "unknown"),
                "issue_type": str(item.get("issue_type") or item.get("type") or "issue"),
                "severity": severity,
                "question": question[:500],
                "requested_action": str(
                    item.get("requested_action")
                    or "请给出判断依据、可补充证据、以及是否需要重跑/人工复核该环节。"
                )[:500],
                "expected_output": str(
                    item.get("expected_output")
                    or "一到三条可执行结论：风险判断、缺失证据、建议继续检测或人工复核的动作。"
                )[:500],
            })
            if len(tasks) >= 5:
                break
    if tasks:
        return tasks
    return [
        {
            "id": f"expert-task-{index}",
            "target_agent": str(trigger.get("target_agent") or "unknown"),
            "issue_type": "issue",
            "severity": "high",
            "question": f"请专家判断并补充：{item}",
            "requested_action": "请给出判断依据、可补充证据、以及是否需要重跑/人工复核该环节。",
            "expected_output": "一到三条可执行结论：风险判断、缺失证据、建议继续检测或人工复核的动作。",
        }
        for index, item in enumerate(help_needed[:5], start=1)
    ]


def _fallback_consultation_context_dedupe(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    trigger = result.get("trigger") if isinstance(result.get("trigger"), dict) else {}
    help_needed = _generic_dedupe_help_items(_normalize_help_items(result.get("help_needed")))
    result["help_needed"] = help_needed
    result["expert_tasks"] = _normalize_expert_tasks(result.get("expert_tasks"), help_needed, trigger)
    result["help_needed_dedupe"] = {
        "provider": "generic_similarity_fallback",
        "llm_available": False,
        "method": "token_jaccard_similarity",
    }
    return result


async def commander_dedupe_consultation_context(
    context: dict[str, Any],
    *,
    case_prompt: str = "",
    sample_refs: list[dict] | None = None,
) -> dict[str, Any]:
    """Let Commander merge repeated consultation help items before showing experts."""
    if not isinstance(context, dict):
        return context
    help_needed = _normalize_help_items(context.get("help_needed"))
    if len(help_needed) <= 1:
        return context

    fallback = _fallback_consultation_context_dedupe(context)
    system_prompt = (
        "你是 TruthSeeker 的 Commander 主持人，负责在启动专家会诊前整理“需要帮助”字段。"
        "你的任务是合并语义重复或同一根因的求助点，保留不同根因、不同 Agent、不同证据缺口。"
        "不要新增输入中不存在的事实，不要按固定关键词套模板。"
        "输出必须是 JSON 对象，字段为 help_needed 和 expert_tasks。"
        "help_needed 最多 5 条，每条应具体、可执行、避免重复。"
        "expert_tasks 应与 help_needed 对齐，每项包含 target_agent、issue_type、severity、question、requested_action、expected_output。"
    )
    human_text = (
        f"案件背景：{case_prompt or context.get('case_prompt') or '用户未补充额外背景。'}\n\n"
        f"会诊触发信息：\n{json.dumps(context.get('trigger') or {}, ensure_ascii=False, indent=2)}\n\n"
        f"原始需要帮助：\n{json.dumps(help_needed, ensure_ascii=False, indent=2)}\n\n"
        f"原始专家任务：\n{json.dumps(context.get('expert_tasks') or [], ensure_ascii=False, indent=2)}"
    )
    raw = await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=sample_refs,
        fallback_text=json.dumps({
            "help_needed": fallback.get("help_needed") or [],
            "expert_tasks": fallback.get("expert_tasks") or [],
        }, ensure_ascii=False),
    )
    parsed = _extract_json_object(raw)
    if not parsed:
        return fallback

    trigger = context.get("trigger") if isinstance(context.get("trigger"), dict) else {}
    deduped_help = _normalize_help_items(parsed.get("help_needed"))
    if not deduped_help:
        return fallback
    deduped_help = deduped_help[:5]
    result = dict(context)
    result["help_needed"] = deduped_help
    result["expert_tasks"] = _normalize_expert_tasks(parsed.get("expert_tasks"), deduped_help, trigger)
    result["help_needed_dedupe"] = {
        "provider": "commander_llm",
        "llm_available": True,
        "method": "semantic_merge",
        "raw_response": raw[:1200],
    }
    return result


def _consultation_message_for_summary(item: dict[str, Any]) -> dict[str, Any] | None:
    role = str(item.get("role") or "").strip()
    message = str(item.get("message") or item.get("content") or "").strip()
    if not message:
        return None
    return {
        "role": role or "participant",
        "expert_name": item.get("expert_name"),
        "message_type": item.get("message_type"),
        "message": message[:1000],
        "created_at": item.get("created_at"),
    }


async def commander_summarize_consultation(
    *,
    messages: list[dict[str, Any]],
    context_payload: dict[str, Any] | None = None,
    fallback_summary: dict[str, Any] | None = None,
    case_prompt: str = "",
) -> dict[str, Any]:
    """Let Commander summarize expert consultation against the requested help items."""
    fallback_summary = dict(fallback_summary or {})
    context_payload = context_payload if isinstance(context_payload, dict) else {}
    normalized_messages = [
        normalized for item in messages
        if isinstance(item, dict) and (normalized := _consultation_message_for_summary(item)) is not None
    ]
    if not normalized_messages:
        fallback_summary.setdefault("summary_provider", "no_human_messages")
        return fallback_summary

    help_needed = _normalize_help_items(context_payload.get("help_needed"))
    expert_tasks = context_payload.get("expert_tasks") if isinstance(context_payload.get("expert_tasks"), list) else []
    fallback_generated = str(fallback_summary.get("generated_summary") or "本轮会诊已结束，但未生成有效摘要。")
    system_prompt = (
        "你是 TruthSeeker 的 Commander 会诊主持人。"
        "用户点击结束会诊后，你必须阅读会诊上下文、需要帮助字段、专家任务、用户与专家对话，生成真正的摘要。"
        "重点总结专家针对“需要帮助”字段中问题的回复、判断依据和下一步建议。"
        "不要逐字复述完整聊天记录，不要只输出固定结构。"
        "输出 JSON 对象，字段包括 generated_summary、expert_answer_summary、recommended_actions、unresolved_questions。"
        "generated_summary 用 3 到 6 句中文自然段，必须可直接回注给后续 Agent 使用。"
    )
    human_text = (
        f"案件背景：{case_prompt or context_payload.get('case_prompt') or '用户未补充额外背景。'}\n\n"
        f"需要帮助字段：\n{json.dumps(help_needed, ensure_ascii=False, indent=2)}\n\n"
        f"专家任务：\n{json.dumps(expert_tasks, ensure_ascii=False, indent=2)}\n\n"
        f"会诊上下文：\n{json.dumps(context_payload, ensure_ascii=False, indent=2)[:6000]}\n\n"
        f"用户与专家对话：\n{json.dumps(normalized_messages, ensure_ascii=False, indent=2)}\n\n"
        f"兜底机械摘要，仅供参考，不得照抄：\n{fallback_generated}"
    )
    fallback_payload = {
        "generated_summary": fallback_generated,
        "expert_answer_summary": "",
        "recommended_actions": [],
        "unresolved_questions": fallback_summary.get("unresolved_questions") or [],
    }
    raw = await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=None,
        fallback_text=json.dumps(fallback_payload, ensure_ascii=False),
    )
    if raw.strip().startswith("[降级模式"):
        fallback_summary.setdefault("summary_provider", "fallback_static")
        fallback_summary["summary_degraded"] = True
        return fallback_summary

    parsed = _extract_json_object(raw)
    if not parsed:
        fallback_summary.setdefault("summary_provider", "fallback_static")
        return fallback_summary

    generated = str(parsed.get("generated_summary") or "").strip()
    if not generated:
        fallback_summary.setdefault("summary_provider", "fallback_static")
        return fallback_summary

    result = dict(fallback_summary)
    result["generated_summary"] = generated[:2000]
    result["confirmed_summary"] = generated[:2000]
    result["summary_provider"] = "commander_llm"
    result["summary_raw_response"] = raw[:1200]
    if isinstance(parsed.get("expert_answer_summary"), str):
        result["expert_answer_summary"] = parsed["expert_answer_summary"][:1200]
    if isinstance(parsed.get("recommended_actions"), list):
        result["recommended_actions"] = [str(item)[:300] for item in parsed["recommended_actions"][:6] if str(item).strip()]
    if isinstance(parsed.get("unresolved_questions"), list):
        result["unresolved_questions"] = [str(item)[:300] for item in parsed["unresolved_questions"][:6] if str(item).strip()]
    result["help_needed"] = help_needed
    return result


async def commander_extract_experience_drafts(
    *,
    messages: list[dict[str, Any]],
    context_payload: dict[str, Any] | None = None,
    summary_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract reusable, private experience drafts from a finished consultation."""
    context_payload = context_payload if isinstance(context_payload, dict) else {}
    summary_payload = summary_payload if isinstance(summary_payload, dict) else {}
    normalized_messages = [
        normalized for item in messages
        if isinstance(item, dict) and (normalized := _consultation_message_for_summary(item)) is not None
    ]
    if not normalized_messages:
        return []

    system_prompt = (
        "你是 TruthSeeker 的 Commander 主持人，负责从已结束的专家会诊中沉淀个人经验草稿。"
        "只提取可复用的方法、判据、补证路径和升级会诊条件；不要保存具体检材名、链接、账号、专家原话或可识别案件细节。"
        "一场会诊可以沉淀 0、1 或多条经验；如果专家回复没有可复用内容，输出空数组。"
        "输出必须是 JSON 对象，字段 drafts 为数组。每条草稿必须包含："
        "title、target_agents、problem_pattern、recommended_method、evidence_to_check、when_to_escalate、limitations。"
        "target_agents 只能包含 forensics、osint、challenger。"
    )
    fallback_payload = {"drafts": []}
    human_text = (
        f"会诊上下文（已脱敏使用）：\n{json.dumps(context_payload, ensure_ascii=False, indent=2)[:5000]}\n\n"
        f"会诊摘要：\n{json.dumps(summary_payload, ensure_ascii=False, indent=2)[:3000]}\n\n"
        f"用户与专家消息：\n{json.dumps(normalized_messages, ensure_ascii=False, indent=2)[:7000]}"
    )
    raw = await _invoke_multimodal_llm(
        system_prompt=system_prompt,
        human_text=human_text,
        sample_refs=None,
        fallback_text=json.dumps(fallback_payload, ensure_ascii=False),
    )
    if raw.strip().startswith("[降级模式"):
        return []
    parsed = _extract_json_object(raw)
    drafts = parsed.get("drafts") if isinstance(parsed, dict) else None
    if not isinstance(drafts, list):
        return []
    return [item for item in drafts if isinstance(item, dict)]


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
    confidence_context: dict | None = None,
) -> str:
    """Let the LLM produce a final ruling based on all agent evidence."""
    system_prompt = (
            "你是一位研判指挥官，负责基于全部智能体证据做出最终裁决。"
            "你需要综合取证分析、情报评估和交叉验证三个维度的结论，"
            "结合各智能体的权重配置，撰写权威的中文最终裁决报告。"
            "公开案例 RAG 命中只能作为类案参考，不得直接改变裁决结论或置信度，"
            "也不得把历史案例内容写成当前任务事实。"
            "报告必须包含：1) 最终裁决结论（伪造/真实/无法判定）；"
            "2) 置信度评估与证据链完整性分析；3) 各智能体结论对比与权重考量；"
            "4) 关键分歧点及处理意见；5) 后续取证建议与风险提示。"
            "综合置信度必须引用结构化 final_verdict.confidence_overall 或权重加权结果，"
            "不得把 OSINT 自身置信度、人工意见或模型自行估计写成最终综合置信度。"
            "如报告中需要提及时间，请统一使用北京时间（UTC+8），不要输出 UTC 时间。"
            "请直接输出分析文本，不要用代码块包裹。"
    )
    human_text = (
        f"【全局检测目标/案件背景】\n{case_prompt or '用户未补充额外提示。'}\n\n"
        f"【样本引用摘要】\n{_sample_references_text(sample_refs)}\n\n"
        f"【取证分析结果】\n{json.dumps(forensics, ensure_ascii=False, indent=2)}\n\n"
        f"【情报评估结果】\n{json.dumps(osint, ensure_ascii=False, indent=2)}\n\n"
        f"【交叉验证反馈】\n{json.dumps(challenger_feedback, ensure_ascii=False, indent=2)}\n\n"
        f"【智能体权重配置】\n{json.dumps(agent_weights, ensure_ascii=False, indent=2)}\n\n"
        f"【结构化综合置信度】\n{json.dumps(confidence_context or {}, ensure_ascii=False, indent=2)}"
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
