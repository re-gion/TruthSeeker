"""TruthSeeker FastAPI Application Entry Point"""
import logging
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config import settings
from app.middleware.auth import AuthMiddleware
from app.middleware.exception_handler import http_exception_handler, unhandled_exception_handler
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.auth_config import validate_auth_configuration

logger = logging.getLogger(__name__)

AUTH_MIDDLEWARE_ENABLED = validate_auth_configuration(
    environment=settings.APP_ENV,
    jwt_secret=settings.SUPABASE_JWT_SECRET,
)


def setup_logging():
    """配置结构化日志 — 所有模块统一格式"""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("TruthSeeker API starting - Supabase: %s", settings.SUPABASE_URL)
    if not AUTH_MIDDLEWARE_ENABLED:
        logger.warning("SUPABASE_JWT_SECRET not configured — auth middleware disabled")
    yield
    logger.info("TruthSeeker API shutting down")


app = FastAPI(
    title="TruthSeeker API",
    description="Cross-modal malicious AIGC detection with multi-agent debate",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Exception Handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ─── Middleware ───
# Starlette 中间件按注册逆序包装：最后注册 = 最外层 = 最先执行请求
# 纯 ASGI 中间件通过 monkey-patch build_middleware_stack 注入，
# 因为 add_middleware 只支持 BaseHTTPMiddleware 子类。
# CORS 必须是最外层：Auth/RateLimit 直接 send 的 401/429 响应也需要
# 携带 CORS 头，否则浏览器跨域时会把这类响应当作网络错误
# （console 报 TypeError: Failed to fetch），用户看不到真实错误原因。
# 执行顺序（由外到内）：CORS → Auth → RateLimit → App

_original_build_middleware_stack = app.build_middleware_stack


def _cors_allowed_origins(frontend_url: str) -> list[str]:
    origins = {frontend_url.rstrip("/")}
    parsed = urlparse(frontend_url)
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"}:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        origins.add(f"{parsed.scheme}://localhost:{port}")
        origins.add(f"{parsed.scheme}://127.0.0.1:{port}")
    return sorted(origin for origin in origins if origin)


def _build_with_pure_asgi_middlewares():
    stack = _original_build_middleware_stack()
    # 内层先包：RateLimit，外层再包：Auth
    stack = RateLimitMiddleware(stack, limit=30, window=60)
    if AUTH_MIDDLEWARE_ENABLED:
        stack = AuthMiddleware(
            stack,
            supabase_jwt_secret=settings.SUPABASE_JWT_SECRET,
            supabase_url=settings.SUPABASE_URL,
        )
    # 不用 add_middleware 注册 CORS：那样 CORS 会被包在 Auth 内层，
    # Auth 直接发送的 401 响应将缺失 CORS 头，浏览器会把它当作跨域失败。
    return CORSMiddleware(
        stack,
        allow_origins=_cors_allowed_origins(settings.FRONTEND_URL),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


app.build_middleware_stack = _build_with_pure_asgi_middlewares

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TruthSeeker API", "version": "1.0.0"}
