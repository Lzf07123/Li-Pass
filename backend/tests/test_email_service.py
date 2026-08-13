from app.services.email import ConsoleEmailService, SMTPEmailService, get_email_service
import pytest


def test_console_backend_by_default() -> None:
    assert isinstance(get_email_service(), ConsoleEmailService)


def test_smtp_message_builds_with_from_and_code() -> None:
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        from_addr="noreply@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    message = service._build_message(
        "a@example.com", "邮箱验证码", "你的验证码是 123456，10 分钟内有效"
    )
    assert "noreply@example.com" in message["From"]
    assert "LinPass SSO" in message["From"]
    assert message["To"] == "a@example.com"
    assert "123456" in message.get_body().get_content()


def test_smtp_from_falls_back_to_username() -> None:
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="pass",
        from_addr="LinPass",
        from_name="LinPass SSO",
        use_tls=True,
    )
    message = service._build_message("a@example.com", "s", "b")
    assert "user@example.com" in message["From"]


def test_smtp_from_requires_email_address() -> None:
    with pytest.raises(ValueError):
        SMTPEmailService(
            host="smtp.example.com",
            port=587,
            username="user",
            password="pass",
            from_addr="LinPass",
            from_name="LinPass SSO",
            use_tls=True,
        )


def test_smtp_port_465_uses_implicit_ssl(monkeypatch) -> None:
    calls: list[tuple] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            calls.append(("plain", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            raise AssertionError("465 不应走 STARTTLS")

        def login(self, username, password):
            pass

        def send_message(self, message):
            pass

    class FakeSMTPSSL(FakeSMTP):
        def __init__(self, host, port, timeout=None):
            calls.append(("ssl", host, port, timeout))

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTPSSL)

    service = SMTPEmailService(
        host="smtp.qiye.aliyun.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    service.send_verification("a@example.com", "123456")
    assert calls == [("ssl", "smtp.qiye.aliyun.com", 465, 15)]


def test_smtp_port_587_uses_starttls(monkeypatch) -> None:
    started_tls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            started_tls.append(True)

        def login(self, username, password):
            pass

        def send_message(self, message):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)

    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    service.send_password_reset("a@example.com", "123456")
    assert started_tls == [True]


def test_smtp_account_deleted_message_is_polite(monkeypatch) -> None:
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="pass",
        from_addr="noreply@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    captured: dict[str, str] = {}

    def fake_send(to: str, subject: str, body: str) -> None:
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body

    monkeypatch.setattr(service, "_send", fake_send)
    service.send_account_deleted("a@example.com", "Alice")

    assert captured["to"] == "a@example.com"
    assert "账号已删除" in captured["subject"]
    assert "您好，Alice" in captured["body"]
    assert "a@example.com" in captured["body"]
    assert "请联系平台管理员" in captured["body"]
