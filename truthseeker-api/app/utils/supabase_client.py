"""Supabase Storage and DB Client for FastAPI"""
from typing import Any

import httpx

from app.config import settings

try:
    from supabase import Client, create_client
    from supabase.lib.client_options import SyncClientOptions
except ImportError:  # pragma: no cover - depends on local environment
    Client = Any  # type: ignore[assignment]
    create_client = None
    SyncClientOptions = None  # type: ignore[assignment,misc]


def _build_http_client() -> httpx.Client:
    """supabase 各子客户端共享的 HTTP/1.1 客户端。

    supabase-py 对 storage/postgrest 等子客户端默认 http2=True；大文件上传走 HTTP/2 时
    容易被网关远程重置流（StreamReset PROTOCOL_ERROR），且传输层会吞掉服务端真实状态码。
    统一改用 HTTP/1.1 消除此类错误，并让 413 等拒绝以真实状态码返回；write 超时放宽
    以容纳大文件上传。
    """
    return httpx.Client(
        http2=False,
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, read=120.0, write=600.0),
    )


class _MissingSupabaseClient:
    def __getattr__(self, name: str) -> Any:
        raise RuntimeError("Supabase client is unavailable. Install the 'supabase' package and configure env vars.")


def get_supabase() -> Client | _MissingSupabaseClient:
    """Initialize and return a Supabase client with connection pooling."""
    if create_client is None:
        return _MissingSupabaseClient()
    if not settings.SUPABASE_URL or not (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY):
        return _MissingSupabaseClient()
    options = None
    if SyncClientOptions is not None:
        options = SyncClientOptions(httpx_client=_build_http_client())
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY,
        options=options,
    )

# Singleton instance
supabase = get_supabase()
