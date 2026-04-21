"""Simple Rate Limiting Middleware for FastAPI"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, List

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 20, window: int = 60):
        super().__init__(app)
        self.limit = limit  # Max requests per window
        self.window = window  # Window in seconds
        self.requests: Dict[str, List[float]] = {}

    async def dispatch(self, request: Request, call_next):
        # 优先使用 X-Forwarded-For 头获取真实客户端 IP（反向代理场景）
        client_ip = request.headers.get("x-forwarded-for", getattr(request.client, "host", "unknown")).split(",")[0].strip()
        now = time.time()

        # 清理所有过期 key，防止内存无限增长
        expired_keys = [k for k, timestamps in self.requests.items() if timestamps and now - timestamps[-1] > self.window]
        for k in expired_keys:
            del self.requests[k]

        if client_ip not in self.requests:
            self.requests[client_ip] = []

        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < self.window]

        if len(self.requests[client_ip]) >= self.limit:
            return JSONResponse(
                {"error": True, "status_code": 429, "detail": "Too many requests. Please try again later."},
                status_code=429,
            )

        self.requests[client_ip].append(now)
        response = await call_next(request)
        return response
