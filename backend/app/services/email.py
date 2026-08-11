from abc import ABC, abstractmethod

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


def get_email_service() -> EmailService:
    if get_settings().email_backend == "console":
        return ConsoleEmailService()
    raise ValueError(f"Unsupported email backend: {get_settings().email_backend}")
