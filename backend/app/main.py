from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin_clients as admin_clients_routes
from app.api.routes import admin_users as admin_users_routes
from app.api.routes import auth as auth_routes
from app.api.routes import client_blocks as client_blocks_routes
from app.api.routes import consent as consent_routes
from app.api.routes import oidc as oidc_routes
from app.api.routes import users as user_routes
from app.api.routes import twofa as twofa_routes
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

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
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; connect-src 'self' {settings.jwt_issuer}; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'"
        )
        return response

    app.include_router(auth_routes.router)
    app.include_router(user_routes.router)
    app.include_router(twofa_routes.router)
    app.include_router(admin_clients_routes.router)
    app.include_router(admin_users_routes.router)
    app.include_router(consent_routes.router)
    app.include_router(client_blocks_routes.router)
    app.include_router(oidc_routes.router)
    return app


app = create_app()
