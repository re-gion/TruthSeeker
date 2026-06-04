"""Application configuration using pydantic-settings"""
from pathlib import Path

from dotenv import dotenv_values
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 确保无论从哪个工作目录启动，都能加载到 truthseeker-api/.env
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _read_kimi_env() -> dict[str, str]:
    """每次调用时重新读取 .env 中的 Agent LLM 相关配置，实现热加载。"""
    raw = dotenv_values(str(_ENV_PATH))
    result: dict[str, str] = {}
    for key in (
        "AGENT_LLM_PROVIDER", "AGENT_LLM_MAX_OUTPUT_TOKENS",
        "KIMI_PROVIDER", "KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL",
        "KIMI_CODING_API_KEY", "KIMI_CODING_BASE_URL", "KIMI_CODING_MODEL",
        "KIMI_SILICONFLOW_API_KEY", "KIMI_SILICONFLOW_BASE_URL", "KIMI_SILICONFLOW_MODEL",
        "MIMO_API_KEY", "MIMO_BASE_URL", "MIMO_MODEL", "MIMO_THINKING",
        "EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL",
        "EMBEDDING_DIMENSIONS", "CASE_RAG_ENABLED", "CASE_RAG_TOP_K",
        "AIGC_IMAGE_PROVIDER", "AIGC_IMAGE_FALLBACK_PROVIDER",
        "SIGHTENGINE_API_USER", "SIGHTENGINE_API_SECRET",
        "WHOISXML_API_KEY", "DOMAIN_PROVENANCE_ENABLED", "WHOISXML_TIMEOUT_SECONDS",
        "TEXT_AIGC_DETECTOR_ENABLED",
        "TEXT_AIGC_AI_THRESHOLD",
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
    AGENT_LLM_PROVIDER: str = Field(
        default="kimi-k2.5",
        validation_alias=AliasChoices("AGENT_LLM_PROVIDER", "Agent_LLM_Provider"),
    )
    AGENT_LLM_MAX_OUTPUT_TOKENS: int = Field(
        default=4096,
        validation_alias=AliasChoices("AGENT_LLM_MAX_OUTPUT_TOKENS", "Agent_LLM_Max_Output_Tokens"),
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
    KIMI_SILICONFLOW_API_KEY: str = Field(default="", validation_alias=AliasChoices("KIMI_SILICONFLOW_API_KEY"))
    KIMI_SILICONFLOW_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        validation_alias=AliasChoices("KIMI_SILICONFLOW_BASE_URL"),
    )
    KIMI_SILICONFLOW_MODEL: str = Field(
        default="Pro/moonshotai/Kimi-K2.5",
        validation_alias=AliasChoices("KIMI_SILICONFLOW_MODEL"),
    )
    MIMO_API_KEY: str = Field(default="", validation_alias=AliasChoices("MIMO_API_KEY", "MiMo_API_KEY"))
    MIMO_BASE_URL: str = Field(
        default="https://token-plan-cn.xiaomimimo.com/v1",
        validation_alias=AliasChoices("MIMO_BASE_URL", "MiMo_Base_URL"),
    )
    MIMO_MODEL: str = Field(
        default="mimo-v2.5",
        validation_alias=AliasChoices("MIMO_MODEL", "MiMo_Model"),
    )
    MIMO_THINKING: str = Field(
        default="enabled",
        validation_alias=AliasChoices("MIMO_THINKING", "MiMo_Thinking"),
    )
    # NOTE: 以下 API key 当前未被代码直接使用，保留用于未来 LLM 提供商切换或兼容
    OPENAI_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    EXA_API_KEY: str = Field(default="", validation_alias=AliasChoices("EXA_API_KEY", "Exa_API_KEY"))
    EXA_BASE_URL: str = Field(
        default="https://api.exa.ai",
        validation_alias=AliasChoices("EXA_BASE_URL", "Exa_Base_URL"),
    )
    AIGC_IMAGE_PROVIDER: str = Field(default="sightengine", validation_alias=AliasChoices("AIGC_IMAGE_PROVIDER"))
    AIGC_IMAGE_FALLBACK_PROVIDER: str = Field(default="reality_defender", validation_alias=AliasChoices("AIGC_IMAGE_FALLBACK_PROVIDER"))
    SIGHTENGINE_API_USER: str = Field(default="", validation_alias=AliasChoices("SIGHTENGINE_API_USER", "Sightengine_API_User"))
    SIGHTENGINE_API_SECRET: str = Field(default="", validation_alias=AliasChoices("SIGHTENGINE_API_SECRET", "Sightengine_API_Secret"))
    WHOISXML_API_KEY: str = Field(default="", validation_alias=AliasChoices("WHOISXML_API_KEY", "WhoisXML_API_KEY"))
    DOMAIN_PROVENANCE_ENABLED: bool = Field(default=True, validation_alias=AliasChoices("DOMAIN_PROVENANCE_ENABLED"))
    WHOISXML_TIMEOUT_SECONDS: float = Field(default=20.0, validation_alias=AliasChoices("WHOISXML_TIMEOUT_SECONDS"))

    # Public case RAG embeddings. Defaults target SiliconFlow's OpenAI-compatible embeddings API.
    EMBEDDING_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "Embedding_Base_URL"),
    )
    EMBEDDING_API_KEY: str = Field(default="", validation_alias=AliasChoices("EMBEDDING_API_KEY", "Embedding_API_KEY"))
    EMBEDDING_MODEL: str = Field(
        default="Qwen/Qwen3-VL-Embedding-8B",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "Embedding_Model"),
    )
    EMBEDDING_DIMENSIONS: int = Field(default=1024, validation_alias=AliasChoices("EMBEDDING_DIMENSIONS", "Embedding_Dimensions"))
    CASE_RAG_ENABLED: bool = Field(default=True, validation_alias=AliasChoices("CASE_RAG_ENABLED", "Case_RAG_Enabled"))
    CASE_RAG_TOP_K: int = Field(default=5, validation_alias=AliasChoices("CASE_RAG_TOP_K", "Case_RAG_Top_K"))

    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_ROUNDS: int = 5
    CONVERGENCE_THRESHOLD: float = 0.08
    CHALLENGER_SATISFACTION_THRESHOLD: float = 0.8
    CONSULTATION_STUCK_ROUNDS: int = 3
    CONSULTATION_CONFIDENCE_THRESHOLD: float = 0.8
    CONSULTATION_DELTA_THRESHOLD: float = 0.08
    TEXT_AIGC_DETECTOR_ENABLED: bool = Field(default=True, validation_alias=AliasChoices("TEXT_AIGC_DETECTOR_ENABLED", "Text_AIGC_Detector_Enabled"))
    TEXT_AIGC_AI_THRESHOLD: float = Field(default=0.6, validation_alias=AliasChoices("TEXT_AIGC_AI_THRESHOLD", "Text_AIGC_AI_Threshold"))
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
    if value in {"siliconflow", "silicon_flow"}:
        return "siliconflow"
    if value in {"mimo", "xiaomi_mimo", "mimo_token_plan", "xiaomi_token_plan"}:
        return "mimo"
    return "official"


