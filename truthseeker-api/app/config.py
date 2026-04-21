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
    REALITY_DEFENDER_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("REALITY_DEFENDER_API_KEY", "Reality_Defender"),
    )
    VIRUSTOTAL_API_KEY: str = Field(default="", validation_alias=AliasChoices("VIRUSTOTAL_API_KEY", "Virus_Total"))
    KIMI_API_KEY: str = Field(default="", validation_alias=AliasChoices("KIMI_API_KEY", "Kimi_API_KEY"))
    KIMI_BASE_URL: str = Field(
        default="https://api.moonshot.cn/v1",
        validation_alias=AliasChoices("KIMI_BASE_URL", "Kimi_Base_URL"),
    )
    OPENAI_API_KEY: str = ""
    QWEN_API_KEY: str = ""

    # App
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_ROUNDS: int = 5
    CONVERGENCE_THRESHOLD: float = 0.05


settings = Settings()
