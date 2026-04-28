"""Supabase Storage and DB Client for FastAPI"""
from typing import Any

from app.config import settings

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - depends on local environment
    Client = Any  # type: ignore[assignment]
    create_client = None


class _MissingSupabaseClient:
    def __getattr__(self, name: str) -> Any:
        raise RuntimeError("Supabase client is unavailable. Install the 'supabase' package and configure env vars.")


def get_supabase() -> Client | _MissingSupabaseClient:
    """Initialize and return a Supabase client with connection pooling."""
    if create_client is None:
        return _MissingSupabaseClient()
    if not settings.SUPABASE_URL or not (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY):
        return _MissingSupabaseClient()
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY,
    )

# Singleton instance
supabase = get_supabase()