def _normalize_agent_llm_provider(provider: str) -> str:
    value = (provider or "kimi-k2.5").strip().lower().replace("-", "_")
    if value in {"mimo", "xiaomi_mimo", "mimo_v2.5", "mimo_v2_5", "mimo_token_plan", "xiaomi_token_plan"}:
        return "mimo"
    return "kimi"


def _normalize_thinking_mode(value: str) -> str:
    normalized = (value or "enabled").strip().lower()
    if normalized in {"disabled", "disable", "off", "false", "0", "no"}:
        return "disabled"
    return "enabled"


def _parse_positive_int(value: str | int | None, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return parsed if parsed > 0 else default


def _normalize_kimi_base_url(base_url: str, provider: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        normalized = "https://api.kimi.com/coding/v1" if provider == "coding" else "https://api.moonshot.cn/v1"
    if provider == "coding" and normalized.endswith("/coding"):
        normalized = f"{normalized}/v1"
    return normalized


def resolve_kimi_runtime(config: Settings | None = None) -> dict[str, str]:
    """Resolve the active Agent LLM endpoint, hot-reloading from .env on every call."""
    cfg = config or settings
    env = _read_kimi_env()  # 每次都从 .env 文件重新读取，实现 Key 热切换

    agent_provider_raw = env.get("AGENT_LLM_PROVIDER") or cfg.AGENT_LLM_PROVIDER
    agent_provider = _normalize_agent_llm_provider(agent_provider_raw)
    provider_raw = env.get("KIMI_PROVIDER") or cfg.KIMI_PROVIDER
    provider = _normalize_kimi_provider(provider_raw)
    if provider == "mimo":
        agent_provider = "mimo"

    official_key = env.get("KIMI_API_KEY") or cfg.KIMI_API_KEY
    official_model = (env.get("KIMI_MODEL") or cfg.KIMI_MODEL or "kimi-k2.5").strip() or "kimi-k2.5"
    official_base = _normalize_kimi_base_url(env.get("KIMI_BASE_URL") or cfg.KIMI_BASE_URL, "official")

    if agent_provider == "mimo":
        mimo_key = env.get("MIMO_API_KEY") or cfg.MIMO_API_KEY
        mimo_model = (env.get("MIMO_MODEL") or cfg.MIMO_MODEL or "mimo-v2.5").strip() or "mimo-v2.5"
        mimo_base = (
            env.get("MIMO_BASE_URL")
            or cfg.MIMO_BASE_URL
            or "https://token-plan-cn.xiaomimimo.com/v1"
        ).strip().rstrip("/")
        return {
            "provider": "mimo",
            "model": mimo_model,
            "base_url": mimo_base,
            "api_key": mimo_key,
            "thinking": _normalize_thinking_mode(env.get("MIMO_THINKING") or cfg.MIMO_THINKING),
            "max_output_tokens": str(_parse_positive_int(
                env.get("AGENT_LLM_MAX_OUTPUT_TOKENS") or cfg.AGENT_LLM_MAX_OUTPUT_TOKENS,
                4096,
            )),
        }
    if provider == "coding":
        coding_key = env.get("KIMI_CODING_API_KEY") or cfg.KIMI_CODING_API_KEY or official_key
        coding_model = (env.get("KIMI_CODING_MODEL") or cfg.KIMI_CODING_MODEL or "kimi-k2.5").strip() or "kimi-k2.5"
        coding_base = _normalize_kimi_base_url(env.get("KIMI_CODING_BASE_URL") or cfg.KIMI_CODING_BASE_URL, "coding")
        return {
            "provider": "coding",
            "model": coding_model,
            "base_url": coding_base,
            "api_key": coding_key,
            "thinking": "disabled",
            "max_output_tokens": str(_parse_positive_int(
                env.get("AGENT_LLM_MAX_OUTPUT_TOKENS") or cfg.AGENT_LLM_MAX_OUTPUT_TOKENS,
                4096,
            )),
        }
    if provider == "siliconflow":
        sf_key = env.get("KIMI_SILICONFLOW_API_KEY") or cfg.KIMI_SILICONFLOW_API_KEY or official_key
        sf_model = (env.get("KIMI_SILICONFLOW_MODEL") or cfg.KIMI_SILICONFLOW_MODEL or "Pro/moonshotai/Kimi-K2.5").strip()
        sf_base = (env.get("KIMI_SILICONFLOW_BASE_URL") or cfg.KIMI_SILICONFLOW_BASE_URL or "https://api.siliconflow.cn/v1").strip().rstrip("/")
        return {
            "provider": "siliconflow",
            "model": sf_model,
            "base_url": sf_base,
            "api_key": sf_key,
            "thinking": "disabled",
            "max_output_tokens": str(_parse_positive_int(
                env.get("AGENT_LLM_MAX_OUTPUT_TOKENS") or cfg.AGENT_LLM_MAX_OUTPUT_TOKENS,
                4096,
            )),
        }
    return {
        "provider": "official",
        "model": official_model,
        "base_url": official_base,
        "api_key": official_key,
        "thinking": "disabled",
        "max_output_tokens": str(_parse_positive_int(
            env.get("AGENT_LLM_MAX_OUTPUT_TOKENS") or cfg.AGENT_LLM_MAX_OUTPUT_TOKENS,
            4096,
        )),
    }


# Production safety check: refuse to run with placeholder JWT secret
if settings.APP_ENV == "production" and settings.SUPABASE_JWT_SECRET in ("NOT_SET", "", "your-jwt-secret"):
    raise RuntimeError(
        "SUPABASE_JWT_SECRET is not configured for production. "
        "Set a real JWT secret in the environment before starting the server."
    )
