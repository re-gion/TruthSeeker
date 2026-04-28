"""威胁情报工具 - 支持 VirusTotal API 和 Mock 模拟"""
import asyncio
import hashlib
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


async def analyze_urls(urls: list[str]) -> dict:
    """
    分析 URL 列表的威胁情报。
    优先使用 VirusTotal API，无 API Key 时使用模拟实现。
    """
    if not urls:
        return {"threat_score": 0.0, "indicators": [], "domain_info": {}, "virustotal": None}

    vt_api_key = settings.VIRUSTOTAL_API_KEY

    if vt_api_key and vt_api_key != "your-key-here":
        return await _virustotal_scan(urls[0], vt_api_key)
    else:
        logger.warning("VirusTotal API key not configured, using mock analysis for URL: %s", urls[0])
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
                logger.warning("VirusTotal URL scan submit returned HTTP %s for %s", resp.status_code, url)
                return await _mock_url_analysis(url)

            scan_data = resp.json()
            analysis_id = scan_data.get("data", {}).get("id", "")

            if not analysis_id:
                logger.warning("VirusTotal URL scan response missing analysis_id for %s", url)
                return await _mock_url_analysis(url)

            # 获取分析结果
            await asyncio.sleep(2)
            result_resp = await client.get(
                f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                headers=headers,
            )
            if result_resp.status_code != 200:
                logger.warning("VirusTotal URL scan result returned HTTP %s for analysis_id=%s", result_resp.status_code, analysis_id)
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
        logger.warning("VirusTotal URL scan degraded: %s", e)
        return await _mock_url_analysis(url)


async def _mock_url_analysis(url: str) -> dict:
    """基于 URL 特征的模拟威胁分析"""
    await asyncio.sleep(0.3)

    url_lower = url.lower()

    # 基于 URL 特征判断风险
    high_risk_keywords = ["phishing", "malware", "hack", "steal", "fake", "scam"]
    medium_risk_keywords = ["free", "click", "win", "prize", "urgent", "verify"]

    h = int(hashlib.sha256(url.encode("utf-8")).hexdigest()[:8], 16) % 100

    has_high_risk = any(kw in url_lower for kw in high_risk_keywords)
    has_medium_risk = any(kw in url_lower for kw in medium_risk_keywords)

    # 仅保留基于 URL 字符串真实关键词匹配的指标，删除虚构外部情报
    indicators = []
    if has_high_risk:
        indicators.append("URL 字符串包含高风险关键词")
    if has_medium_risk:
        indicators.append("URL 字符串包含中等风险关键词")
    if not indicators:
        indicators = ["未发现明显本地威胁特征"]

    if has_high_risk:
        threat_score = 0.3
    elif has_medium_risk:
        threat_score = 0.15
    else:
        threat_score = 0.0

    # mock:// 协议直接返回低威胁
    if url.startswith("mock://"):
        threat_score = 0.05
        indicators = ["模拟数据，无实际威胁"]

    # 保留本地启发式分析结果，但明确区分 VT 数据不可用
    indicators_with_note = indicators + ["VirusTotal 未实际调用 — 结果不可用"]

    return {
        "threat_score": min(1.0, threat_score),
        "indicators": indicators_with_note,
        "domain_info": {
            "url": url,
            "analysis_method": "mock_heuristic",
        },
        "virustotal": {
            "malicious": 0,
            "suspicious": 0,
            "total_engines": 0,
            "note": "模拟数据（未配置 VirusTotal API Key）",
            "scan_available": False,
        },
        "degraded": True,
    }


