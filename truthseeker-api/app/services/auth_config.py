"""Authentication configuration guards."""
from __future__ import annotations


LOCAL_ENVIRONMENTS = {"", "dev", "development", "local", "test", "testing"}
PRODUCTION_ENVIRONMENTS = {"prod", "production"}
UNSET_JWT_VALUES = {"", "NOT_SET", "not_set", "your-jwt-secret"}


def validate_auth_configuration(*, environment: str, jwt_secret: str | None) -> bool:
    """Return whether JWT auth should be enabled, and fail fast in production."""
    normalized_env = (environment or "development").strip().lower()
    normalized_secret = (jwt_secret or "").strip()

    if normalized_env in PRODUCTION_ENVIRONMENTS and normalized_secret in UNSET_JWT_VALUES:
        raise RuntimeError("生产环境必须配置真实 SUPABASE_JWT_SECRET，不能使用 NOT_SET")

    if normalized_secret in UNSET_JWT_VALUES:
        return False

    return True
