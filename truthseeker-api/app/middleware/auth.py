"""Supabase JWT 验证中间件"""
import jwt
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# 不需要鉴权的路由前缀（公开路由）
PUBLIC_PATHS = {"/health", "/api/v1/detect", "/api/v1/tasks", "/api/v1/upload"}


class AuthMiddleware(BaseHTTPMiddleware):
    """验证 Supabase JWT，将 user_id 注入 request.state"""

    def __init__(self, app, supabase_jwt_secret: str):
        super().__init__(app)
        self.jwt_secret = supabase_jwt_secret

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            request.state.user_id = None
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization token")

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            request.state.user_id = payload.get("sub")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        return await call_next(request)
