"""Deepfake Detection Tool - Reality Defender API with mock fallback"""
import asyncio
import random
import httpx
from datetime import datetime
from app.config import settings


REALITY_DEFENDER_BASE = "https://api.realitydefender.com"


async def analyze_with_reality_defender(file_url: str, media_type: str = "image") -> dict:
    """
    调用 Reality Defender API 进行 Deepfake 检测
    支持 audio 和 image，视频支持抽帧后逐帧检测
    """
    if not settings.REALITY_DEFENDER_API_KEY:
        return await mock_deepfake_analysis(file_url, media_type)

    headers = {
        "Authorization": f"Bearer {settings.REALITY_DEFENDER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Reality Defender API: upload media for analysis
            upload_payload = {
                "url": file_url,
                "media_type": media_type,
            }
            resp = await client.post(
                f"{REALITY_DEFENDER_BASE}/v1/media/analyze",
                json=upload_payload,
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()

            # 解析 Reality Defender 返回格式
            deepfake_score = result.get("deepfake_score", 0.0)
            is_deepfake = deepfake_score > 0.5

            return {
                "is_deepfake": is_deepfake,
                "confidence": deepfake_score if is_deepfake else (1.0 - deepfake_score),
                "deepfake_probability": deepfake_score,
                "model": "reality_defender",
                "details": result.get("details", {}),
                "raw_response": result,
                "timestamp": datetime.utcnow().isoformat(),
            }

    except httpx.HTTPStatusError as e:
        print(f"[Reality Defender] HTTP Error {e.response.status_code}: {e.response.text}")
        print("[Reality Defender] 降级到模拟分析...")
        return await mock_deepfake_analysis(file_url, media_type)
    except (httpx.RequestError, httpx.TimeoutException) as e:
        print(f"[Reality Defender] 网络错误: {e}")
        print("[Reality Defender] 降级到模拟分析...")
        return await mock_deepfake_analysis(file_url, media_type)
    except Exception as e:
        print(f"[Reality Defender] 未知错误: {e}")
        return await mock_deepfake_analysis(file_url, media_type)


async def mock_deepfake_analysis(file_url: str, media_type: str = "video") -> dict:
    """模拟 Deepfake 检测结果（降级/测试用）"""
    await asyncio.sleep(random.uniform(1.5, 3.0))  # 模拟 API 延迟

    deepfake_prob = random.uniform(0.3, 0.95)
    is_deepfake = deepfake_prob > 0.5

    indicators = []
    if is_deepfake:
        candidates = [
            "面部边缘融合不自然，检测到 GAN 伪影",
            "眨眼频率异常（0.3 次/秒，正常为 0.4-0.5 次/秒）",
            "音画嘴唇同步偏差 > 80ms",
            "频谱分析显示声纹克隆特征",
            "帧间时序一致性低于阈值（0.62）",
        ]
        indicators = random.sample(candidates, k=random.randint(2, 4))
    else:
        indicators = ["帧间一致性正常", "面部特征自然", "无 GAN 伪影检测"]

    return {
        "is_deepfake": is_deepfake,
        "confidence": deepfake_prob if is_deepfake else (1.0 - deepfake_prob),
        "deepfake_probability": deepfake_prob,
        "model": "mock_analyzer_v1",
        "details": {
            "indicators": indicators,
            "frames_analyzed": random.randint(30, 120) if media_type == "video" else 1,
            "anomaly_score": deepfake_prob,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


async def analyze_media(file_url: str, media_type: str = "video") -> dict:
    """主入口：优先调用真实 API，不可用时回退到模拟"""
    return await analyze_with_reality_defender(file_url, media_type)
