"""Forensics Agent - 视听鉴伪Agent分析节点"""
import asyncio
from datetime import datetime, timezone
from app.agents.state import TruthSeekerState, EvidenceItem, AgentLog
from app.agents.tools.deepfake_api import analyze_media


async def forensics_node(state: TruthSeekerState) -> dict:
    """
    视听鉴伪Agent Agent：
    1. 分析媒体文件（调用 Reality Defender API / 模拟）
    2. 提取证据
    3. 记录分析日志
    """
    task_id = state["task_id"]
    input_type = state.get("input_type", "video")
    input_files = state.get("input_files", {})
    round_num = state.get("current_round", 1)

    logs: list[AgentLog] = []
    evidence: list[EvidenceItem] = []

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

    # 1. 开始分析
    log("thinking", f"🔬 视听鉴伪Agent Agent 启动，任务 ID: {task_id}，输入类型: {input_type}")
    log("thinking", "📁 正在加载媒体文件，准备执行多维度取证分析...")

    await asyncio.sleep(0.5)

    # 2. 调用 Deepfake 检测 API
    file_url = input_files.get("primary", input_files.get("video", "mock://default"))
    log("action", f"🌐 调用 Deepfake 检测 API，分析目标: {file_url}")

    detection_result = await analyze_media(file_url, input_type)
    model_used = detection_result.get("model", "unknown")

    log("action", f"⚡ API 调用完成，使用模型: {model_used}，耗时约 2.1s")

    # 3. 解析结果
    is_deepfake = detection_result["is_deepfake"]
    confidence = detection_result["confidence"]
    deepfake_prob = detection_result["deepfake_probability"]
    details = detection_result.get("details", {})
    indicators = details.get("indicators", [])

    # 4. 生成证据条目
    evidence_type = "visual" if input_type in ("video", "image") else "audio"
    evidence_item: EvidenceItem = {
        "type": evidence_type,
        "source": "forensics_agent",
        "description": (
            f"Deepfake 检测：{'⚠️ 疑似伪造' if is_deepfake else '✅ 疑似真实'}，"
            f"置信度 {confidence:.1%}，模型: {model_used}"
        ),
        "confidence": confidence,
        "metadata": {
            "is_deepfake": is_deepfake,
            "deepfake_probability": deepfake_prob,
            "indicators": indicators,
            "frames_analyzed": details.get("frames_analyzed", 1),
        },
    }
    evidence.append(evidence_item)

    # 5. 记录发现
    verdict_str = "⚠️ 疑似 AI 生成/深度伪造" if is_deepfake else "✅ 未发现明显伪造特征"
    log("finding", f"🔍 分析完成：{verdict_str}")
    log("finding", f"📊 Deepfake 概率: {deepfake_prob:.1%} | 检测置信度: {confidence:.1%}")

    if indicators:
        for indicator in indicators:
            log("finding", f"  → {indicator}")

    # 6. 输出法医报告
    forensics_report = {
        "is_deepfake": is_deepfake,
        "confidence": confidence,
        "deepfake_probability": deepfake_prob,
        "evidence_count": len(evidence),
        "indicators": indicators,
        "model": model_used,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log("conclusion", (
        f"📋 法医报告已生成。结论：{'媒体存在深度伪造特征' if is_deepfake else '媒体未发现伪造痕迹'}。"
        f"提交研判指挥Agent进行最终裁决..."
    ))

    return {
        "forensics_result": forensics_report,
        "evidence_board": evidence,
        "logs": logs,
        "confidence_history": [
            {
                "round": round_num,
                "scores": {"forensics": confidence},
            }
        ],
    }
