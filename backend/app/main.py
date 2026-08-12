from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
