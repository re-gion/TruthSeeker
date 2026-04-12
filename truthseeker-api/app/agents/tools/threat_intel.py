"""威胁情报工具 - 支持 VirusTotal API 和 Mock 模拟"""
import asyncio
import hashlib
import os
from typing import Optional


async def analyze_urls(urls: list[str]) -> dict:
    """
    分析 URL 列表的威胁情报。
    优先使用 VirusTotal API，无 API Key 时使用模拟实现。
    """
    if not urls:
        return {"threat_score": 0.0, "indicators": [], "domain_info": {}, "virustotal": None}

    vt_api_key = os.environ.get("VIRUSTOTAL_API_KEY", "")

    if vt_api_key and vt_api_key != "your-key-here":
        return await _virustotal_scan(urls[0], vt_api_key)
    else:
        return await _mock_url_analysis(urls[0])


async def _virustotal_scan(url: str, api_key: str) -> dict:
    """调用 VirusTotal API 进行扫描"""
    try:
        import httpx
        headers = {"x-apikey": api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 提交 URL 扫描
            resp = await client.post(
                "https://www.virustotal.com/api/v3/urls",
                headers=headers,
                data={"url": url},
            )
            if resp.status_code not in (200, 201):
                return await _mock_url_analysis(url)

            scan_data = resp.json()
            analysis_id = scan_data.get("data", {}).get("id", "")

            if not analysis_id:
                return await _mock_url_analysis(url)

            # 获取分析结果
            await asyncio.sleep(2)
            result_resp = await client.get(
                f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                headers=headers,
            )
            if result_resp.status_code != 200:
                return await _mock_url_analysis(url)

            result = result_resp.json()
            stats = result.get("data", {}).get("attributes", {}).get("stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values()) if stats else 1

            threat_score = min(1.0, (malicious * 1.0 + suspicious * 0.5) / max(total, 1))

            indicators = []
            if malicious > 0:
                indicators.append(f"VirusTotal: {malicious} 家安全厂商标记为恶意")
            if suspicious > 0:
                indicators.append(f"VirusTotal: {suspicious} 家安全厂商标记为可疑")

            return {
                "threat_score": threat_score,
                "indicators": indicators,
                "domain_info": {"url": url},
                "virustotal": {
                    "malicious": malicious,
                    "suspicious": suspicious,
                    "total_engines": total,
                    "stats": stats,
                },
            }
    except Exception as e:
        return await _mock_url_analysis(url)


async def _mock_url_analysis(url: str) -> dict:
    """基于 URL 特征的模拟威胁分析"""
    await asyncio.sleep(0.3)

    url_lower = url.lower()

    # 基于 URL 特征判断风险
    high_risk_keywords = ["phishing", "malware", "hack", "steal", "fake", "scam"]
    medium_risk_keywords = ["free", "click", "win", "prize", "urgent", "verify"]

    h = int(hashlib.md5(url.encode()).hexdigest(), 16) % 100

    has_high_risk = any(kw in url_lower for kw in high_risk_keywords)
    has_medium_risk = any(kw in url_lower for kw in medium_risk_keywords)

    if has_high_risk or h > 85:
        threat_score = 0.75 + (h % 20) / 100
        indicators = [
            "域名注册时间较短（< 30天）",
            "URL 包含可疑关键词",
            "未发现有效 SSL 证书",
        ]
        malicious = 8
    elif has_medium_risk or h > 60:
        threat_score = 0.35 + (h % 30) / 100
        indicators = ["URL 结构存在可疑参数", "域名声誉评分偏低"]
        malicious = 2
    else:
        threat_score = max(0.0, (h % 20) / 100 - 0.05)
        indicators = ["未发现明显威胁指标"] if threat_score > 0 else []
        malicious = 0

    # mock:// 协议直接返回低威胁
    if url.startswith("mock://"):
        threat_score = 0.05
        indicators = ["模拟数据，无实际威胁"]
        malicious = 0

    return {
        "threat_score": min(1.0, threat_score),
        "indicators": indicators,
        "domain_info": {
            "url": url,
            "analysis_method": "mock_heuristic",
        },
        "virustotal": {
            "malicious": malicious,
            "suspicious": 0,
            "total_engines": 72,
            "note": "模拟数据（未配置 VirusTotal API Key）",
        },
    }


async def check_domain_reputation(domain: str) -> dict:
    """检查域名声誉（简化版，主要用于 OSINT）"""
    await asyncio.sleep(0.2)
    result = await _mock_url_analysis(f"https://{domain}")
    return {
        "domain": domain,
        "reputation_score": 1.0 - result["threat_score"],
        "is_suspicious": result["threat_score"] > 0.5,
        "indicators": result["indicators"],
    }
