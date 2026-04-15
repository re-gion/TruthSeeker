"""Forensics Agent - 视听鉴伪Agent，调用真实检测 API + LLM 推理"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.agents.state import TruthSeekerState, EvidenceItem, AgentLog
from app.agents.tools.deepfake_api import analyze_media
from app.agents.tools.fallback import fallback_metadata_analysis, minimal_forensics_result, sharedshared_degradation
from app.agents.tools.llm_client import forensics_interpret
from app.agents.tools.text_detection import analyze_text
from app.utils.supabase_client import supabase as supabase_client

# 文本内容最大字符数（避免过长文本超出 LLM token 限制）
TEXT_MAX_CHARS = 10000


async def forensics_node(state: TruthSeekerState) -> dict:
    """
    视听鉴伪Agent：
    1. 根据输入类型选择检测通道（媒体 → Reality Defender，文本 → AI 生成检测）
    2. 解析检测结果，提取帧级/音频/视觉/文本证据
    3. LLM 深度解读，生成结构化鉴证报告
    """
    task_id = state["task_id"]
    input_type = state.get("input_type", "video")
    input_files = state.get("input_files", {})
    round_num = state.get("current_round", 1)

    logs: list[AgentLog] = []
    evidence: list[EvidenceItem] = []
    timeline_events: list[dict] = []

    def log(log_type: str, content: str) -> AgentLog:
        entry: AgentLog = {
            "agent": "forensics",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(entry)
        return entry

    log("thinking", f"🔍 鉴伪Agent 启动，任务 ID: {task_id}")
    log("thinking", f"📁 输入类型: {input_type}")

    primary_url = input_files.get("primary", input_files.get("url", ""))

    # 默认值
    is_deepfake = False
    confidence = 0.0
    deepfake_prob = 0.0
    model_scores: list = []
    frame_inferences: list = []
    audio_score = None
    indicators: list = []
    result: dict = {"model": "unknown", "details": {}}
    degradation_status = "full"

    # ================================================================
    #  文本检测通道
    # ================================================================
    if input_type == "text":
        log("action", "📝 检测到文本输入，启动文本 AI 生成检测...")
        text_content = ""

        if primary_url and not primary_url.startswith("mock://"):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(primary_url, follow_redirects=True)
                    text_content = resp.text[:TEXT_MAX_CHARS]
            except Exception:
                text_content = ""

        if not text_content:
            try:
                task_resp = supabase_client.table("tasks").select("description").eq("id", task_id).execute()
                if task_resp.data:
                    text_content = task_resp.data[0].get("description", "")
            except Exception:
                pass

        if not text_content:
            text_content = "（无法获取文本内容）"

        try:
            text_result = await analyze_text(text_content)
            is_deepfake = text_result.get("is_ai_generated", False)
            deepfake_prob = text_result.get("ai_probability", 0.0)
            confidence = text_result.get("confidence", 0.5)
            indicators = text_result.get("anomalies", [])
            result = {
                "is_deepfake": is_deepfake,
                "confidence": confidence,
                "deepfake_probability": deepfake_prob,
                "model": "text_detection",
                "details": {
                    "ai_probability": deepfake_prob,
                    "manipulation_score": text_result.get("manipulation_score", 0.0),
                    "structural_analysis": text_result.get("structural_analysis", {}),
                    "key_claims": text_result.get("key_claims", []),
                },
            }

            if is_deepfake:
                log("finding", f"🚨 文本检测发现 AI 生成特征！AI概率: {deepfake_prob:.1%}，置信度: {confidence:.1%}")
            else:
                log("finding", f"✅ 文本未检测到明显 AI 生成特征，AI概率: {deepfake_prob:.1%}")

            for anomaly in indicators[:3]:
                log("finding", f"  → {anomaly}")

        except Exception as e:
            log("action", f"❌ 文本检测异常: {e}")
            confidence = 0.2
            indicators = [f"文本检测失败: {e}"]
            result = {
                "is_deepfake": False, "confidence": 0.2,
                "deepfake_probability": 0.0, "model": "degraded",
                "degraded": True, "details": {"error": str(e)},
            }

    # ================================================================
    #  媒体检测通道 (默认)
    # ================================================================
    else:
        log("action", "📡 正在连接 Reality Defender 深度鉴伪服务...")
        degradation_status = shared_degradation.getshared_degradation_level("reality_defender")

        try:
            result = await analyze_media(primary_url, input_type)
            shared_degradation.report_success("reality_defender")
            degradation_status = shared_degradation.getshared_degradation_level("reality_defender")

            model_used = result.get("model", "unknown")
            if model_used.startswith("mock"):
                log("action", "⚠️  Reality Defender API 不可用，使用降级模式分析")
            else:
                log("action", f"✅ Reality Defender API 连接成功")

            deepfake_prob = result.get("deepfake_probability", 0.0)
            is_deepfake = result.get("is_deepfake", False)
            confidence = result.get("confidence", 0.0)
            model_scores = result.get("models", [])
            frame_inferences = result.get("frame_inferences", [])
            audio_score = result.get("audio_score")
            indicators = result.get("details", {}).get("indicators", [])

            if is_deepfake:
                log("finding", f"🚨 检测到 Deepfake 篡改！伪造概率: {deepfake_prob:.1%}，置信度: {confidence:.1%}")
                if frame_inferences:
                    suspicious_frames = [f for f in frame_inferences if f.get("label", "").upper() == "FAKE"]
                    log("finding", f"🎬 可疑帧: {len(suspicious_frames)}/{len(frame_inferences)} 帧被标记为伪造")
                if audio_score is not None:
                    log("finding", f"🔊 音频轨道评分: {audio_score:.1%}")
            else:
                log("finding", f"✅ 未检测到明显 Deepfake 篡改，伪造概率: {deepfake_prob:.1%}，置信度: {confidence:.1%}")

            if model_scores:
                for ms in model_scores[:3]:
                    log("finding", f"  → 模型 {ms.get('name', '?')}: {ms.get('label', '?')} ({ms.get('score', 0):.1%})")

            for indicator in indicators[:3]:
                log("finding", f"  → {indicator}")

        except Exception as e:
            shared_degradation.report_failure("reality_defender", e)
            degradation_status = shared_degradation.getshared_degradation_level("reality_defender")
            log("action", f"❌ Reality Defender API 调用异常: {type(e).__name__}: {e}")
            log("action", f"🔄 降级策略: degradation_level={degradation_status}")

            if degradation_status == "degraded":
                log("action", "📊 使用元数据启发式降级分析...")
                try:
                    result = await fallback_metadata_analysis(primary_url, input_type)
                    is_deepfake = result.get("is_deepfake", False)
                    confidence = result.get("confidence", 0.3)
                    deepfake_prob = result.get("deepfake_probability", 0.0)
                    model_scores = result.get("models", [])
                    frame_inferences = result.get("frame_inferences", [])
                    audio_score = result.get("audio_score")
                    indicators = result.get("details", {}).get("indicators", [])
                except Exception as e2:
                    log("action", f"❌ 降级分析也失败: {e2}")
                    result = minimal_forensics_result(input_type)
                    is_deepfake = False
                    confidence = 0.2
                    deepfake_prob = 0.0
                    indicators = ["所有 API 不可用，建议人工复核"]
            else:
                result = minimal_forensics_result(input_type)
                is_deepfake = False
                confidence = 0.2
                deepfake_prob = 0.0
                indicators = ["所有 API 不可用，建议人工复核"]

    # ================================================================
    #  共享后续逻辑 — 证据板 + LLM + 结果汇总
    # ================================================================
    forensics_score = confidence

    # LLM 深度解读检测结果
    llm_analysis = ""
    log("action", "🧠 正在调用大模型进行深度鉴证推理...")
    try:
        llm_analysis = await forensics_interpret(result, input_type)
        if llm_analysis.startswith("[LLM降级]"):
            log("action", "⚠️  LLM 推理不可用，使用降级模式")
        else:
            log("finding", f"🧠 LLM 鉴证分析完成，生成 {len(llm_analysis)} 字专业报告")
    except Exception as e:
        llm_analysis = f"[LLM降级] 鉴证推理异常: {e}"
        log("action", f"⚠️  LLM 推理异常: {e}")

    # 构建证据条目
    evidence_type = (
        "text" if input_type == "text"
        else "visual" if input_type in ("video", "image")
        else "audio"
    )
    evidence_item: EvidenceItem = {
        "type": evidence_type,
        "source": "forensics_agent",
        "description": (
            f"鉴证分析：{'检测到 Deepfake 篡改' if is_deepfake else '未检测到明显篡改'}，"
            f"伪造概率 {deepfake_prob:.1%}，置信度 {confidence:.1%}"
        ),
        "confidence": confidence,
        "metadata": {
            "deepfake_probability": deepfake_prob,
            "is_deepfake": is_deepfake,
            "model_scores": model_scores[:5],
            "frame_inferences": [
                {"frame": f.get("frame"), "score": f.get("score"), "label": f.get("label")}
                for f in frame_inferences[:10]
            ],
            "audio_score": audio_score,
            "indicators": indicators[:5],
            "details": result.get("details", {}),
        },
    }
    evidence.append(evidence_item)

    # 汇总 forensics_result
    forensics_result = {
        "is_deepfake": is_deepfake,
        "deepfake_probability": deepfake_prob,
        "confidence": confidence,
        "forensics_score": forensics_score,
        "model_used": result.get("model", "unknown"),
        "model_scores": model_scores[:5],
        "frame_inferences_count": len(frame_inferences),
        "audio_score": audio_score,
        "indicators": indicators[:5],
        "degraded": result.get("degraded", False) or degradation_status != "full",
        "degradation_status": degradation_status,
        "llm_analysis": llm_analysis,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 置信度历史
    confidence_history = list(state.get("confidence_history", []))
    confidence_history.append({
        "round": round_num,
        "scores": {"forensics": forensics_score},
    })

    verdict_hint = "suspicious" if is_deepfake else "authentic"
    log("conclusion", f"🔬 鉴证分析完成。评估: {verdict_hint}，置信度: {confidence:.1%}")
    log("conclusion", "📋 鉴证报告已提交证据板，等待质询官交叉验证...")

    timeline_events.append({
        "round": round_num,
        "agent": "forensics",
        "event_type": "analysis_complete",
        "summary": f"鉴证完成: {verdict_hint}, 置信度 {confidence:.1%}",
    })

    return {
        "forensics_result": forensics_result,
        "evidence_board": evidence,
        "confidence_history": confidence_history,
        "logs": logs,
        "timeline_events": timeline_events,
        "degradation_status": {"reality_defender": degradation_status} if input_type != "text" else {},
    }
