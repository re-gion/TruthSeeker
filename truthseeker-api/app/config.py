"""Application configuration using pydantic-settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = "NOT_SET"

    # AI APIs
    OPENAI_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    REALITY_DEFENDER_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""

    # App
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_ROUNDS: int = 5
    CONVERGENCE_THRESHOLD: float = 0.05


settings = Settings()
