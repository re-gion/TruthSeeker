"""TruthSeeker FastAPI Application Entry Point"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config import settings
from app.middleware.auth import AuthMiddleware
from app.middleware.exception_handler import http_exception_handler, unhandled_exception_handler
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)


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
    if settings.SUPABASE_JWT_SECRET == "NOT_SET":
        logger.warning("SUPABASE_JWT_SECRET not configured — auth middleware disabled")
    yield
    logger.info("TruthSeeker API shutting down")


app = FastAPI(
    title="TruthSeeker API",
    description="Cross-modal deepfake detection with multi-agent debate",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Exception Handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ─── Middleware（M-1 修复：注册逆序执行，RateLimit 需在最外层）───
# Starlette 中间件按注册逆序执行请求，因此注册顺序应为：
# 1. CORS（最内层）→ 2. Auth → 3. RateLimit（最外层，最先执行）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.SUPABASE_JWT_SECRET and settings.SUPABASE_JWT_SECRET != "NOT_SET":
    app.add_middleware(AuthMiddleware, supabase_jwt_secret=settings.SUPABASE_JWT_SECRET)
app.add_middleware(RateLimitMiddleware, limit=30, window=60)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TruthSeeker API", "version": "1.0.0"}