async def check_domain_reputation(domain: str) -> dict:
    """查询域名信誉（VirusTotal API）"""
    vt_key = settings.VIRUSTOTAL_API_KEY
    if not vt_key:
        logger.warning("VirusTotal API key not configured, using mock analysis for domain: %s", domain)
        result = await _mock_url_analysis(f"https://{domain}")
        return {
            "domain": domain,
            "reputation": int((1.0 - result["threat_score"]) * 100),
            "threat_score": result["threat_score"],
            "categories": [],
            "last_seen": "",
            "is_suspicious": result["threat_score"] > 0.5,
        }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://www.virustotal.com/api/v3/domains/{domain}",
                headers={"x-apikey": vt_key},
            )
            if resp.status_code != 200:
                logger.warning("VirusTotal domain reputation returned HTTP %s for %s", resp.status_code, domain)
                result = await _mock_url_analysis(f"https://{domain}")
                return {
                    "domain": domain,
                    "reputation": int((1.0 - result["threat_score"]) * 100),
                    "threat_score": result["threat_score"],
                    "categories": [],
                    "last_seen": "",
                    "is_suspicious": result["threat_score"] > 0.5,
                }

            data = resp.json().get("data", {}).get("attributes", {})
            reputation = data.get("reputation", 0)
            categories = data.get("categories", [])
            last_analysis = data.get("last_analysis_stats", {})
            total = sum(last_analysis.values()) or 1
            malicious = last_analysis.get("malicious", 0)
            suspicious = last_analysis.get("suspicious", 0)

            threat_score = min(1.0, (malicious + suspicious * 0.5) / total)
            is_suspicious = reputation < 0 or threat_score > 0.1

            # Flatten categories if they are dict values
            if isinstance(categories, dict):
                categories = list(set(categories.values()))
            elif isinstance(categories, list):
                categories = list(set(categories))

            return {
                "domain": domain,
                "reputation": reputation,
                "threat_score": threat_score,
                "categories": categories,
                "last_seen": str(data.get("last_modification_date", "")),
                "is_suspicious": is_suspicious,
            }
    except Exception as e:
        logger.warning("VirusTotal domain reputation degraded for %s: %s", domain, e)
        result = await _mock_url_analysis(f"https://{domain}")
        return {
            "domain": domain,
            "reputation": int((1.0 - result["threat_score"]) * 100),
            "threat_score": result["threat_score"],
            "categories": [],
            "last_seen": "",
            "is_suspicious": result["threat_score"] > 0.5,
        }


async def scan_file_hash(file_url: str) -> dict:
    """下载文件并查询 VirusTotal 文件哈希扫描结果"""
    import httpx

    vt_key = settings.VIRUSTOTAL_API_KEY
    default_result = {
        "malicious": 0,
        "suspicious": 0,
        "total_scans": 0,
        "threat_score": 0.0,
        "hash": "",
        "scan_available": False,
    }

    # 下载文件计算 SHA-256（最多 32MB）
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                file_url,
                headers={"Range": "bytes=0-33554431"},  # 前 32MB
                follow_redirects=True,
            )
            if resp.status_code not in (200, 206):
                return default_result

            file_bytes = resp.content
            hash_str = hashlib.sha256(file_bytes).hexdigest()
    except Exception as exc:
        logger.warning("VirusTotal file hash download failed for %s: %s", file_url, exc)
        return default_result

    result = {**default_result, "hash": hash_str}

    # 查询 VirusTotal
    if not vt_key:
        return {**result, "status": "no_key"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://www.virustotal.com/api/v3/files/{hash_str}",
                headers={"x-apikey": vt_key},
            )
            if resp.status_code == 404:
                # 哈希未在 VT 中找到 — 这是正常结果，不是降级
                return {**result, "status": "not_found"}

            if resp.status_code != 200:
                logger.warning("VirusTotal file hash query returned HTTP %s for hash=%s", resp.status_code, result.get("hash", ""))
                return {**result, "status": "error"}

            data = resp.json().get("data", {}).get("attributes", {})
            last_analysis = data.get("last_analysis_stats", {})
            malicious = last_analysis.get("malicious", 0)
            suspicious = last_analysis.get("suspicious", 0)
            total = sum(last_analysis.values()) or 1

            return {
                "malicious": malicious,
                "suspicious": suspicious,
                "total_scans": total,
                "threat_score": min(1.0, (malicious + suspicious * 0.5) / total),
                "hash": hash_str,
                "scan_available": True,
                "status": "ok",
            }
    except Exception as exc:
        logger.warning("VirusTotal file hash query failed for hash=%s: %s", result.get("hash", ""), exc)
        return {**result, "status": "error"}


