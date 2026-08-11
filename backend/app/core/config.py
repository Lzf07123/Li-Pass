from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Portal OSS"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5432/portal"
    redis_url: str = "redis://localhost:6379/0"
    session_cookie_name: str = "portal_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_days: int = 30
    cors_origins: list[str] = ["http://localhost:5173"]
    email_backend: str = "console"


@lru_cache
def get_settings() -> Settings:
    return Settings()
