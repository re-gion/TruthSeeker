"""TruthSeeker FastAPI Application Entry Point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 TruthSeeker API starting - Supabase: {settings.SUPABASE_URL}")
    yield
    print("⚡ TruthSeeker API shutting down")


from app.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(
    title="TruthSeeker API",
    description="Cross-modal deepfake detection with multi-agent debate",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Middleware ───
app.add_middleware(RateLimitMiddleware, limit=30, window=60)
from app.middleware.auth import AuthMiddleware
if settings.SUPABASE_JWT_SECRET:
    app.add_middleware(AuthMiddleware, supabase_jwt_secret=settings.SUPABASE_JWT_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TruthSeeker API", "version": "1.0.0"}
