import asyncio
import contextlib
import logging
from urllib.parse import urlparse

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import admin_clients as admin_clients_routes
from app.api.routes import admin_notifications as admin_notifications_routes
from app.api.routes import admin_sessions as admin_sessions_routes
from app.api.routes import admin_settings as admin_settings_routes
from app.api.routes import admin_stats as admin_stats_routes
from app.api.routes import admin_system as admin_system_routes
from app.api.routes import admin_users as admin_users_routes
from app.api.routes import auth as auth_routes
from app.api.routes import client_blocks as client_blocks_routes
from app.api.routes import consent as consent_routes
from app.api.routes import messages as messages_routes
from app.api.routes import oidc as oidc_routes
from app.api.routes import users as user_routes
from app.api.routes import twofa as twofa_routes
from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis import get_redis_client
from app.services.avatar_cleanup import cleanup_orphan_avatars
from app.services.email import warn_email_config
from app.services.ip2region_update import maybe_auto_update
from app.services.maintenance import cleanup_expired_ephemeral_rows

logger = logging.getLogger(__name__)


def _run_maintenance(app: FastAPI) -> None:
    """执行一次后台维护：孤儿头像 + 过期临时凭证；失败仅记录日志。"""
    try:
        dependency = app.dependency_overrides.get(get_db, get_db)
        db = next(dependency())
        try:
            removed_files, removed_dirs = cleanup_orphan_avatars(db)
            if removed_files or removed_dirs:
                logger.info(
                    "头像自动清理：删除 %d 个未引用文件、%d 个空目录",
                    removed_files,
                    removed_dirs,
                )
            counts = cleanup_expired_ephemeral_rows(db)
            total = sum(counts.values())
            if total:
                logger.info(
                    "临时凭证清理：OTP %d 条、授权码 %d 条、邀请 %d 条、审计日志 %d 条、会话 %d 条",
                    counts["otps"],
                    counts["authorization_codes"],
                    counts["account_invites"],
                    counts["audit_logs"],
                    counts["sessions"],
                )
        finally:
            db.close()
    except Exception:
        logger.exception("后台维护任务失败")


def _run_ip2region_update(app: FastAPI) -> None:
    """检查站点设置并按间隔执行 ip2region 自动更新；失败仅记录日志。"""
    try:
        dependency = app.dependency_overrides.get(get_db, get_db)
        db = next(dependency())
        try:
            maybe_auto_update(db)
        finally:
            db.close()
    except Exception:
        logger.exception("ip2region 自动更新检查失败")


async def _maintenance_loop(app: FastAPI) -> None:
    interval = get_settings().avatar_cleanup_interval_seconds
    if interval <= 0:
        return
    while True:
        await asyncio.sleep(interval)
        # 文件扫描/数据库删除是阻塞 IO，放到线程池执行，避免卡住事件循环。
        await asyncio.to_thread(_run_maintenance, app)


async def _ip2region_update_loop(app: FastAPI) -> None:
    """每小时醒来一次；是否执行/多久执行一次由站点设置决定。"""
    while True:
        await asyncio.sleep(3600)
        await asyncio.to_thread(_run_ip2region_update, app)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时先清理一次历史遗留；周期任务可单独开关。
    await asyncio.to_thread(_run_maintenance, app)
    warn_email_config(get_settings())
    maintenance_task = None
    if get_settings().avatar_cleanup_interval_seconds > 0:
        maintenance_task = asyncio.create_task(_maintenance_loop(app))
    ip2region_task = asyncio.create_task(_ip2region_update_loop(app))
    try:
        yield
    finally:
        ip2region_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ip2region_task
        if maintenance_task is not None:
            maintenance_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await maintenance_task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
        ],
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
            # 共享客户端已配置 2s 连接/读写超时，Redis 故障时快速失败。
            get_redis_client().ping()
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
        # 认证/业务接口包含用户数据，禁止浏览器与共享代理缓存；
        # 头像等公开静态资源除外（文件名带随机 UUID，可由网关长缓存）。
        if not request.url.path.startswith("/uploads/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Accept-CH"] = (
            "Sec-CH-UA-Model, Sec-CH-UA-Platform-Version"
        )
        response.headers["Content-Security-Policy"] = _build_csp(settings)
        if settings.session_cookie_secure:
            # 生产（HTTPS）自动签发 HSTS；开发/测试不签发，避免 HTTP 直连误发。
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
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
    app.include_router(admin_settings_routes.router)
    app.include_router(admin_users_routes.router)
    app.include_router(admin_sessions_routes.router)
    app.include_router(admin_notifications_routes.router)
    app.include_router(admin_system_routes.router)
    app.include_router(admin_stats_routes.router)
    app.include_router(messages_routes.router)
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


def _build_csp(settings) -> str:
    """构造 CSP：生产禁用内联样式；开发保留以支撑 Swagger 文档内联样式。"""
    style_src = (
        "'self'" if settings.environment == "production" else "'self' 'unsafe-inline'"
    )
    return (
        f"default-src 'self'; connect-src 'self' {_origin(settings.jwt_issuer)}; "
        f"img-src 'self' data:; style-src {style_src}"
    )


app = create_app()