async def extract_media_metadata(file_url: str, file_type: str) -> dict:
    """从媒体文件 URL 提取元数据特征（本地字节分析）"""
    import httpx
    import struct

    # 下载前 1MB 字节
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                file_url,
                headers={"Range": "bytes=0-1048575"},
                follow_redirects=True,
            )
            if resp.status_code not in (200, 206):
                logger.warning("Media metadata download returned HTTP %s for %s", resp.status_code, file_url)
                return _default_metadata_result()
            raw = resp.content
    except Exception as exc:
        logger.warning("Media metadata download failed for %s: %s", file_url, exc)
        return _default_metadata_result()

    file_size_approx = len(raw)
    exif_anomalies: list[str] = []
    manipulation_indicators: list[str] = []
    fmt = "unknown"
    dimensions = None
    has_exif = False
    compression_artifacts = False

    # --- JPEG ---
    if raw[:2] == b"\xff\xd8":
        fmt = "jpeg"
        offset = 2
        while offset < len(raw) - 4:
            if raw[offset] != 0xFF:
                break
            marker = raw[offset + 1]
            if marker == 0xD9:  # EOI
                break
            if marker == 0xE1:  # APP1 (EXIF)
                has_exif = True
                length = struct.unpack(">H", raw[offset + 2 : offset + 4])[0]
                exif_chunk = raw[offset + 4 : offset + 2 + length]
                # Check for manipulation tool signatures in EXIF
                exif_text = exif_chunk.decode("ascii", errors="ignore").lower()
                manipulation_tools = [
                    "photoshop", "gimp", "paint.net", "affinity",
                    "lightroom", "picasa", "snapseed", "faceapp",
                    "deepfake", "faceswap", "gan",
                ]
                for tool in manipulation_tools:
                    if tool in exif_text:
                        exif_anomalies.append(f"EXIF 软件字段包含编辑工具: {tool}")
                        manipulation_indicators.append(f"元数据检出编辑软件指纹: {tool}")
                # Check for missing/inconsistent dates
                if "datetime" not in exif_text and "date" not in exif_text:
                    exif_anomalies.append("EXIF 缺少创建时间戳")
            elif marker == 0xE0:  # APP0 (JFIF)
                pass
            if marker in (0xDA,):  # SOS - start of scan
                break
            if 0xD0 <= marker <= 0xD7:  # RST markers
                offset += 2
                continue
            if offset + 4 > len(raw):
                break
            seg_len = struct.unpack(">H", raw[offset + 2 : offset + 4])[0]
            offset += 2 + seg_len

        # Parse SOF for dimensions
        sof_pos = raw.find(b"\xff\xc0")
        if sof_pos == -1:
            sof_pos = raw.find(b"\xff\xc2")
        if sof_pos != -1 and sof_pos + 9 <= len(raw):
            h = struct.unpack(">H", raw[sof_pos + 5 : sof_pos + 7])[0]
            w = struct.unpack(">H", raw[sof_pos + 7 : sof_pos + 9])[0]
            dimensions = f"{w}x{h}"

    # --- PNG ---
    elif raw[:8] == b"\x89PNG\r\n\x1a\n":
        fmt = "png"
        offset = 8
        while offset < len(raw) - 12:
            chunk_len = struct.unpack(">I", raw[offset : offset + 4])[0]
            chunk_type = raw[offset + 4 : offset + 8]
            if chunk_type == b"tEXt" or chunk_type == b"zTXt" or chunk_type == b"iTXt":
                has_exif = True
                chunk_data = raw[offset + 8 : offset + 8 + chunk_len]
                text = chunk_data.decode("ascii", errors="ignore").lower()
                manipulation_tools = [
                    "photoshop", "gimp", "paint.net", "affinity",
                    "lightroom", "snapseed", "faceapp", "deepfake",
                ]
                for tool in manipulation_tools:
                    if tool in text:
                        exif_anomalies.append(f"PNG 元数据包含编辑工具: {tool}")
                        manipulation_indicators.append(f"元数据检出编辑软件指纹: {tool}")
            if chunk_type == b"IHDR" and chunk_len >= 13 and offset + 24 <= len(raw):
                w = struct.unpack(">I", raw[offset + 8 : offset + 12])[0]
                h = struct.unpack(">I", raw[offset + 12 : offset + 16])[0]
                dimensions = f"{w}x{h}"
            if chunk_type == b"IEND":
                break
            offset += 12 + chunk_len

    # --- MP4 / Video ---
    elif len(raw) >= 12:
        # Check for ftyp atom (MP4/MOV)
        if raw[4:8] == b"ftyp":
            fmt = "mp4"
            # Parse atom structure for moov
            offset = 0
            found_moov = False
            while offset < len(raw) - 8:
                atom_size = struct.unpack(">I", raw[offset : offset + 4])[0]
                atom_type = raw[offset + 4 : offset + 8]
                if atom_type == b"moov":
                    found_moov = True
                if atom_type == b"mdat" and not found_moov:
                    manipulation_indicators.append(
                        "视频文件结构异常: mdat 在 moov 之前（可能经过二次封装）"
                    )
                if atom_size == 0 or atom_size > len(raw):
                    break
                offset += atom_size
            if not has_exif:
                # Check for metadata in moov/udta
                if b"udta" in raw[:min(len(raw), 65536)]:
                    has_exif = True

    # --- MP3 (ID3) ---
    elif raw[:3] == b"ID3":
        fmt = "mp3"
        has_exif = True
        # Parse ID3v2 header
        id3_text = raw[:min(len(raw), 4096)].decode("ascii", errors="ignore").lower()
        manipulation_tools = ["audacity", "adobe", "goldwave", "wavepad"]
        for tool in manipulation_tools:
            if tool in id3_text:
                exif_anomalies.append(f"ID3 标签包含编辑工具: {tool}")
                manipulation_indicators.append(f"音频元数据检出编辑软件指纹: {tool}")

    # --- WAV (RIFF) ---
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        fmt = "wav"
        # Check for LIST/INFO chunk
        if b"LIST" in raw[:min(len(raw), 4096)]:
            has_exif = True

    # Generic checks
    if fmt == "unknown":
        # Try to detect format from extension hints in URL
        url_lower = file_url.lower()
        if url_lower.endswith((".jpg", ".jpeg")):
            fmt = "jpeg"
        elif url_lower.endswith(".png"):
            fmt = "png"
        elif url_lower.endswith((".mp4", ".mov", ".avi")):
            fmt = "mp4"
        elif url_lower.endswith((".mp3", ".wav")):
            fmt = "audio"
        else:
            fmt = file_type or "unknown"

    # Additional anomaly checks
    if has_exif and not exif_anomalies:
        # EXIF present but no anomalies found - this is normal
        pass
    elif not has_exif and fmt in ("jpeg", "png"):
        exif_anomalies.append("媒体文件缺少 EXIF 元数据，可能经过清洗处理")
        manipulation_indicators.append("元数据缺失：可能被故意擦除")

    # Detect potential double-compression for JPEG
    if fmt == "jpeg" and file_size_approx < 50000 and dimensions:
        try:
            w_h = dimensions.split("x")
            pixel_count = int(w_h[0]) * int(w_h[1])
            bytes_per_pixel = file_size_approx / pixel_count if pixel_count > 0 else 0
            if bytes_per_pixel < 0.5:
                compression_artifacts = True
                manipulation_indicators.append(
                    "压缩率异常高，可能经历多次编码/压缩"
                )
        except (ValueError, IndexError, ZeroDivisionError):
            pass

    return {
        "format": fmt,
        "dimensions": dimensions,
        "duration_seconds": None,
        "has_exif": has_exif,
        "exif_anomalies": exif_anomalies,
        "file_size_approx": file_size_approx,
        "compression_artifacts": compression_artifacts,
        "manipulation_indicators": manipulation_indicators,
    }


def _default_metadata_result() -> dict:
    """返回默认的元数据结果（下载失败时）"""
    return {
        "format": "unknown",
        "dimensions": None,
        "duration_seconds": None,
        "has_exif": False,
        "exif_anomalies": [],
        "file_size_approx": 0,
        "compression_artifacts": False,
        "manipulation_indicators": ["无法获取媒体元数据"],
    }
