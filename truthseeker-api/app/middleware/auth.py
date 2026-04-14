"""Supabase JWT 验证中间件"""
import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# 不需要鉴权的路由前缀（前缀匹配，有意为之）
PUBLIC_PATHS = {"/health", "/api/v1/detect", "/api/v1/tasks", "/api/v1/upload"}


class AuthMiddleware(BaseHTTPMiddleware):
    """验证 Supabase JWT，将 user_id 注入 request.state"""

    def __init__(self, app, supabase_jwt_secret: str):
        super().__init__(app)
        self.jwt_secret = supabase_jwt_secret

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 公开路由跳过鉴权
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            request.state.user_id = None
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Missing authorization token"}, status_code=401)

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
            if not user_id:
                return JSONResponse({"detail": "Invalid token: missing sub"}, status_code=401)
            request.state.user_id = user_id
        except jwt.ExpiredSignatureError:
            return JSONResponse({"detail": "Token expired"}, status_code=401)
        except jwt.InvalidTokenError:
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        return await call_next(request)
