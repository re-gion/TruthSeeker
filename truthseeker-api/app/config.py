"""Application configuration using pydantic-settings"""
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = "NOT_SET"

    # AI APIs — 使用 Field 映射 .env 中的实际变量名
    REALITY_DEFENDER_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    KIMI_API_KEY: str = Field(default="", validation_alias=AliasChoices("KIMI_API_KEY", "Kimi_API_KEY"))
    KIMI_BASE_URL: str = Field(
        default="https://api.moonshot.cn/v1",
        validation_alias=AliasChoices("KIMI_BASE_URL", "Kimi_Base_URL"),
    )
    KIMI_MODEL: str = Field(
        default="kimi-k2.5",
        validation_alias=AliasChoices("KIMI_MODEL", "Kimi_Model"),
    )
    KIMI_FALLBACK_MODEL: str = Field(
        default="moonshot-v1-128k",
        validation_alias=AliasChoices("KIMI_FALLBACK_MODEL", "Kimi_Fallback_Model"),
    )
    # NOTE: 以下 API key 当前未被代码直接使用，保留用于未来 LLM 提供商切换或兼容
    OPENAI_API_KEY: str = ""
    QWEN_API_KEY: str = ""

    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_ROUNDS: int = 5
    CONVERGENCE_THRESHOLD: float = 0.05


settings = Settings()
