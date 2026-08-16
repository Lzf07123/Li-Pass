from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 品牌改名过渡期保留的旧会话 Cookie 名：旧浏览器里尚未过期的会话继续可验证，
# 直到自然过期；新会话一律签发 lipass_session。
LEGACY_SESSION_COOKIE_NAME = "portal_session"

# .env 固定相对 config.py 解析（backend/.env），与进程工作目录解耦：
# 从仓库根或任意目录启动/测试时，不会误加载根目录的部署 .env。
ENV_FILE = str(Path(__file__).resolve().parents[2] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Li&Pass"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5432/portal"
    redis_url: str = "redis://localhost:6379/0"
    session_cookie_name: str = "lipass_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_days: int = 30
    session_default_ttl_days: int = 1
    session_idle_days: int = 7
    # 登录可信设备：勾选「信任此设备」后该设备 7 天内登录免二次验证（仅登录环节）。
    trusted_device_ttl_days: int = 7
    cors_origins: list[str] = ["http://localhost:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    email_backend: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "Li&Pass"
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 15
    smtp_max_retries: int = 2
    smtp_retry_delay_seconds: float = 1.0
    frontend_base_url: str = "http://localhost:5173"
    jwt_issuer: str = "http://localhost:8000"
    jwt_private_key_path: str = "jwt_private.pem"
    # 目录模式（可选）：从目录加载多把 *.pem 私钥，文件名即 kid；
    # JWT_ACTIVE_KID 指定签名 kid，缺省取字典序最大的文件名。空目录退回单文件模式。
    jwt_keys_dir: str = ""
    jwt_active_kid: str = ""
    oauth_access_token_ttl_minutes: int = 15
    oauth_id_token_ttl_minutes: int = 5
    oauth_code_ttl_minutes: int = 10
    logout_token_ttl_seconds: int = 120
    backchannel_logout_timeout_seconds: float = 5.0
    backchannel_logout_max_retries: int = 2
    pending_request_store: str = "memory"
    encryption_key_path: str = "encryption.key"
    twofa_store: str = "memory"
    rate_limiter: str = "memory"
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 900
    login_email_rate_limit: int = 10
    login_email_rate_window_seconds: int = 900
    login_ip_rate_limit: int = 20
    authorize_rate_limit: int = 120
    authorize_rate_window_seconds: int = 60
    token_rate_limit: int = 120
    token_rate_window_seconds: int = 60
    # 敏感操作 step-up 复核窗口与限流：
    # 一次密码复核成功后，该会话 STEPUP_WINDOW_MINUTES 分钟内免再次输入密码；
    # 0 = 关闭窗口（每次敏感操作都必须重新复核）。
    stepup_window_minutes: int = 30
    stepup_rate_limit: int = 5
    stepup_rate_window_seconds: int = 900
    stepup_email_rate_limit: int = 10
    stepup_email_rate_window_seconds: int = 900
    client_block_rate_limit: int = 100
    client_block_rate_window_seconds: int = 3600
    audit_retention_days: int = 180
    # 已吊销/已过期会话的保留天数：保留窗口用于近期排查，超期由后台维护任务删除。
    session_retention_days: int = 30
    otp_send_limit: int = 5
    otp_send_window_seconds: int = 3600
    otp_resend_cooldown_seconds: int = 60
    register_rate_limit: int = 10
    register_rate_window_seconds: int = 3600
    # 公开注册入口开关：关闭后普通注册返回 403，仅保留邀请注册渠道。
    public_registration_enabled: bool = True
    admin_invite_rate_limit: int = 100
    admin_invite_rate_window_seconds: int = 3600
    admin_notification_rate_limit: int = 20
    admin_notification_rate_window_seconds: int = 3600
    admin_session_revoke_rate_limit: int = 30
    admin_session_revoke_rate_window_seconds: int = 60
    notification_max_recipients: int = 500
    notification_retention_days: int = 180
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
    # ip2region 离线 IP 库：数据目录、更新源与调度（详见 ip2region_update 服务）
    ip2region_data_dir: str = "data/ip2region"
    ip2region_releases_api_url: str = (
        "https://api.github.com/repos/lionsoul2014/ip2region/releases/latest"
    )
    ip2region_download_base_url: str = (
        "https://raw.githubusercontent.com/lionsoul2014/ip2region"
    )
    ip2region_http_timeout_seconds: float = 30.0
    ip2region_auto_update_enabled: bool = False
    ip2region_update_interval_hours: int = 24
    ip2region_update_rate_limit: int = 6
    ip2region_update_rate_window_seconds: int = 3600

    @model_validator(mode="after")
    def _validate_production(self):
        if self.environment not in ("development", "production"):
            raise ValueError(
                "ENVIRONMENT 必须为 development 或 production，防止拼写错误导致生产校验被跳过"
            )
        if self.session_cookie_samesite not in ("lax", "strict", "none"):
            raise ValueError("SESSION_COOKIE_SAMESITE 必须为 lax、strict 或 none")
        if not 1 <= self.trusted_device_ttl_days <= 365:
            raise ValueError("TRUSTED_DEVICE_TTL_DAYS 必须在 1–365 之间")
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
        if self.ip2region_http_timeout_seconds < 5:
            raise ValueError("IP2REGION_HTTP_TIMEOUT_SECONDS 必须 ≥5")
        if not 30 <= self.logout_token_ttl_seconds <= 600:
            raise ValueError("LOGOUT_TOKEN_TTL_SECONDS 必须在 30–600 之间")
        if not 1 <= self.backchannel_logout_timeout_seconds <= 30:
            raise ValueError("BACKCHANNEL_LOGOUT_TIMEOUT_SECONDS 必须在 1–30 之间")
        if not 0 <= self.backchannel_logout_max_retries <= 5:
            raise ValueError("BACKCHANNEL_LOGOUT_MAX_RETRIES 必须在 0–5 之间")
        if not 1 <= self.ip2region_update_interval_hours <= 8760:
            raise ValueError("IP2REGION_UPDATE_INTERVAL_HOURS 必须在 1–8760 之间")
        if self.ip2region_update_rate_limit < 1:
            raise ValueError("IP2REGION_UPDATE_RATE_LIMIT 必须 ≥1")
        if self.ip2region_update_rate_window_seconds < 1:
            raise ValueError("IP2REGION_UPDATE_RATE_WINDOW_SECONDS 必须 ≥1")
        if self.stepup_window_minutes < 0:
            raise ValueError("STEPUP_WINDOW_MINUTES 必须 ≥0（0 表示关闭免复核窗口）")
        if self.stepup_rate_limit < 1:
            raise ValueError("STEPUP_RATE_LIMIT 必须 ≥1")
        if self.stepup_rate_window_seconds < 1:
            raise ValueError("STEPUP_RATE_WINDOW_SECONDS 必须 ≥1")
        if self.stepup_email_rate_limit < 1:
            raise ValueError("STEPUP_EMAIL_RATE_LIMIT 必须 ≥1")
        if self.stepup_email_rate_window_seconds < 1:
            raise ValueError("STEPUP_EMAIL_RATE_WINDOW_SECONDS 必须 ≥1")
        if not self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS 不能为空")
        if self.db_pool_size < 1 or self.db_max_overflow < 0:
            raise ValueError("DB_POOL_SIZE 必须 ≥1，DB_MAX_OVERFLOW 必须 ≥0")
        if (
            self.login_email_rate_limit < 1
            or self.login_email_rate_window_seconds < 1
            or self.client_block_rate_limit < 1
            or self.client_block_rate_window_seconds < 1
            or self.audit_retention_days < 1
            or self.session_retention_days < 1
            or self.authorize_rate_limit < 1
            or self.authorize_rate_window_seconds < 1
            or self.token_rate_limit < 1
            or self.token_rate_window_seconds < 1
        ):
            raise ValueError(
                "LOGIN_EMAIL_RATE_LIMIT/CLIENT_BLOCK_RATE_LIMIT/AUDIT_RETENTION_DAYS/"
                "SESSION_RETENTION_DAYS/AUTHORIZE_RATE_LIMIT/TOKEN_RATE_LIMIT "
                "等配置必须 ≥1"
            )
        if self.jwt_active_kid and not self.jwt_keys_dir:
            raise ValueError("JWT_ACTIVE_KID 必须与 JWT_KEYS_DIR 同时配置")
        if self.admin_invite_rate_limit < 1 or self.admin_invite_rate_window_seconds < 1:
            raise ValueError(
                "ADMIN_INVITE_RATE_LIMIT/ADMIN_INVITE_RATE_WINDOW_SECONDS 必须 ≥1"
            )
        if (
            self.admin_notification_rate_limit < 1
            or self.admin_notification_rate_window_seconds < 1
        ):
            raise ValueError(
                "ADMIN_NOTIFICATION_RATE_LIMIT/"
                "ADMIN_NOTIFICATION_RATE_WINDOW_SECONDS 必须 ≥1"
            )
        if (
            self.admin_session_revoke_rate_limit < 1
            or self.admin_session_revoke_rate_window_seconds < 1
        ):
            raise ValueError(
                "ADMIN_SESSION_REVOKE_RATE_LIMIT/"
                "ADMIN_SESSION_REVOKE_RATE_WINDOW_SECONDS 必须 ≥1"
            )
        if not 1 <= self.notification_max_recipients <= 10000:
            raise ValueError("NOTIFICATION_MAX_RECIPIENTS 必须在 1–10000 之间")
        if self.notification_retention_days < 1:
            raise ValueError("NOTIFICATION_RETENTION_DAYS 必须 ≥1")
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
        if self.jwt_keys_dir and not self.jwt_keys_dir.startswith("/"):
            raise ValueError(
                "JWT_KEYS_DIR 在生产环境必须使用绝对路径（推荐 /app/keys/jwt）"
            )
        if not self.ip2region_data_dir.startswith("/"):
            raise ValueError(
                "IP2REGION_DATA_DIR 在生产环境必须使用绝对路径（推荐 /app/data/ip2region）"
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
