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
        "MINIMAX_API_KEY", "MINIMAX_BASE_URL", "MINIMAX_MODEL",
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
        default="kimi-k2.6",
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
        default="kimi-k2.6",
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
        default="kimi-k2.6",
        validation_alias=AliasChoices("KIMI_CODING_MODEL", "Kimi_Coding_Model"),
    )
    KIMI_SILICONFLOW_API_KEY: str = Field(default="", validation_alias=AliasChoices("KIMI_SILICONFLOW_API_KEY"))
    KIMI_SILICONFLOW_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        validation_alias=AliasChoices("KIMI_SILICONFLOW_BASE_URL"),
    )
    KIMI_SILICONFLOW_MODEL: str = Field(
        default="Pro/moonshotai/Kimi-K2.6",
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
    MINIMAX_API_KEY: str = Field(default="", validation_alias=AliasChoices("MINIMAX_API_KEY", "MiniMax_API_KEY"))
    MINIMAX_BASE_URL: str = Field(
        default="https://minnimax.chat/v1",
        validation_alias=AliasChoices("MINIMAX_BASE_URL", "MiniMax_Base_URL"),
    )
    MINIMAX_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        validation_alias=AliasChoices("MINIMAX_MODEL", "MiniMax_Model"),
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

    # 音频 ASR — 取证阶段音频语义转写，用于校验音频内容与文本主题的一致性。
    # 通过 AUDIO_ASR_PROVIDER 在两个服务商之间切换：
    # - groq：Groq OpenAI 兼容 Whisper（海外）
    # - baidu：百度智能云短语音识别极速版（国内，dev_pid=80001 普通话输入法模型）
    AUDIO_ASR_ENABLED: bool = Field(default=True, validation_alias=AliasChoices("AUDIO_ASR_ENABLED", "Audio_ASR_Enabled"))
    AUDIO_ASR_PROVIDER: str = Field(default="groq", validation_alias=AliasChoices("AUDIO_ASR_PROVIDER", "Audio_ASR_Provider"))
    GROQ_API_KEY: str = Field(default="", validation_alias=AliasChoices("GROQ_API_KEY", "Groq_API_Key"))
    GROQ_ASR_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("GROQ_ASR_BASE_URL", "Groq_ASR_Base_URL"),
    )
    GROQ_ASR_MODEL: str = Field(
        default="whisper-large-v3-turbo",
        validation_alias=AliasChoices("GROQ_ASR_MODEL", "Groq_ASR_Model"),
    )
    # 百度智能云短语音识别极速版：控制台创建应用并勾选开通“短语音识别极速版”后，
    # 取得应用的 API Key（client_id）与 Secret Key（client_secret）
    BAIDU_ASR_API_KEY: str = Field(default="", validation_alias=AliasChoices("BAIDU_ASR_API_KEY", "Baidu_ASR_API_Key"))
    BAIDU_ASR_SECRET_KEY: str = Field(default="", validation_alias=AliasChoices("BAIDU_ASR_SECRET_KEY", "Baidu_ASR_Secret_Key"))
    BAIDU_ASR_DEV_PID: int = Field(default=80001, validation_alias=AliasChoices("BAIDU_ASR_DEV_PID", "Baidu_ASR_Dev_Pid"))
    BAIDU_ASR_BASE_URL: str = Field(
        default="https://vop.baidu.com/pro_api",
        validation_alias=AliasChoices("BAIDU_ASR_BASE_URL", "Baidu_ASR_Base_URL"),
    )
    BAIDU_ASR_TOKEN_URL: str = Field(
        default="https://aip.baidubce.com/oauth/2.0/token",
        validation_alias=AliasChoices("BAIDU_ASR_TOKEN_URL", "Baidu_ASR_Token_URL"),
    )
    BAIDU_ASR_CUID: str = Field(default="truthseeker-api", validation_alias=AliasChoices("BAIDU_ASR_CUID", "Baidu_ASR_Cuid"))
    AUDIO_ASR_MAX_FILE_MB: float = Field(default=50.0, validation_alias=AliasChoices("AUDIO_ASR_MAX_FILE_MB", "Audio_ASR_Max_File_MB"))
    AUDIO_ASR_TIMEOUT_SECONDS: float = Field(default=90.0, validation_alias=AliasChoices("AUDIO_ASR_TIMEOUT_SECONDS", "Audio_ASR_Timeout_Seconds"))
    AUDIO_ASR_TOOL_TIMEOUT_SECONDS: float = Field(default=180.0, validation_alias=AliasChoices("AUDIO_ASR_TOOL_TIMEOUT_SECONDS", "Audio_ASR_Tool_Timeout_Seconds"))
    # 留空时按 PATH 查找 ffmpeg/ffprobe，再回退到本机常见安装目录
    FFMPEG_BINARY: str = Field(default="", validation_alias=AliasChoices("FFMPEG_BINARY", "FFmpeg_Binary"))
    FFPROBE_BINARY: str = Field(default="", validation_alias=AliasChoices("FFPROBE_BINARY", "FFprobe_Binary"))

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
    # 每阶段每次检测最多触发的人机协同次数；超过后带残留风险放行，不再打扰用户
    CONSULTATION_MAX_SESSIONS_PER_PHASE: int = 1
    # 单次人机协同向用户/专家提出的问题上限
    CONSULTATION_MAX_QUESTIONS: int = 3
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
    value = (provider or "kimi-k2.6").strip().lower().replace("-", "_")
    if value in {"mimo", "xiaomi_mimo", "mimo_v2.5", "mimo_v2_5", "mimo_token_plan", "xiaomi_token_plan"}:
        return "mimo"
    if value in {"minimax", "mini_max", "minnimax"}:
        return "minimax"
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
    official_model = (env.get("KIMI_MODEL") or cfg.KIMI_MODEL or "kimi-k2.6").strip() or "kimi-k2.6"
    official_base = _normalize_kimi_base_url(env.get("KIMI_BASE_URL") or cfg.KIMI_BASE_URL, "official")

    if agent_provider == "minimax":
        minimax_key = env.get("MINIMAX_API_KEY") or cfg.MINIMAX_API_KEY
        minimax_model = (env.get("MINIMAX_MODEL") or cfg.MINIMAX_MODEL or "claude-3-5-sonnet-20241022").strip()
        minimax_base = (
            env.get("MINIMAX_BASE_URL")
            or cfg.MINIMAX_BASE_URL
            or "https://minnimax.chat/v1"
        ).strip().rstrip("/")
        return {
            "provider": "minimax",
            "model": minimax_model,
            "base_url": minimax_base,
            "api_key": minimax_key,
            "thinking": "disabled",
            "max_output_tokens": str(_parse_positive_int(
                env.get("AGENT_LLM_MAX_OUTPUT_TOKENS") or cfg.AGENT_LLM_MAX_OUTPUT_TOKENS,
                4096,
            )),
        }
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
        coding_model = (env.get("KIMI_CODING_MODEL") or cfg.KIMI_CODING_MODEL or "kimi-k2.6").strip() or "kimi-k2.6"
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
        sf_model = (env.get("KIMI_SILICONFLOW_MODEL") or cfg.KIMI_SILICONFLOW_MODEL or "Pro/moonshotai/Kimi-K2.6").strip()
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


