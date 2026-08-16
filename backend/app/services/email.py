import logging
import socket
import smtplib
import time
from email.utils import formatdate, make_msgid
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.core.config import Settings, get_settings
from app.services.email_templates import (
    LOGO_BYTES,
    render_account_deleted,
    render_custom_notification,
    render_email_changed,
    render_invite,
    render_password_reset,
    render_verification,
)

logger = logging.getLogger(__name__)

TRANSIENT_SMTP_ERRORS = (
    smtplib.SMTPConnectError,
    smtplib.SMTPServerDisconnected,
    socket.timeout,
    TimeoutError,
    ConnectionError,
    OSError,
)


class EmailService(ABC):
    @abstractmethod
    def send_verification(self, to: str, code: str) -> None: ...

    @abstractmethod
    def send_password_reset(self, to: str, code: str) -> None: ...

    @abstractmethod
    def send_invite(self, to: str, link: str) -> None: ...

    @abstractmethod
    def send_account_deleted(self, to: str, nickname: str | None) -> None: ...

    @abstractmethod
    def send_email_changed(self, to: str, nickname: str | None) -> None: ...

    @abstractmethod
    def send_custom_notification(
        self, to: str, subject: str, body: str
    ) -> None: ...

    def send_invite_batch(
        self, items: list[tuple[str, str]]
    ) -> list[Exception | None]:
        """默认实现：逐封发送；SMTP 子类覆盖为复用单条连接。"""
        results: list[Exception | None] = []
        for to, link in items:
            try:
                self.send_invite(to, link)
                results.append(None)
            except Exception as exc:
                results.append(exc)
        return results

    def send_custom_notification_batch(
        self, items: list[tuple[str, str, str]]
    ) -> list[Exception | None]:
        """默认实现：逐封发送；SMTP 子类复用单条连接。"""
        results: list[Exception | None] = []
        for to, subject, body in items:
            try:
                self.send_custom_notification(to, subject, body)
                results.append(None)
            except Exception as exc:
                results.append(exc)
        return results


class ConsoleEmailService(EmailService):
    def _send(self, subject: str, to: str, code: str) -> None:
        print(f"[email:{get_settings().email_backend}] {subject} -> {to}: code={code}")

    def send_verification(self, to: str, code: str) -> None:
        self._send("verify your email", to, code)

    def send_password_reset(self, to: str, code: str) -> None:
        self._send("reset your password", to, code)

    def send_invite(self, to: str, link: str) -> None:
        print(f"[email:{get_settings().email_backend}] invite -> {to}: {link}")

    def send_account_deleted(self, to: str, nickname: str | None) -> None:
        print(f"[email:{get_settings().email_backend}] account deleted -> {to}")

    def send_email_changed(self, to: str, nickname: str | None) -> None:
        print(f"[email:{get_settings().email_backend}] email changed -> {to}")

    def send_custom_notification(self, to: str, subject: str, body: str) -> None:
        print(
            f"[email:{get_settings().email_backend}] custom notification -> "
            f"{to}: {subject}\n{body}"
        )


