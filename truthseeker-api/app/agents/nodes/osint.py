"""OSINT Agent - 情报溯源Agent，负责 URL/域名/IP 情报分析 + LLM 推理"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
from app.agents.state import TruthSeekerState, EvidenceItem, AgentLog
from app.agents.tools.fallback import fallback_osint_analysis, minimal_osint_result, shared_degradation
from app.agents.tools.threat_intel import analyze_urls, check_domain_reputation, scan_file_hash, extract_media_metadata
from app.agents.tools.llm_client import osint_interpret
from app.agents.tools.text_detection import extract_urls_from_text


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

    # 文本输入类型：从文本内容中提取 URL
    if input_type == "text" and not urls_to_check:
        log("action", "📝 文本输入模式，尝试从文本中提取 URL 进行情报分析...")
        text_content = ""
        # 尝试获取文本内容
        try:
            from app.utils.supabase_client import supabase as supabase_client
            task_resp = supabase_client.table("tasks").select("description").eq("id", task_id).execute()
            if task_resp.data:
                text_content = task_resp.data[0].get("description", "")
        except Exception:
            pass

        if text_content:
            extracted_urls = extract_urls_from_text(text_content)
            if extracted_urls:
                urls_to_check = extracted_urls
                log("finding", f"🔗 从文本中提取到 {len(extracted_urls)} 个 URL")
            else:
                log("finding", "📋 文本中未发现 URL，OSINT 情报贡献有限")

    degradation_status = shared_degradation.get_degradation_level("virustotal")

    threat_score = 0.0
    threat_indicators = []
    domain_info = {}
    virustotal_result = None

    if urls_to_check:
        log("action", f"🔍 正在查询威胁情报数据库，目标: {urls_to_check[0][:60]}...")
        await asyncio.sleep(0.5)

        try:
            intel_result = await analyze_urls(urls_to_check)
            shared_degradation.report_success("virustotal")
            degradation_status = shared_degradation.get_degradation_level("virustotal")
        except Exception as e:
            shared_degradation.report_failure("virustotal", e)
            degradation_status = shared_degradation.get_degradation_level("virustotal")
            log("action", f"❌ VirusTotal API 调用异常: {type(e).__name__}: {e}")
            log("action", f"🔄 降级策略: degradation_level={degradation_status}")

            if degradation_status == "degraded":
                try:
                    intel_result = await fallback_osint_analysis(urls_to_check[0], input_type)
                    log("action", "📊 使用元数据启发式降级分析...")
                except Exception:
                    intel_result = minimal_osint_result(input_type)
                    log("action", "⚠️  元数据降级分析也失败，使用最小降级结果")
            else:
                intel_result = minimal_osint_result(input_type)

        threat_score = intel_result.get("threat_score", 0.0)
        threat_indicators = intel_result.get("indicators", [])
        domain_info = intel_result.get("domain_info", {})
        virustotal_result = intel_result.get("virustotal", {})

        if threat_score > 0.7:
            log("finding", f"🚨 高威胁！VirusTotal 检测到恶意标记: {virustotal_result.get('malicious', 0) if virustotal_result else 0} 家")
        elif threat_score > 0.4:
            log("finding", f"⚠️  中等风险，部分安全厂商标记可疑: {threat_score:.1%}")
        else:
            log("finding", f"✅ URL 情报检查通过，威胁分数: {threat_score:.1%}")
    else:
        # 对媒体文件做元数据分析与文件哈希扫描
        log("action", "📋 无外部 URL，转为分析媒体元数据与文件哈希威胁情报...")
        await asyncio.sleep(0.4)

        file_url = primary_url or "mock://unknown"

        # 并发调用文件哈希扫描和元数据提取
        vt_scan_task = asyncio.create_task(scan_file_hash(file_url))
        metadata_task = asyncio.create_task(extract_media_metadata(file_url, input_type))

        vt_scan_result, metadata_result = await asyncio.gather(
            vt_scan_task, metadata_task, return_exceptions=True
        )

        # 处理异常结果
        if isinstance(vt_scan_result, Exception):
            shared_degradation.report_failure("virustotal", vt_scan_result)
            log("warning", f"⚠️  文件哈希扫描失败: {vt_scan_result}")
            vt_scan_result = {
                "malicious": 0, "suspicious": 0, "total_scans": 0,
                "threat_score": 0.0, "hash": "", "scan_available": False,
            }
        else:
            # scan_file_hash succeeded (even if no VT key — it returned a result)
            shared_degradation.report_success("virustotal")

        degradation_status = shared_degradation.get_degradation_level("virustotal")

        if isinstance(metadata_result, Exception):
            log("warning", f"⚠️  元数据提取失败: {metadata_result}")
            metadata_result = {
                "format": "unknown", "dimensions": None, "duration_seconds": None,
                "has_exif": False, "exif_anomalies": [], "file_size_approx": 0,
                "compression_artifacts": False, "manipulation_indicators": [],
            }

        # 构建 threat_indicators
        threat_indicators = []

        # 来自元数据分析的异常指标
        exif_anomalies = metadata_result.get("exif_anomalies", [])
        manipulation_indicators = metadata_result.get("manipulation_indicators", [])
        threat_indicators.extend(exif_anomalies)
        threat_indicators.extend(manipulation_indicators)

        if metadata_result.get("compression_artifacts"):
            threat_indicators.append("检测到高压缩率，可能经历多次编码")

        # 来自 VirusTotal 的扫描结果
        if vt_scan_result.get("scan_available"):
            vt_malicious = vt_scan_result.get("malicious", 0)
            vt_suspicious = vt_scan_result.get("suspicious", 0)
            if vt_malicious > 0:
                threat_indicators.append(f"VirusTotal: {vt_malicious} 家厂商标记为恶意")
            if vt_suspicious > 0:
                threat_indicators.append(f"VirusTotal: {vt_suspicious} 家厂商标记为可疑")
            log("action", f"🔍 文件哈希 {vt_scan_result.get('hash', '')[:16]}... 在 VirusTotal 中已收录")
        else:
            if vt_scan_result.get("hash"):
                log("action", f"🔍 文件哈希 {vt_scan_result.get('hash', '')[:16]}... 未在 VirusTotal 中找到记录")

        # 计算 threat_score（综合元数据和 VT 结果）
        vt_threat = vt_scan_result.get("threat_score", 0.0)
        meta_factor = 0.0
        if exif_anomalies:
            meta_factor += 0.15 * len(exif_anomalies)
        if manipulation_indicators:
            meta_factor += 0.2 * len(manipulation_indicators)
        if metadata_result.get("compression_artifacts"):
            meta_factor += 0.1
        if not metadata_result.get("has_exif") and metadata_result.get("format") in ("jpeg", "png"):
            meta_factor += 0.1

        threat_score = min(1.0, max(vt_threat, meta_factor * 0.5))

        # 构建 domain_info（来自元数据）
        domain_info = {
            "source": "media_metadata",
            "file_hash": vt_scan_result.get("hash", ""),
            "input_type": input_type,
            "format": metadata_result.get("format", "unknown"),
            "dimensions": metadata_result.get("dimensions"),
            "has_exif": metadata_result.get("has_exif", False),
        }

        # 构建 virustotal_result
        virustotal_result = vt_scan_result

        # 日志输出
        if threat_score > 0.4:
            log("finding", f"⚠️  媒体分析发现异常，威胁评分: {threat_score:.1%}")
        elif threat_score > 0.1:
            log("finding", f"🔍 媒体分析发现轻微异常，威胁评分: {threat_score:.1%}")
        else:
            log("finding", f"✅ 媒体元数据检查通过，威胁评分: {threat_score:.1%}")

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

    # LLM 深度解读情报结果
    llm_analysis = ""
    log("action", "🧠 正在调用大模型进行深度情报推理...")
    try:
        llm_analysis = await osint_interpret(osint_result, input_type)
        if llm_analysis.startswith("[LLM降级]"):
            log("action", "⚠️  LLM 情报推理不可用，使用降级模式")
        else:
            log("finding", f"🧠 LLM 情报分析完成，生成 {len(llm_analysis)} 字专业报告")
    except Exception as e:
        llm_analysis = f"[LLM降级] 情报推理异常: {e}"
        log("action", f"⚠️  LLM 情报推理异常: {e}")

    # 将 LLM 分析添加到结果中
    osint_result["llm_analysis"] = llm_analysis

    log("conclusion", f"🕵️  OSINT 分析完成。溯源评估: {risk_level}，置信度: {osint_confidence:.1%}")
    log("conclusion", "📡 情报报告已提交证据板，等待质询官审核...")

    return {
        "osint_result": osint_result,
        "evidence_board": evidence,
        "degradation_status": {"virustotal": degradation_status},
        "logs": logs,
    }
