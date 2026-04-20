"""LLM client wrapper for TruthSeeker multi-agent deepfake detection system.

Wraps the Kimi/Moonshot API (OpenAI-compatible) using langchain-openai's ChatOpenAI.
Each agent-specific function builds a prompt chain and invokes the LLM asynchronously.
On failure, gracefully degrades to a rule-based fallback string.
"""
from __future__ import annotations

import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings

logger = logging.getLogger(__name__)


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI instance configured for Kimi/Moonshot API."""
    return ChatOpenAI(
        model="moonshot-v1-8k",
        base_url=settings.KIMI_BASE_URL,
        api_key=settings.KIMI_API_KEY,
        temperature=0.3,
        max_tokens=2048,
    )


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
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_template),
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        return await chain.ainvoke(variables)
    except Exception as exc:
        logger.exception("LLM 调用失败: %s", exc)
        return fallback_text


# ---------------------------------------------------------------------------
# Forensics Agent
# ---------------------------------------------------------------------------

async def forensics_interpret(raw_api_result: dict, input_type: str, case_prompt: str = "") -> str:
    """Let the LLM interpret raw forensic detection results into professional analysis."""
    return await _invoke_llm(
        system_prompt=(
            "你是一位专攻深度伪造检测的取证分析专家。"
            "你需要对传入的原始检测结果进行专业解读，撰写结构清晰、术语准确的中文取证分析报告。"
            "报告应包含：1) 检测结论（是否为伪造及置信度）；2) 关键技术指标分析；"
            "3) 检测模型的推断细节；4) 潜在影响与风险提示。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
        ),
        human_template=(
            "全局检测目标/案件背景：{case_prompt}\n\n"
            "输入媒体类型：{input_type}\n\n原始检测结果：\n{raw_data}"
        ),
        variables={
            "case_prompt": case_prompt or "用户未补充额外提示。",
            "input_type": input_type,
            "raw_data": json.dumps(raw_api_result, ensure_ascii=False, indent=2),
        },
        fallback_text=(
            f"[LLM降级] 基于规则推断: 检测对象类型={input_type}, "
            f"是否伪造={raw_api_result.get('is_deepfake', False)}, "
            f"置信度/概率={raw_api_result.get('deepfake_probability', raw_api_result.get('confidence', 'N/A'))}。"
            f"原始数据如下: {json.dumps(raw_api_result, ensure_ascii=False)}"
        ),
    )


# ---------------------------------------------------------------------------
# OSINT Agent
# ---------------------------------------------------------------------------

async def osint_interpret(raw_intel: dict, input_type: str, case_prompt: str = "") -> str:
    """Let the LLM interpret raw OSINT intelligence into a professional assessment."""
    indicators = raw_intel.get("indicators", [])
    return await _invoke_llm(
        system_prompt=(
            "你是一位专攻威胁评估的开源情报(OSINT)分析师。"
            "你需要对传入的原始情报数据进行专业研判，撰写结构清晰、逻辑严密的中文情报评估报告。"
            "报告应包含：1) 威胁等级判定；2) 关键指标与异常信号分析；"
            "3) 来源可信度评估；4) 关联风险与溯源线索。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
        ),
        human_template=(
            "全局检测目标/案件背景：{case_prompt}\n\n"
            "输入媒体类型：{input_type}\n\n原始情报数据：\n{raw_data}"
        ),
        variables={
            "case_prompt": case_prompt or "用户未补充额外提示。",
            "input_type": input_type,
            "raw_data": json.dumps(raw_intel, ensure_ascii=False, indent=2),
        },
        fallback_text=(
            f"[LLM降级] 基于规则推断: 威胁评分={raw_intel.get('threat_score', 'N/A')}, "
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
) -> str:
    """Let the LLM cross-validate evidence from forensics and OSINT agents."""
    return await _invoke_llm(
        system_prompt=(
            "你是一位批判性思维挑战者，职责是交叉验证多个智能体的证据。"
            "你需要仔细比对取证分析与情报评估的结论，找出其中的矛盾、"
            "薄弱证据、逻辑漏洞，或在证据一致时予以确认。"
            "请撰写结构化的中文交叉验证报告，包含："
            "1) 证据一致性总览；2) 矛盾与差异点；3) 薄弱环节与不确定性；"
            "4) 需要进一步调查的问题；5) 整体证据链强度评级(强/中/弱)。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
        ),
        human_template=(
            "【全局检测目标/案件背景】\n{case_prompt}\n\n"
            "【取证分析结果】\n{forensics_data}\n\n"
            "【情报评估结果】\n{osint_data}\n\n"
            "【已有质疑记录】\n{challenges_data}"
        ),
        variables={
            "case_prompt": case_prompt or "用户未补充额外提示。",
            "forensics_data": json.dumps(forensics, ensure_ascii=False, indent=2),
            "osint_data": json.dumps(osint, ensure_ascii=False, indent=2),
            "challenges_data": json.dumps(challenges, ensure_ascii=False, indent=2),
        },
        fallback_text=(
            "[LLM降级] 基于规则推断: "
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
) -> str:
    """Let the LLM produce a final ruling based on all agent evidence."""
    return await _invoke_llm(
        system_prompt=(
            "你是一位资深指挥官，负责基于全部智能体证据做出最终裁决。"
            "你需要综合取证分析、情报评估和交叉验证三个维度的结论，"
            "结合各智能体的权重配置，撰写权威的中文最终裁决报告。"
            "报告必须包含：1) 最终裁决结论（伪造/真实/无法判定）；"
            "2) 置信度评估与证据链完整性分析；3) 各智能体结论对比与权重考量；"
            "4) 关键分歧点及处理意见；5) 后续取证建议与风险提示。"
            "请直接输出分析文本，不要使用 Markdown 代码块包裹。"
        ),
        human_template=(
            "【全局检测目标/案件背景】\n{case_prompt}\n\n"
            "【取证分析结果】\n{forensics_data}\n\n"
            "【情报评估结果】\n{osint_data}\n\n"
            "【交叉验证反馈】\n{challenger_data}\n\n"
            "【智能体权重配置】\n{weights_data}"
        ),
        variables={
            "case_prompt": case_prompt or "用户未补充额外提示。",
            "forensics_data": json.dumps(forensics, ensure_ascii=False, indent=2),
            "osint_data": json.dumps(osint, ensure_ascii=False, indent=2),
            "challenger_data": json.dumps(challenger_feedback, ensure_ascii=False, indent=2),
            "weights_data": json.dumps(agent_weights, ensure_ascii=False, indent=2),
        },
        fallback_text=(
            "[LLM降级] 基于规则推断: 综合所有智能体证据，"
            f"权重={json.dumps(agent_weights, ensure_ascii=False)}，"
            "裁决未能由 LLM 完成。"
            f"取证={json.dumps(forensics, ensure_ascii=False)[:150]}, "
            f"情报={json.dumps(osint, ensure_ascii=False)[:150]}, "
            f"挑战={json.dumps(challenger_feedback, ensure_ascii=False)[:150]}。"
            "建议人工审核所有证据后做出最终判定。"
        ),
    )
