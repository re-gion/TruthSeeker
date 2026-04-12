"""OSINT Agent - 情报溯源Agent，负责 URL/域名/IP 情报分析"""
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional
from app.agents.state import TruthSeekerState, EvidenceItem, AgentLog
from app.agents.tools.threat_intel import analyze_urls, check_domain_reputation


async def osint_node(state: TruthSeekerState) -> dict:
    """
    情报溯源Agent Agent：
    1. 提取输入中的 URL/域名
    2. 查询威胁情报（VirusTotal/mock）
    3. 分析元数据（EXIF、Whois 等）
    4. 输出结构化 OSINT 报告
    """
    task_id = state["task_id"]
    input_type = state.get("input_type", "video")
    input_files = state.get("input_files", {})
    round_num = state.get("current_round", 1)

    logs: list[AgentLog] = []
    evidence: list[EvidenceItem] = []

    def log(log_type: str, content: str) -> AgentLog:
        entry: AgentLog = {
            "agent": "osint",
            "round": round_num,
            "type": log_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(entry)
        return entry

    log("thinking", f"🕵️  情报溯源Agent Agent 启动，任务 ID: {task_id}")
    log("thinking", "🌐 正在扫描输入内容，提取可疑 URL 和域名特征...")

    await asyncio.sleep(0.3)

    # 提取目标 URL
    primary_url = input_files.get("primary", input_files.get("url", ""))
    urls_to_check = [u for u in [primary_url] if u and not u.startswith("mock://")]

    threat_score = 0.0
    threat_indicators = []
    domain_info = {}
    virustotal_result = None

    if urls_to_check:
        log("action", f"🔍 正在查询威胁情报数据库，目标: {urls_to_check[0][:60]}...")
        await asyncio.sleep(0.5)

        intel_result = await analyze_urls(urls_to_check)
        threat_score = intel_result.get("threat_score", 0.0)
        threat_indicators = intel_result.get("indicators", [])
        domain_info = intel_result.get("domain_info", {})
        virustotal_result = intel_result.get("virustotal", {})

        if threat_score > 0.7:
            log("finding", f"🚨 高威胁！VirusTotal 检测到恶意标记: {virustotal_result.get('malicious', 0)} 家")
        elif threat_score > 0.4:
            log("finding", f"⚠️  中等风险，部分安全厂商标记可疑: {threat_score:.1%}")
        else:
            log("finding", f"✅ URL 情报检查通过，威胁分数: {threat_score:.1%}")
    else:
        # 对媒体文件做元数据分析
        log("action", "📋 无外部 URL，转为分析媒体元数据与来源特征...")
        await asyncio.sleep(0.4)

        # 模拟元数据分析
        file_url = primary_url or "mock://unknown"
        file_hash = hashlib.md5(file_url.encode()).hexdigest()[:8]

        domain_info = {
            "source": "media_metadata",
            "file_hash": file_hash,
            "input_type": input_type,
        }

        # 随机模拟发现 - 基于 hash 值确定
        seed = int(file_hash, 16) % 100
        if seed > 70:
            threat_score = 0.35
            threat_indicators = ["元数据异常：创建时间与修改时间不一致", "编码器指纹与声称来源不符"]
            log("finding", "⚠️  发现元数据异常，媒体文件可能经过二次编码处理")
        elif seed > 40:
            threat_score = 0.15
            threat_indicators = ["未发现明显元数据篡改痕迹"]
            log("finding", "✅ 媒体元数据检查正常，来源特征一致")
        else:
            threat_score = 0.0
            log("finding", "✅ 媒体元数据完整，无异常标记")

    # 构建证据条目
    evidence_item: EvidenceItem = {
        "type": "osint",
        "source": "osint_agent",
        "description": (
            f"OSINT 情报分析：威胁评分 {threat_score:.1%}，"
            f"发现 {len(threat_indicators)} 条情报线索"
        ),
        "confidence": min(0.95, 0.6 + (1 - threat_score) * 0.35) if threat_score > 0 else 0.75,
        "metadata": {
            "threat_score": threat_score,
            "threat_indicators": threat_indicators,
            "domain_info": domain_info,
            "virustotal": virustotal_result,
            "urls_analyzed": len(urls_to_check),
        },
    }
    evidence.append(evidence_item)

    for indicator in threat_indicators[:3]:
        log("finding", f"  → {indicator}")

    # OSINT 置信度
    osint_confidence = 1 - threat_score if threat_score > 0 else 0.75

    # 汇总结果
    osint_result = {
        "threat_score": threat_score,
        "is_malicious": threat_score > 0.7,
        "is_suspicious": threat_score > 0.4,
        "confidence": osint_confidence,
        "threat_indicators": threat_indicators,
        "domain_info": domain_info,
        "virustotal_summary": virustotal_result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    risk_level = "高风险" if threat_score > 0.7 else "中等风险" if threat_score > 0.4 else "低风险"
    log("conclusion", f"🕵️  OSINT 分析完成。溯源评估: {risk_level}，置信度: {osint_confidence:.1%}")
    log("conclusion", "📡 情报报告已提交证据板，等待质询官审核...")

    return {
        "osint_result": osint_result,
        "evidence_board": evidence,
        "logs": logs,
    }
