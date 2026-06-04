"""Evidence file byte access helpers."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.utils.supabase_client import supabase


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
    """Download evidence bytes from an HTTP URL or Supabase storage path."""
    if not reference:
        raise ValueError("empty evidence reference")
    if reference.startswith("mock://"):
        return b"", _filename_from_reference(reference)
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
