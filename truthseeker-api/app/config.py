"""Application configuration using pydantic-settings"""
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 确保无论从哪个工作目录启动，都能加载到 truthseeker-api/.env
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
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
    KIMI_API_KEY: str = Field(default="", validation_alias=AliasChoices("KIMI_API_KEY", "Kimi_API_KEY"))
    KIMI_BASE_URL: str = Field(
        default="https://api.moonshot.cn/v1",
        validation_alias=AliasChoices("KIMI_BASE_URL", "Kimi_Base_URL"),
    )
    KIMI_MODEL: str = Field(
        default="kimi-k2.6",
        validation_alias=AliasChoices("KIMI_MODEL", "Kimi_Model"),
    )
    KIMI_FALLBACK_MODEL: str = Field(
        default="moonshot-v1-128k",
        validation_alias=AliasChoices("KIMI_FALLBACK_MODEL", "Kimi_Fallback_Model"),
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
    REALITY_DEFENDER_DOWNLOAD_TIMEOUT_SECONDS: float = 120.0
    REALITY_DEFENDER_UPLOAD_TIMEOUT_SECONDS: float = 60.0
    REALITY_DEFENDER_CLIENT_TIMEOUT_SECONDS: float = 240.0
    REALITY_DEFENDER_POLL_MAX_ATTEMPTS: int = 8
    REALITY_DEFENDER_POLL_DELAY_SECONDS: float = 15.0
    FORENSICS_TOOL_TIMEOUT_SECONDS: float = 210.0


settings = Settings()


# Production safety check: refuse to run with placeholder JWT secret
if settings.APP_ENV == "production" and settings.SUPABASE_JWT_SECRET in ("NOT_SET", "", "your-jwt-secret"):
    raise RuntimeError(
        "SUPABASE_JWT_SECRET is not configured for production. "
        "Set a real JWT secret in the environment before starting the server."
    )