def _normalize_asr_provider(provider: str) -> str:
    value = (provider or "groq").strip().lower().replace("-", "_")
    if value in {"baidu", "baidu_cloud", "baiduyun", "baidu_yun"}:
        return "baidu"
    return "groq"


def resolve_asr_runtime(config: Settings | None = None) -> dict:
    """Resolve ASR runtime config, hot-reloading key fields from .env.

    与 resolve_kimi_runtime 同样每次从 .env 重新读取，避免配置 Key 后必须重启服务。
    `AUDIO_ASR_PROVIDER` 决定服务商（groq/baidu）；两套 Key 都会解析，
    调用方按 provider 取用，切换服务商只需改 .env 并配好对应 Key。
    """
    cfg = config or settings
    raw = dotenv_values(str(_ENV_PATH))

    def pick(key: str, default: str) -> str:
        value = raw.get(key)
        return value if value is not None else default

    enabled_raw = (pick("AUDIO_ASR_ENABLED", str(cfg.AUDIO_ASR_ENABLED)) or "true").strip().lower()
    provider = _normalize_asr_provider(pick("AUDIO_ASR_PROVIDER", cfg.AUDIO_ASR_PROVIDER))

    try:
        dev_pid = int(str(pick("BAIDU_ASR_DEV_PID", cfg.BAIDU_ASR_DEV_PID)).strip())
    except (TypeError, ValueError):
        dev_pid = 80001
    cuid = (pick("BAIDU_ASR_CUID", cfg.BAIDU_ASR_CUID) or "").strip()[:60] or "truthseeker-api"

    return {
        "enabled": enabled_raw not in {"false", "0", "no", "off", "disabled"},
        "provider": provider,
        # Groq OpenAI 兼容 Whisper
        "api_key": (pick("GROQ_API_KEY", cfg.GROQ_API_KEY) or "").strip(),
        "base_url": (
            pick("GROQ_ASR_BASE_URL", cfg.GROQ_ASR_BASE_URL) or "https://api.groq.com/openai/v1"
        ).strip().rstrip("/"),
        "model": (pick("GROQ_ASR_MODEL", cfg.GROQ_ASR_MODEL) or "whisper-large-v3-turbo").strip(),
        # 百度智能云短语音识别极速版
        "baidu_api_key": (pick("BAIDU_ASR_API_KEY", cfg.BAIDU_ASR_API_KEY) or "").strip(),
        "baidu_secret_key": (pick("BAIDU_ASR_SECRET_KEY", cfg.BAIDU_ASR_SECRET_KEY) or "").strip(),
        "baidu_dev_pid": dev_pid if dev_pid > 0 else 80001,
        "baidu_base_url": (
            pick("BAIDU_ASR_BASE_URL", cfg.BAIDU_ASR_BASE_URL) or "https://vop.baidu.com/pro_api"
        ).strip().rstrip("/"),
        "baidu_token_url": (
            pick("BAIDU_ASR_TOKEN_URL", cfg.BAIDU_ASR_TOKEN_URL) or "https://aip.baidubce.com/oauth/2.0/token"
        ).strip().rstrip("/"),
        "baidu_cuid": cuid,
        "max_file_mb": cfg.AUDIO_ASR_MAX_FILE_MB,
        "timeout_seconds": cfg.AUDIO_ASR_TIMEOUT_SECONDS,
    }


# Production safety check: refuse to run with placeholder JWT secret
if settings.APP_ENV == "production" and settings.SUPABASE_JWT_SECRET in ("NOT_SET", "", "your-jwt-secret"):
    raise RuntimeError(
        "SUPABASE_JWT_SECRET is not configured for production. "
        "Set a real JWT secret in the environment before starting the server."
    )
