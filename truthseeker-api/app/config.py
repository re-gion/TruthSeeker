"""Application configuration using pydantic-settings"""
from pathlib import Path

from dotenv import dotenv_values
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 确保无论从哪个工作目录启动，都能加载到 truthseeker-api/.env
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _read_kimi_env() -> dict[str, str]:
    """每次调用时重新读取 .env 中的 Kimi 相关配置，实现热加载。"""
    raw = dotenv_values(str(_ENV_PATH))
    result: dict[str, str] = {}
    for key in (
        "KIMI_PROVIDER", "KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL",
        "KIMI_CODING_API_KEY", "KIMI_CODING_BASE_URL", "KIMI_CODING_MODEL",
    ):
        value = raw.get(key)
        if value is not None:
            result[key] = value
    return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = "NOT_SET"

    # AI APIs — 使用 Field 映射 .env 中的实际变量名
    REALITY_DEFENDER_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "REALITY_DEFENDER_API_KEY",
            "Reality_Defender",
            "REALITY_DEFENDER",
        ),
    )
    VIRUSTOTAL_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "VIRUSTOTAL_API_KEY",
            "Virus_Total",
            "VirusTotal_API_KEY",
        ),
    )
    KIMI_PROVIDER: str = Field(default="official", validation_alias=AliasChoices("KIMI_PROVIDER", "Kimi_Provider"))
    KIMI_API_KEY: str = Field(default="", validation_alias=AliasChoices("KIMI_API_KEY", "Kimi_API_KEY"))
    KIMI_BASE_URL: str = Field(
        default="https://api.moonshot.cn/v1",
        validation_alias=AliasChoices("KIMI_BASE_URL", "Kimi_Base_URL"),
    )
    KIMI_MODEL: str = Field(
        default="kimi-k2.5",
        validation_alias=AliasChoices("KIMI_MODEL", "Kimi_Model"),
    )
    KIMI_CODING_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("KIMI_CODING_API_KEY", "Kimi_Coding_API_KEY"),
    )
    KIMI_CODING_BASE_URL: str = Field(
        default="https://api.kimi.com/coding/v1",
        validation_alias=AliasChoices("KIMI_CODING_BASE_URL", "Kimi_Coding_Base_URL"),
    )
    KIMI_CODING_MODEL: str = Field(
        default="kimi-k2.5",
        validation_alias=AliasChoices("KIMI_CODING_MODEL", "Kimi_Coding_Model"),
    )
    # NOTE: 以下 API key 当前未被代码直接使用，保留用于未来 LLM 提供商切换或兼容
    OPENAI_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    EXA_API_KEY: str = Field(default="", validation_alias=AliasChoices("EXA_API_KEY", "Exa_API_KEY"))
    EXA_BASE_URL: str = Field(
        default="https://api.exa.ai",
        validation_alias=AliasChoices("EXA_BASE_URL", "Exa_Base_URL"),
    )

    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_ROUNDS: int = 5
    CONVERGENCE_THRESHOLD: float = 0.08
    CHALLENGER_SATISFACTION_THRESHOLD: float = 0.8
    CONSULTATION_STUCK_ROUNDS: int = 3
    CONSULTATION_CONFIDENCE_THRESHOLD: float = 0.8
    CONSULTATION_DELTA_THRESHOLD: float = 0.08
    REALITY_DEFENDER_DOWNLOAD_TIMEOUT_SECONDS: float = 120.0
    REALITY_DEFENDER_UPLOAD_TIMEOUT_SECONDS: float = 60.0
    REALITY_DEFENDER_CLIENT_TIMEOUT_SECONDS: float = 240.0
    REALITY_DEFENDER_POLL_MAX_ATTEMPTS: int = 8
    REALITY_DEFENDER_POLL_DELAY_SECONDS: float = 15.0
    FORENSICS_TOOL_TIMEOUT_SECONDS: float = 210.0


settings = Settings()


def _normalize_kimi_provider(provider: str) -> str:
    value = (provider or "official").strip().lower().replace("-", "_")
    if value in {"coding", "coding_plan", "kimi_coding", "kimi_coding_plan"}:
        return "coding"
    return "official"


def _normalize_kimi_base_url(base_url: str, provider: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        normalized = "https://api.kimi.com/coding/v1" if provider == "coding" else "https://api.moonshot.cn/v1"
    if provider == "coding" and normalized.endswith("/coding"):
        normalized = f"{normalized}/v1"
    return normalized


def resolve_kimi_runtime(config: Settings | None = None) -> dict[str, str]:
    """Resolve the active Kimi endpoint, hot-reloading from .env on every call."""
    cfg = config or settings
    env = _read_kimi_env()  # 每次都从 .env 文件重新读取，实现 Key 热切换

    provider_raw = env.get("KIMI_PROVIDER") or cfg.KIMI_PROVIDER
    provider = _normalize_kimi_provider(provider_raw)

    official_key = env.get("KIMI_API_KEY") or cfg.KIMI_API_KEY
    official_model = (env.get("KIMI_MODEL") or cfg.KIMI_MODEL or "kimi-k2.5").strip() or "kimi-k2.5"
    official_base = _normalize_kimi_base_url(env.get("KIMI_BASE_URL") or cfg.KIMI_BASE_URL, "official")

    if provider == "coding":
        coding_key = env.get("KIMI_CODING_API_KEY") or cfg.KIMI_CODING_API_KEY or official_key
        coding_model = (env.get("KIMI_CODING_MODEL") or cfg.KIMI_CODING_MODEL or "kimi-k2.5").strip() or "kimi-k2.5"
        coding_base = _normalize_kimi_base_url(env.get("KIMI_CODING_BASE_URL") or cfg.KIMI_CODING_BASE_URL, "coding")
        return {
            "provider": "coding",
            "model": coding_model,
            "base_url": coding_base,
            "api_key": coding_key,
        }
    return {
        "provider": "official",
        "model": official_model,
        "base_url": official_base,
        "api_key": official_key,
    }


# Production safety check: refuse to run with placeholder JWT secret
if settings.APP_ENV == "production" and settings.SUPABASE_JWT_SECRET in ("NOT_SET", "", "your-jwt-secret"):
    raise RuntimeError(
        "SUPABASE_JWT_SECRET is not configured for production. "
        "Set a real JWT secret in the environment before starting the server."
    )
