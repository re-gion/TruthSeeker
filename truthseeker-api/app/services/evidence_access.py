"""Evidence file byte access helpers."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

# 检材下载的传输层重试，与上传端 (app/api/v1/upload.py) 的韧性策略对称：
# 代理/网络抖动会造成间歇性 TLS 中断（如 httpx.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING]），
# 有限重试可显著降低检材读取失败率，避免文本/媒体内容读不到而被降级。
DOWNLOAD_MAX_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY_SECONDS = 1.5


def is_http_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"}


def _filename_from_reference(reference: str, fallback: str = "upload.bin") -> str:
    parsed = urlparse(reference or "")
    path = parsed.path if parsed.scheme else reference
    filename = path.rstrip("/").split("/")[-1]
    return filename or fallback


def _coerce_storage_bytes(raw: object) -> bytes:
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if hasattr(raw, "read"):
        data = raw.read()
        return data if isinstance(data, bytes) else bytes(data)
    return bytes(raw)  # type: ignore[arg-type]


async def download_evidence_bytes(reference: str, *, timeout: float = 30.0, range_header: str | None = None) -> tuple[bytes, str]:
    """Download evidence bytes from an HTTP URL or Supabase storage path.

    传输层瞬时错误（连接中断/超时等 httpx.TransportError）会有限重试，
    服务端明确拒绝（4xx/5xx、bucket 不存在等）不重试，直接抛出。
    """
    if not reference:
        raise ValueError("empty evidence reference")
    if reference.startswith("mock://"):
        return b"", _filename_from_reference(reference)

    last_error: httpx.TransportError | None = None
    for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
        try:
            return await _download_once(reference, timeout=timeout, range_header=range_header)
        except httpx.TransportError as exc:
            last_error = exc
            logger.warning(
                "Evidence download transport error (attempt %d/%d) reference=%s: %s",
                attempt, DOWNLOAD_MAX_ATTEMPTS, reference, exc,
            )
            if attempt < DOWNLOAD_MAX_ATTEMPTS:
                await asyncio.sleep(DOWNLOAD_RETRY_DELAY_SECONDS * attempt)
    assert last_error is not None
    raise last_error


async def _download_once(reference: str, *, timeout: float, range_header: str | None) -> tuple[bytes, str]:
    if is_http_url(reference):
        headers = {"Range": range_header} if range_header else None
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(reference, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            filename = _filename_from_reference(reference)
            cd = resp.headers.get("content-disposition", "")
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"\'') or filename
            return resp.content, filename

    raw = await _download_storage_path(reference)
    return _coerce_storage_bytes(raw), _filename_from_reference(reference)


async def _download_storage_path(path: str) -> object:
    return supabase.storage.from_("media").download(path)
