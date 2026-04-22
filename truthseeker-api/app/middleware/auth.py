"""JWT 认证中间件 — 纯 ASGI 实现，兼容 SSE StreamingResponse"""
import logging

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# 精确匹配的公开路径（A-1 修复：避免 startswith 前缀绕过）
PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
})

# 需要前缀匹配的公开路径（必须以 / 结尾）
PUBLIC_PREFIXES: frozenset[str] = frozenset()

# GET-only 公开前缀（POST/PUT/DELETE 仍需认证）
PUBLIC_GET_PREFIXES: frozenset[str] = frozenset({
    "/api/v1/share/",
    "/api/v1/consultation/invite/",
})

PUBLIC_POST_PATH_SUFFIXES: frozenset[str] = frozenset({
    "/inject",
})

PUBLIC_GET_CONSULTATION_SUFFIXES: frozenset[str] = frozenset({
    "/messages",
    "/unread",
    "/agent-history",
})


def _is_public(path: str, method: str = "GET") -> bool:
    """判断路径是否为公开路由（A-1 修复：精确 + 受控前缀匹配）"""
    if path in PUBLIC_PATHS:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    if method.upper() == "GET":
        for prefix in PUBLIC_GET_PREFIXES:
            if path.startswith(prefix):
                return True
    if method.upper() == "POST":
        for suffix in PUBLIC_POST_PATH_SUFFIXES:
            if path.startswith("/api/v1/consultation/") and path.endswith(suffix):
                return True
    if method.upper() == "GET":
        for suffix in PUBLIC_GET_CONSULTATION_SUFFIXES:
            if path.startswith("/api/v1/consultation/") and path.endswith(suffix):
                return True
    return False


class AuthMiddleware:
    """JWT 认证 — 纯 ASGI 中间件，兼容 SSE 流式响应。

    BaseHTTPMiddleware 会消费 StreamingResponse 的 body 导致 SSE 断裂，
    改用纯 ASGI 让流式响应直接透传。
    """

    def __init__(self, app, supabase_jwt_secret: str, supabase_url: str = ""):
        self.app = app
        self.jwt_secret = supabase_jwt_secret
        self.jwks_client: PyJWKClient | None = None

        if supabase_url:
            jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            self.jwks_client = PyJWKClient(jwks_url, cache_keys=True)
            logger.info("JWKS client initialized: %s", jwks_url)

    def _verify_token(self, token: str) -> dict:
        """验证 JWT — 优先 JWKS（ES256），回退 HS256"""
        if self.jwks_client:
            try:
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256"],
                    audience="authenticated",
                )
            except jwt.InvalidTokenError:
                pass

        return jwt.decode(
            token,
            self.jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

    def _json_response(self, scope: dict, status: int, detail: str):
        """构造 JSON 错误响应的 ASGI 发送序列"""
        import json as _json

        body = _json.dumps(
            {"error": True, "status_code": status, "detail": detail},
            ensure_ascii=False,
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]
        return [
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            },
            {"type": "http.response.body", "body": body},
        ]

    def _parse_headers(self, scope: dict) -> dict[str, str]:
        """从 ASGI scope 解析请求头"""
        return {
            name.decode().lower(): value.decode()
            for name, value in scope.get("headers", [])
        }

    async def __call__(self, scope: dict, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        headers = self._parse_headers(scope)
        auth_header = headers.get("authorization", "")
        user_id = "anonymous"
        is_authenticated = False

        if method.upper() == "OPTIONS" or _is_public(path, method):
            # 公开路由：尝试提取用户但不阻断
            if auth_header.startswith("Bearer "):
                try:
                    payload = self._verify_token(auth_header[7:])
                    sub = payload.get("sub")
                    if sub:
                        user_id = sub
                        is_authenticated = True
                except jwt.InvalidTokenError:
                    pass
        else:
            # 受保护路由：必须提供有效 token
            if not auth_header.startswith("Bearer "):
                for msg in self._json_response(scope, 401, "未提供认证令牌"):
                    await send(msg)
                return

            try:
                payload = self._verify_token(auth_header[7:])
                sub = payload.get("sub")
                if not sub:
                    for msg in self._json_response(scope, 401, "令牌缺少用户标识"):
                        await send(msg)
                    return
                user_id = sub
                is_authenticated = True
            except jwt.ExpiredSignatureError:
                for msg in self._json_response(scope, 401, "令牌已过期"):
                    await send(msg)
                return
            except jwt.InvalidTokenError as e:
                logger.warning("Invalid JWT: %s", e)
                for msg in self._json_response(scope, 401, "无效的认证令牌"):
                    await send(msg)
                return

        # 注入 user_id 到 scope 的 state 中
        scope.setdefault("state", {})
        scope["state"]["user_id"] = user_id
        scope["state"]["is_authenticated"] = is_authenticated

        await self.app(scope, receive, send)
