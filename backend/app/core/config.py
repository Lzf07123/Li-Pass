from functools import lru_cache
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "LinPass SSO"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5432/portal"
    redis_url: str = "redis://localhost:6379/0"
    session_cookie_name: str = "portal_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_days: int = 30
    session_default_ttl_days: int = 1
    session_idle_days: int = 7
    cors_origins: list[str] = ["http://localhost:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    email_backend: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "LinPass SSO"
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 15
    smtp_max_retries: int = 2
    smtp_retry_delay_seconds: float = 1.0
    frontend_base_url: str = "http://localhost:5173"
    jwt_issuer: str = "http://localhost:8000"
    jwt_private_key_path: str = "jwt_private.pem"
    oauth_access_token_ttl_minutes: int = 15
    oauth_id_token_ttl_minutes: int = 5
    oauth_code_ttl_minutes: int = 10
    pending_request_store: str = "memory"
    encryption_key_path: str = "encryption.key"
    twofa_store: str = "memory"
    rate_limiter: str = "memory"
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 900
    login_ip_rate_limit: int = 30
    otp_send_limit: int = 5
    otp_send_window_seconds: int = 3600
    otp_resend_cooldown_seconds: int = 60
    register_rate_limit: int = 10
    register_rate_window_seconds: int = 3600
    # 公开注册入口开关：关闭后普通注册返回 403，仅保留邀请注册渠道。
    public_registration_enabled: bool = True
    admin_invite_rate_limit: int = 100
    admin_invite_rate_window_seconds: int = 3600
    password_reset_rate_limit: int = 5
    password_reset_rate_window_seconds: int = 3600
    email_verify_rate_limit: int = 30
    email_verify_rate_window_seconds: int = 3600
    twofa_verify_rate_limit: int = 60
    twofa_verify_rate_window_seconds: int = 900
    invite_ttl_days: int = 7
    avatar_upload_dir: str = "uploads/avatars"
    avatar_max_size_mb: int = 5
    avatar_cleanup_interval_seconds: int = 21600
    # 过期 OTP/授权码的保留期：默认 7 天，过期即对业务无意义，
    # 保留一小段窗口便于排查后即可安全清理，防止表无限增长。
    ephemeral_retention_hours: int = 168
    db_pool_size: int = 5
    db_max_overflow: int = 10

    @model_validator(mode="after")
    def _validate_production(self):
        if self.environment not in ("development", "production"):
            raise ValueError(
                "ENVIRONMENT 必须为 development 或 production，防止拼写错误导致生产校验被跳过"
            )
        if self.session_cookie_samesite not in ("lax", "strict", "none"):
            raise ValueError("SESSION_COOKIE_SAMESITE 必须为 lax、strict 或 none")
        if self.email_backend not in ("console", "smtp"):
            raise ValueError("EMAIL_BACKEND 必须为 console 或 smtp")
        if not (1 <= self.smtp_port <= 65535):
            raise ValueError("SMTP_PORT 必须在 1–65535 之间")
        if self.smtp_timeout_seconds < 1:
            raise ValueError("SMTP_TIMEOUT_SECONDS 必须 ≥1")
        if not (0 <= self.smtp_max_retries <= 5):
            raise ValueError("SMTP_MAX_RETRIES 必须在 0–5 之间")
        if self.smtp_retry_delay_seconds < 0:
            raise ValueError("SMTP_RETRY_DELAY_SECONDS 必须 ≥0")
        if not self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS 不能为空")
        if self.db_pool_size < 1 or self.db_max_overflow < 0:
            raise ValueError("DB_POOL_SIZE 必须 ≥1，DB_MAX_OVERFLOW 必须 ≥0")
        if self.admin_invite_rate_limit < 1 or self.admin_invite_rate_window_seconds < 1:
            raise ValueError(
                "ADMIN_INVITE_RATE_LIMIT/ADMIN_INVITE_RATE_WINDOW_SECONDS 必须 ≥1"
            )
        if self.ephemeral_retention_hours < 1:
            raise ValueError("EPHEMERAL_RETENTION_HOURS 必须 ≥1")
        if self.session_idle_days < 1:
            raise ValueError("SESSION_IDLE_DAYS 必须 ≥1")
        if self.session_default_ttl_days < 1:
            raise ValueError("SESSION_DEFAULT_TTL_DAYS 必须 ≥1")
        if self.session_default_ttl_days > self.session_ttl_days:
            raise ValueError("SESSION_DEFAULT_TTL_DAYS 不能大于 SESSION_TTL_DAYS")
        if self.environment != "production":
            return self
        for field in ("jwt_issuer", "frontend_base_url", "database_url", "redis_url"):
            value = getattr(self, field)
            if not value or "localhost" in value or "127.0.0.1" in value:
                raise ValueError(f"{field} 在生产环境必须显式配置真实地址，禁止使用默认值")
        for field in ("jwt_private_key_path", "encryption_key_path"):
            path = getattr(self, field)
            if not path or not path.startswith("/"):
                raise ValueError(
                    f"{field} 在生产环境必须使用绝对路径（推荐 /app/keys/ 下的持久卷）"
                )
        if self.email_backend != "smtp" or not self.smtp_host or not self.smtp_from:
            raise ValueError(
                "生产环境邮件必须配置 EMAIL_BACKEND=smtp 与 SMTP_HOST/SMTP_FROM"
            )
        if not self.session_cookie_secure:
            raise ValueError("生产环境必须设置 SESSION_COOKIE_SECURE=true（HTTPS）")
        origins = [str(origin).rstrip("/") for origin in self.cors_origins]
        if not origins or any(
            origin == "*" or "localhost" in origin or "127.0.0.1" in origin
            for origin in origins
        ):
            raise ValueError("生产环境 CORS_ORIGINS 必须配置真实 HTTPS 来源，禁止 * 或 localhost")
        real_hosts = [
            host
            for host in self.allowed_hosts
            if host not in ("localhost", "127.0.0.1", "testserver")
        ]
        if not real_hosts:
            raise ValueError(
                "生产环境 ALLOWED_HOSTS 必须包含至少一个真实域名（可同时保留 "
                "127.0.0.1 供容器健康检查）"
            )
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SAMESITE=none 在生产环境必须配合 HTTPS（secure=true）")
        for store, name in (
            (self.pending_request_store, "PENDING_REQUEST_STORE"),
            (self.twofa_store, "TWOFA_STORE"),
            (self.rate_limiter, "RATE_LIMITER"),
        ):
            if store != "redis":
                raise ValueError(f"生产环境 {name} 必须使用 redis")
        db_password = urlparse(self.database_url).password or ""
        if len(db_password) < 12 or db_password in ("portal", "postgres", "password"):
            raise ValueError("生产环境数据库口令必须使用长度 ≥12 的强密码")
        redis_password = urlparse(self.redis_url).password or ""
        if (
            len(redis_password) < 12
            or redis_password in ("portal", "portal-dev-redis", "redis")
        ):
            raise ValueError("生产环境 Redis 必须启用 AUTH 并使用长度 ≥12 的强密码")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
