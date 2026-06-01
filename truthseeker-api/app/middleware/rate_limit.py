"""Simple Rate Limiting Middleware — 纯 ASGI 实现，兼容 SSE StreamingResponse"""
import json
import time
from typing import Dict, List

# 不计入限流的路径后缀（高频轮询接口）
_RATE_LIMIT_EXEMPT_SUFFIXES: frozenset[str] = frozenset({
    "/messages",
    "/unread",
    "/agent-history",
    "/session",
})


class RateLimitMiddleware:
    """纯 ASGI 限流中间件，不使用 BaseHTTPMiddleware 以兼容 SSE 流。"""

    def __init__(self, app, limit: int = 20, window: int = 60):
        self.app = app
        self.limit = limit
        self.window = window
        self.requests: Dict[str, List[float]] = {}

    def _json_response(self, scope: dict, status: int, detail: str):
        # 从请求头提取 Origin，确保限流错误响应也携带 CORS 头
        headers_map = {
            name.decode().lower(): value.decode()
            for name, value in scope.get("headers", [])
        }
        origin = headers_map.get("origin", "")
        cors_headers: list[tuple[bytes, bytes]] = []
        if origin:
            cors_headers = [
                (b"access-control-allow-origin", origin.encode()),
                (b"access-control-allow-credentials", b"true"),
            ]

        body = json.dumps(
            {"error": True, "status_code": status, "detail": detail},
            ensure_ascii=False,
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            *cors_headers,
        ]
        return [
            {"type": "http.response.start", "status": status, "headers": headers},
            {"type": "http.response.body", "body": body},
        ]

    def _parse_headers(self, scope: dict) -> dict[str, str]:
        return {
            name.decode().lower(): value.decode()
            for name, value in scope.get("headers", [])
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")

        # OPTIONS preflight 和高频轮询接口不计入限流
        if method == "OPTIONS" or any(path.endswith(s) for s in _RATE_LIMIT_EXEMPT_SUFFIXES):
            await self.app(scope, receive, send)
            return

        headers = self._parse_headers(scope)
        client_ip = headers.get(
            "x-forwarded-for",
            (scope.get("client") or ("unknown",))[0],
        ).split(",")[0].strip()

        now = time.time()
        expired_keys = [k for k, ts in self.requests.items() if ts and now - ts[-1] > self.window]
        for k in expired_keys:
            del self.requests[k]

        self.requests.setdefault(client_ip, [])
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < self.window]

        if len(self.requests[client_ip]) >= self.limit:
            for msg in self._json_response(
                scope, 429, "Too many requests. Please try again later."
            ):
                await send(msg)
            return

        self.requests[client_ip].append(now)
        await self.app(scope, receive, send)
