"""Reality Defender HTTP 错误降级原因回归。

背景：免费套餐上传视频会被 RD 以 403 free-tier-restriction 拒绝，
此前降级原因只记 http_403，报告与质询无法自解释根因。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.tools import deepfake_api


@pytest.mark.asyncio
async def test_rd_403_includes_structured_reason(monkeypatch):
    async def fake_download(url):
        return b"video-bytes", "case.mp4"

    monkeypatch.setattr(deepfake_api, "_download_file", fake_download)
    monkeypatch.setattr(deepfake_api, "_get_api_key", lambda: "rd_test_key")

    request = deepfake_api.httpx.Request(
        "POST", f"{deepfake_api.RD_BASE}/api/files/aws-presigned"
    )
    response = deepfake_api.httpx.Response(
        403,
        request=request,
        json={
            "statusCode": 403,
            "path": "/api/files/aws-presigned",
            "message": "Forbidden: Video and text uploads require a paid plan",
            "code": "free-tier-restriction",
        },
    )

    async def fake_presigned(client, api_key, filename):
        raise deepfake_api.httpx.HTTPStatusError(
            "Client error '403 Forbidden'", request=request, response=response
        )

    monkeypatch.setattr(deepfake_api, "_request_presigned_url", fake_presigned)

    result = await deepfake_api.analyze_with_reality_defender("mock://video", "video")

    assert result["degraded"] is True
    assert result["analysis_available"] is False
    reason = result["details"]["fallback_reason"]
    assert reason.startswith("http_403")
    assert "free-tier-restriction" in reason
    assert "paid plan" in reason
