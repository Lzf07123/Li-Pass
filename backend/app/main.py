from urllib.parse import urlparse

import redis
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import admin_clients as admin_clients_routes
from app.api.routes import admin_users as admin_users_routes
from app.api.routes import auth as auth_routes
from app.api.routes import client_blocks as client_blocks_routes
from app.api.routes import consent as consent_routes
from app.api.routes import oidc as oidc_routes
from app.api.routes import users as user_routes
from app.api.routes import twofa as twofa_routes
from app.core.config import get_settings
from app.core.db import get_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

    _allowed_origins = {str(origin).rstrip("/") for origin in settings.cors_origins}

    @app.middleware("http")
    async def csrf_origin_check(request, call_next):
        """带会话 Cookie 的写请求必须声明允许的 Origin，阻断跨站 CSRF。

        浏览器发出的 POST/PUT/PATCH/DELETE 都会携带 Origin；缺失 Origin 视为
        非浏览器客户端（curl 等），不构成 CSRF 场景。第三方 OAuth 客户端直接
        调用 /oauth2/token 时不携带本门户会话 Cookie，不受此检查影响。
        """
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and request.cookies.get(settings.session_cookie_name):
                if origin.rstrip("/") not in _allowed_origins:
                    return JSONResponse(
                        status_code=403, content={"detail": "跨站请求被拒绝"}
                    )
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(db: Session = Depends(get_db)) -> dict[str, str]:
        """就绪检查：数据库可用，且配置了 Redis 存储时 Redis 也可用。"""
        db.execute(text("SELECT 1"))
        if (
            settings.pending_request_store == "redis"
            or settings.twofa_store == "redis"
            or settings.rate_limiter == "redis"
        ):
            client = redis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=2, socket_timeout=2
            )
            try:
                client.ping()
            finally:
                client.close()
        return {"status": "ready"}

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str | None]:
        """服务入口：返回服务信息与关键端点，避免根路径 404。"""
        return {
            "service": settings.app_name,
            "environment": settings.environment,
            "frontend": settings.frontend_base_url,
            "health": "/healthz",
            "ready": "/readyz",
            "docs": "/docs" if settings.environment != "production" else None,
            "openapi": "/openapi.json" if settings.environment != "production" else None,
        }

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = [str(part) for part in first.get("loc", []) if part not in ("body", "query", "path")]
        field = ".".join(loc)
        msg = str(first.get("msg", ""))
        if field == "email":
            detail = "邮箱格式不正确"
        elif "min_length" in msg or "max_length" in msg:
            detail = "输入长度不符合要求"
        else:
            detail = f"请求参数错误：{field} {msg}"
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; connect-src 'self' {_origin(settings.jwt_issuer)}; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'"
        )
        return response

    app.mount(
        "/uploads/avatars",
        StaticFiles(directory=settings.avatar_upload_dir, check_dir=False),
        name="uploads",
    )

    app.include_router(auth_routes.router)
    app.include_router(user_routes.router)
    app.include_router(twofa_routes.router)
    app.include_router(admin_clients_routes.router)
    app.include_router(admin_users_routes.router)
    app.include_router(consent_routes.router)
    app.include_router(client_blocks_routes.router)
    app.include_router(oidc_routes.router)
    return app


def _origin(url: str) -> str:
    """提取 URL 的 scheme://host[:port]，避免 CSP 源表达式带路径或尾斜杠。"""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        return url


app = create_app()
