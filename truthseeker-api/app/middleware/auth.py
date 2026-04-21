"""JWT 认证中间件 — 验证 Supabase 签发的 token"""
import logging

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

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
})


def _is_public(path: str, method: str = "GET") -> bool:
    """判断路径是否为公开路由（A-1 修复：精确 + 受控前缀匹配）"""
    if path in PUBLIC_PATHS:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    # GET-only 公开路径：仅 GET 请求放行
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


class AuthMiddleware(BaseHTTPMiddleware):
    """可选 JWT 认证：有 token 则提取 user_id，无 token 则为匿名"""

    def __init__(self, app, supabase_jwt_secret: str):
        super().__init__(app)
        self.jwt_secret = supabase_jwt_secret

    async def dispatch(self, request: Request, call_next):
        # 公开路径：仍然尝试提取 user_id 用于追踪（X-4 修复）
        if _is_public(request.url.path, request.method):
            request.state.user_id = "anonymous"
            request.state.is_authenticated = False
            self._try_extract_user(request)
            return await call_next(request)

        # 受保护路径：必须认证
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": True, "status_code": 401, "detail": "未提供认证令牌"},
                status_code=401,
            )

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",  # A-2 修复：校验 audience
            )
            sub = payload.get("sub")
            if not sub:
                return JSONResponse(
                    {"error": True, "status_code": 401, "detail": "令牌缺少用户标识"},
                    status_code=401,
                )
            request.state.user_id = sub
            request.state.is_authenticated = True

        except jwt.ExpiredSignatureError:
            return JSONResponse({"error": True, "status_code": 401, "detail": "令牌已过期"}, status_code=401)
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT: %s", e)
            return JSONResponse({"error": True, "status_code": 401, "detail": "无效的认证令牌"}, status_code=401)

        try:
            return await call_next(request)
        except Exception as e:
            logger.error("Request processing error after auth: %s", e)
            return JSONResponse({"error": True, "status_code": 500, "detail": "服务器内部错误"}, status_code=500)

    def _try_extract_user(self, request: Request) -> None:
        """尝试从公开路由的请求中提取 user_id（X-4 修复）"""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token, self.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            sub = payload.get("sub")
            if sub:
                request.state.user_id = sub
                request.state.is_authenticated = True
        except jwt.InvalidTokenError:
            pass  # 公开路由，token 无效不影响访问
