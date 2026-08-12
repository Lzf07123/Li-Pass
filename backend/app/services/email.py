import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.core.config import get_settings


class EmailService(ABC):
    @abstractmethod
    def send_verification(self, to: str, code: str) -> None: ...

    @abstractmethod
    def send_password_reset(self, to: str, code: str) -> None: ...

    @abstractmethod
    def send_invite(self, to: str, link: str) -> None: ...

    @abstractmethod
    def send_account_deleted(self, to: str, nickname: str | None) -> None: ...


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
    ) -> None:
        # SMTP_FROM 允许只填显示名：缺失邮箱地址时回退为认证邮箱，
        # 避免 From 头变成 "LinPass <LinPass>" 这种无效地址。
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

    def _build_message(self, to: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_addr}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        return message

    def _connect(self) -> smtplib.SMTP:
        # 465 为隐式 SSL（SMTP_SSL），587/25 为明文 + STARTTLS。
        # 混用会导致 465 端口握手失败（服务端等待 TLS 而客户端发纯文本）。
        if self.port == 465:
            return smtplib.SMTP_SSL(self.host, self.port, timeout=15)
        server = smtplib.SMTP(self.host, self.port, timeout=15)
        if self.use_tls:
            server.starttls()
        return server

    def _send(self, to: str, subject: str, body: str) -> None:
        message = self._build_message(to, subject, body)
        with self._connect() as server:
            if self.username:
                server.login(self.username, self.password)
            server.send_message(message)

    def send_verification(self, to: str, code: str) -> None:
        self._send(to, "LinPass SSO 邮箱验证码", f"你的验证码是 {code}，10 分钟内有效。")

    def send_password_reset(self, to: str, code: str) -> None:
        self._send(to, "LinPass SSO 重置密码", f"你的重置验证码是 {code}，10 分钟内有效。")

    def send_invite(self, to: str, link: str) -> None:
        self._send(
            to,
            "LinPass SSO 账号邀请",
            f"你被邀请注册 LinPass SSO 账号，请点击以下链接完成注册（7 天内有效）：\n{link}",
        )

    def send_account_deleted(self, to: str, nickname: str | None) -> None:
        greeting = f"您好，{nickname}：" if nickname else "您好："
        body = (
            f"{greeting}\n\n"
            f"您的 {get_settings().app_name} 账号（{to}）已被删除，您将无法再使用该账号"
            "登录相关网站。\n"
            "如非您本人操作或对此有疑问，请联系平台管理员。\n\n"
            "此邮件由系统自动发送，请勿直接回复。"
        )
        self._send(
            to,
            f"您的 {get_settings().app_name} 账号已删除",
            body,
        )


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
        )
    raise ValueError(f"Unsupported email backend: {settings.email_backend}")
