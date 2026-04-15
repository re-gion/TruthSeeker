"""文本检测工具 - AI 生成文本检测与操纵分析

支持三个维度的文本深度伪造 / AI 操纵检测：
1. LLM 分析：使用 Kimi 大模型识别 AI 生成模式
2. URL 提取：从文本中提取所有 URL 供 OSINT 智能体进一步分析
3. 结构分析：纯本地统计，检测句长均匀性、词汇多样性等异常特征
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timezone

from app.agents.tools.llm_client import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. LLM-based AI text detection
# ---------------------------------------------------------------------------

async def analyze_text_llm(text_content: str) -> dict:
    """使用 Kimi LLM 分析文本中的 AI 生成特征。

    Returns:
        包含 ai_probability, manipulation_score, key_claims, anomalies,
        writing_style_analysis 的字典。LLM 调用失败时返回降级结果。
    """
    llm = get_llm()
    llm = llm.bind(temperature=0.2)  # 降低温度以获得更确定性的 JSON 输出

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "你是一位专攻 AI 生成文本检测的分析专家。"
            "你需要对给定的文本进行深入分析，识别其中的 AI 生成痕迹、情绪操纵手法、"
            "事实不一致性和文体风格异常。"
            "请以严格的 JSON 格式输出分析结果，包含以下字段：\n"
            "- ai_probability: AI 生成概率（0 到 1 之间的浮点数）\n"
            "- manipulation_score: 操纵评分（0 到 1 之间的浮点数，越高表示越可能包含操纵性内容）\n"
            "- key_claims: 文本中的关键声明列表（字符串数组）\n"
            "- anomalies: 检测到的异常特征列表（字符串数组，用中文描述）\n"
            "- writing_style_analysis: 写作风格分析（中文描述字符串）\n"
            "请务必只输出合法的 JSON，不要添加任何额外文字或 Markdown 代码块标记。",
        ),
        (
            "human",
            "请分析以下文本：\n\n{text_content}",
        ),
    ])
    chain = prompt | llm | StrOutputParser()

    fallback = {
        "ai_probability": 0.5,
        "manipulation_score": 0.0,
        "key_claims": [],
        "anomalies": ["LLM 分析未能执行，已降级为默认结果"],
        "writing_style_analysis": "无法完成写作风格分析",
    }

    try:
        raw_output = await chain.ainvoke({"text_content": text_content})
        # 尝试解析 JSON —— 可能被 ```json 包裹
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            # 去除 markdown 代码块标记
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        result = json.loads(cleaned)

        # 确保必要字段存在且类型正确
        result.setdefault("ai_probability", 0.5)
        result.setdefault("manipulation_score", 0.0)
        result.setdefault("key_claims", [])
        result.setdefault("anomalies", [])
        result.setdefault("writing_style_analysis", "")

        # 将概率夹到 [0, 1]
        result["ai_probability"] = max(0.0, min(1.0, float(result["ai_probability"])))
        result["manipulation_score"] = max(0.0, min(1.0, float(result["manipulation_score"])))
        if not isinstance(result["key_claims"], list):
            result["key_claims"] = []
        if not isinstance(result["anomalies"], list):
            result["anomalies"] = []
        return result

    except json.JSONDecodeError as exc:
        logger.warning("analyze_text_llm 返回非法 JSON: %s | 原始输出: %.200s", exc, raw_output)
        return fallback
    except Exception as exc:
        logger.exception("analyze_text_llm LLM 调用失败: %s", exc)
        return fallback


# ---------------------------------------------------------------------------
# 2. URL extraction
# ---------------------------------------------------------------------------

def extract_urls_from_text(text: str) -> list[str]:
    """从文本中提取所有 http/https URL。

    Returns:
        URL 字符串列表。
    """
    url_pattern = re.compile(
        r'https?://'            # http:// or https://
        r'[^\s<>"\'\]\)}）】]+'  # 非空白/常见右括号类字符
    )
    return url_pattern.findall(text)


# ---------------------------------------------------------------------------
# 3. Structural / statistical analysis (pure local, no API)
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """简单的中英文混合分句。"""
    # 按常见句末标点分割，同时保留中文标点
    parts = re.split(r'(?<=[。！？.!?\n])', text)
    sentences = [s.strip() for s in parts if s.strip()]
    if not sentences:
        # 如果没有句末标点，整段作为一个句子
        sentences = [text.strip()] if text.strip() else []
    return sentences


def _split_words(text: str) -> list[str]:
    """简单的中英文混合分词。

    对中文按字符拆分（粗粒度），对英文按空格拆分。
    对于更精确的分析可替换为 jieba 等分词库，此处保持轻量。
    """
    words: list[str] = []
    # 提取英文单词
    words.extend(re.findall(r'[a-zA-Z]+', text.lower()))
    # 提取中文字符（每个字作为一个 token）
    words.extend(re.findall(r'[\u4e00-\u9fff]', text))
    return words


def analyze_text_structure(text: str) -> dict:
    """纯本地统计分析，检测文本结构异常。

    分析维度包括句长分布、词汇多样性、长度均匀性等。

    Returns:
        包含 sentence_count, avg_sentence_length, type_token_ratio,
        sentence_length_std, length_uniformity_score, vocabulary_diversity,
        anomalies 的字典。
    """
    anomalies: list[str] = []

    sentences = _split_sentences(text)
    sentence_count = len(sentences)

    if sentence_count < 2:
        anomalies.append("文本过短，无法进行可靠的结构分析")
        return {
            "sentence_count": sentence_count,
            "avg_sentence_length": 0.0,
            "type_token_ratio": 0.0,
            "sentence_length_std": 0.0,
            "length_uniformity_score": 0.0,
            "vocabulary_diversity": 0.0,
            "anomalies": anomalies,
        }

    # 句长列表（以字符数计）
    lengths = [len(s) for s in sentences]
    avg_length = sum(lengths) / sentence_count

    # 标准差
    variance = sum((l - avg_length) ** 2 for l in lengths) / sentence_count
    std_dev = math.sqrt(variance)

    # 句长均匀性评分：标准差越小越均匀 → 越可能为 AI 生成
    # 使用 sigmoid 式映射，std < 3.0 时评分 > 0.7
    if std_dev < 1.0:
        uniformity_score = 0.95
    elif std_dev < 3.0:
        uniformity_score = 0.7 + (3.0 - std_dev) / 6.67  # 3.0→0.7, 1.0→0.95 附近
        uniformity_score = min(1.0, max(0.7, uniformity_score))
    else:
        # std_dev >= 3.0：均匀性较低
        uniformity_score = max(0.0, min(0.7, 3.0 / std_dev))

    if std_dev < 3.0:
        anomalies.append("句长异常均匀，疑似 AI 生成")

    # 词汇多样性：Type-Token Ratio
    words = _split_words(text)
    total_words = len(words)
    if total_words == 0:
        ttr = 0.0
        vocabulary_diversity = 0.0
    else:
        unique_words = len(set(words))
        ttr = unique_words / total_words
        vocabulary_diversity = ttr  # 直接使用 TTR 作为多样性指标

    if ttr < 0.3 and total_words > 10:
        anomalies.append("词汇多样性偏低，疑似 AI 生成")

    return {
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_length, 2),
        "type_token_ratio": round(ttr, 4),
        "sentence_length_std": round(std_dev, 2),
        "length_uniformity_score": round(uniformity_score, 4),
        "vocabulary_diversity": round(vocabulary_diversity, 4),
        "anomalies": anomalies,
    }


# ---------------------------------------------------------------------------
# 4. Main entry point
# ---------------------------------------------------------------------------

async def analyze_text(text_content: str) -> dict:
    """文本检测主入口，编排三种分析维度。

    1. 并发执行 LLM 分析和结构分析
    2. 提取 URL（供 OSINT 智能体后续处理）
    3. 汇总为统一评估结果

    Returns:
        包含 is_ai_generated, ai_probability, manipulation_score,
        structural_analysis, key_claims, anomalies, extracted_urls,
        confidence, timestamp 的字典。
    """
    # 并发执行 LLM 分析和结构分析
    # analyze_text_structure 是同步函数，需包装为协程
    async def _run_structural():
        return analyze_text_structure(text_content)

    llm_result, structural_result = await asyncio.gather(
        analyze_text_llm(text_content),
        _run_structural(),
        return_exceptions=True,
    )

    # 处理可能的异常
    if isinstance(llm_result, Exception):
        logger.error("analyze_text_llm 抛出异常: %s", llm_result)
        llm_result = {
            "ai_probability": 0.5,
            "manipulation_score": 0.0,
            "key_claims": [],
            "anomalies": [f"LLM 分析异常: {llm_result}"],
            "writing_style_analysis": "分析失败",
        }

    if isinstance(structural_result, Exception):
        logger.error("analyze_text_structure 抛出异常: %s", structural_result)
        structural_result = {
            "sentence_count": 0,
            "avg_sentence_length": 0.0,
            "type_token_ratio": 0.0,
            "sentence_length_std": 0.0,
            "length_uniformity_score": 0.0,
            "vocabulary_diversity": 0.0,
            "anomalies": [f"结构分析异常: {structural_result}"],
        }

    # 提取 URL
    extracted_urls = extract_urls_from_text(text_content)

    # 合并结果
    ai_probability = llm_result.get("ai_probability", 0.5)
    manipulation_score = llm_result.get("manipulation_score", 0.0)
    key_claims = llm_result.get("key_claims", [])
    llm_anomalies = llm_result.get("anomalies", [])
    structural_anomalies = structural_result.get("anomalies", [])

    # 判断是否 AI 生成
    is_ai_generated = ai_probability > 0.6

    # 计算置信度：基于 LLM 与结构分析的一致性
    # 结构分析的 length_uniformity_score 高 → 也暗示 AI
    structural_hint = structural_result.get("length_uniformity_score", 0.0)
    llm_hint = ai_probability

    # 两者越一致，置信度越高
    agreement = 1.0 - abs(llm_hint - structural_hint)
    # 基础置信度 0.5，一致时提升到 0.8+，不一致时降低
    confidence = 0.5 + agreement * 0.35
    confidence = max(0.2, min(0.95, confidence))

    # 如果结构分析表明文本太短，降低置信度
    if structural_result.get("sentence_count", 0) < 3:
        confidence *= 0.6

    # 合并异常列表
    all_anomalies = list(dict.fromkeys(llm_anomalies + structural_anomalies))

    return {
        "is_ai_generated": is_ai_generated,
        "ai_probability": ai_probability,
        "manipulation_score": manipulation_score,
        "structural_analysis": structural_result,
        "key_claims": key_claims,
        "anomalies": all_anomalies,
        "extracted_urls": extracted_urls,
        "confidence": round(confidence, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