class SMTPEmailService(EmailService):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        from_name: str,
        use_tls: bool,
        timeout: int = 15,
        max_retries: int = 2,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        # SMTP_FROM 允许只填显示名：缺失邮箱地址时回退为认证邮箱，
        # 避免 From 头变成 "LiPass <LiPass>" 这种无效地址。
        if "@" not in from_addr and username and "@" in username:
            from_addr = username
        if "@" not in from_addr:
            raise ValueError(
                "SMTP_FROM 必须配置为邮箱地址，例如 noreply@example.com"
            )
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.from_name = from_name
        self.use_tls = use_tls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def _build_message(
        self, to: str, subject: str, body: str, html_body: str
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_addr}>"
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        domain = self.from_addr.split("@")[-1] if "@" in self.from_addr else "localhost"
        message["Message-ID"] = make_msgid(domain=domain)
        # multipart/alternative（纯文本 + HTML）；Logo 以 CID 内嵌在 HTML
        # 子部分里（multipart/related），不依赖外网图片加载。
        message.set_content(body)
        message.add_alternative(html_body, subtype="html")
        for part in message.iter_parts():
            if part.get_content_type() == "text/html":
                part.add_related(
                    LOGO_BYTES,
                    maintype="image",
                    subtype="png",
                    cid="brand-logo",
                )
                break
        return message

    def _connect(self) -> smtplib.SMTP:
        # 465 为隐式 SSL（SMTP_SSL），587/25 为明文 + STARTTLS。
        # 混用会导致 465 端口握手失败（服务端等待 TLS 而客户端发纯文本）。
        if self.port == 465:
            return smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
        server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        if self.use_tls:
            server.starttls()
        return server

    def _send(self, to: str, subject: str, body: str, html_body: str) -> None:
        message = self._build_message(to, subject, body, html_body)
        with self._connect() as server:
            if self.username:
                server.login(self.username, self.password)
            server.send_message(message)

    def _send_with_retry(
        self, to: str, subject: str, body: str, html_body: str
    ) -> None:
        last_error: Exception | None = None
        total_attempts = 1 + self.max_retries
        for attempt in range(1, total_attempts + 1):
            started = time.perf_counter()
            try:
                self._send(to, subject, body, html_body)
                logger.info(
                    "邮件发送成功 to=%s subject=%s duration=%.2fs",
                    to,
                    subject,
                    time.perf_counter() - started,
                )
                return
            except (smtplib.SMTPAuthenticationError, smtplib.SMTPResponseException):
                logger.exception("邮件发送失败（SMTP 拒绝） to=%s subject=%s", to, subject)
                raise
            except TRANSIENT_SMTP_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "邮件发送临时失败 to=%s attempt=%d/%d error=%s",
                    to,
                    attempt,
                    total_attempts,
                    exc,
                )
                if attempt < total_attempts:
                    time.sleep(self.retry_delay_seconds)
            except Exception:
                logger.exception("邮件发送失败 to=%s subject=%s", to, subject)
                raise
        logger.error(
            "邮件发送最终失败 to=%s subject=%s error=%s",
            to,
            subject,
            last_error,
        )
        raise last_error or RuntimeError("SMTP 发送失败")

    def send_verification(self, to: str, code: str) -> None:
        self._send_with_retry(
            to,
            "Li&Pass 邮箱验证码",
            f"你的验证码是 {code}，10 分钟内有效。",
            render_verification(code),
        )

    def send_password_reset(self, to: str, code: str) -> None:
        self._send_with_retry(
            to,
            "Li&Pass 重置密码",
            f"你的重置验证码是 {code}，10 分钟内有效。",
            render_password_reset(code),
        )

    def send_invite(self, to: str, link: str) -> None:
        self._send_with_retry(
            to,
            "Li&Pass 账号邀请",
            self._invite_body(link),
            render_invite(link),
        )

    @staticmethod
    def _invite_body(link: str) -> str:
        return (
            "你被邀请注册 Li&Pass 账号，"
            f"请点击以下链接完成注册（7 天内有效）：\n{link}"
        )

    def _build_invite_message(self, to: str, link: str) -> EmailMessage:
        return self._build_message(
            to,
            "Li&Pass 账号邀请",
            self._invite_body(link),
            render_invite(link),
        )

    def send_invite_batch(
        self, items: list[tuple[str, str]]
    ) -> list[Exception | None]:
        """复用一条 SMTP 连接发送整批邀请，避免逐封建连。"""
        if not items:
            return []
        results: list[Exception | None] = []
        try:
            server = self._connect()
        except Exception as exc:
            return [exc for _ in items]
        try:
            if self.username:
                server.login(self.username, self.password)
            for to, link in items:
                try:
                    server.send_message(self._build_invite_message(to, link))
                    results.append(None)
                except TRANSIENT_SMTP_ERRORS:
                    # 连接可能已失效：关闭后重建，并重试当前这封。
                    try:
                        server.close()
                    except Exception:
                        pass
                    try:
                        server = self._connect()
                        if self.username:
                            server.login(self.username, self.password)
                        server.send_message(self._build_invite_message(to, link))
                        results.append(None)
                    except Exception as exc:
                        results.append(exc)
                except Exception as exc:
                    results.append(exc)
        except Exception as exc:
            return [exc for _ in items]
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return results

    def send_account_deleted(self, to: str, nickname: str | None) -> None:
        greeting = f"您好，{nickname}：" if nickname else "您好："
        body = (
            f"{greeting}\n\n"
            f"您的 {get_settings().app_name} 账号（{to}）已被删除，您将无法再使用该账号"
            "登录相关网站。\n"
            "如非您本人操作或对此有疑问，请联系平台管理员。\n\n"
            "此邮件由系统自动发送，请勿直接回复。"
        )
        self._send_with_retry(
            to,
            f"您的 {get_settings().app_name} 账号已删除",
            body,
            render_account_deleted(to, nickname),
        )

    def send_email_changed(self, to: str, nickname: str | None) -> None:
        self._send_with_retry(
            to,
            f"您的 {get_settings().app_name} 账号登录邮箱已更换",
            "您的账号登录邮箱已被更换，今后请使用新邮箱登录。"
            "如非本人操作，请立即找回密码或联系平台管理员。",
            render_email_changed(nickname),
        )

    def send_custom_notification(self, to: str, subject: str, body: str) -> None:
        self._send_with_retry(
            to,
            subject,
            body,
            render_custom_notification(
                subject, body, get_settings().frontend_base_url
            ),
        )

    def send_custom_notification_batch(
        self, items: list[tuple[str, str, str]]
    ) -> list[Exception | None]:
        """复用一条 SMTP 连接发送整批自定义通知。"""
        if not items:
            return []
        results: list[Exception | None] = []
        try:
            server = self._connect()
        except Exception as exc:
            return [exc for _ in items]
        try:
            if self.username:
                server.login(self.username, self.password)
            for to, subject, body in items:
                try:
                    server.send_message(
                        self._build_message(
                            to,
                            subject,
                            body,
                            render_custom_notification(
                                subject, body, get_settings().frontend_base_url
                            ),
                        )
                    )
                    results.append(None)
                except TRANSIENT_SMTP_ERRORS:
                    try:
                        server.close()
                    except Exception:
                        pass
                    try:
                        server = self._connect()
                        if self.username:
                            server.login(self.username, self.password)
                        server.send_message(
                            self._build_message(
                                to,
                                subject,
                                body,
                                render_custom_notification(
                                    subject,
                                    body,
                                    get_settings().frontend_base_url,
                                ),
                            )
                        )
                        results.append(None)
                    except Exception as exc:
                        results.append(exc)
                except Exception as exc:
                    results.append(exc)
        except Exception as exc:
            return [exc for _ in items]
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return results


def get_email_service() -> EmailService:
    settings = get_settings()
    if settings.email_backend == "console":
        return ConsoleEmailService()
    if settings.email_backend == "smtp":
        if not settings.smtp_host or not settings.smtp_from:
            raise ValueError("SMTP 未配置：请设置 SMTP_HOST 与 SMTP_FROM")
        return SMTPEmailService(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_addr=settings.smtp_from,
            from_name=settings.smtp_from_name,
            use_tls=settings.smtp_use_tls,
            timeout=settings.smtp_timeout_seconds,
            max_retries=settings.smtp_max_retries,
            retry_delay_seconds=settings.smtp_retry_delay_seconds,
        )
    raise ValueError(f"Unsupported email backend: {settings.email_backend}")


def warn_email_config(settings: Settings) -> None:
    """启动时提醒会影响邮件可用性的配置问题。"""
    if settings.email_backend != "smtp":
        return
    if (
        "localhost" in settings.frontend_base_url
        or "127.0.0.1" in settings.frontend_base_url
    ):
        logger.warning(
            "SMTP 已启用但 FRONTEND_BASE_URL=%s 指向本机，"
            "邀请邮件中的链接将无法被外部访问，请配置真实对外地址",
            settings.frontend_base_url,
        )
