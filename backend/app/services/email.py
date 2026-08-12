import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.core.config import get_settings


class EmailService(ABC):
    @abstractmethod
    def send_verification(self, to: str, code: str) -> None: ...

    @abstractmethod
    def send_password_reset(self, to: str, code: str) -> None: ...


class ConsoleEmailService(EmailService):
    def _send(self, subject: str, to: str, code: str) -> None:
        print(f"[email:{get_settings().email_backend}] {subject} -> {to}: code={code}")

    def send_verification(self, to: str, code: str) -> None:
        self._send("verify your email", to, code)

    def send_password_reset(self, to: str, code: str) -> None:
        self._send("reset your password", to, code)


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

    def _send(self, to: str, subject: str, body: str) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(self._build_message(to, subject, body))

    def send_verification(self, to: str, code: str) -> None:
        self._send(to, "Portal OSS 邮箱验证码", f"你的验证码是 {code}，10 分钟内有效。")

    def send_password_reset(self, to: str, code: str) -> None:
        self._send(to, "Portal OSS 重置密码", f"你的重置验证码是 {code}，10 分钟内有效。")


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
