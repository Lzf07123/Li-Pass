import logging
import smtplib

from app.services.email import (
    ConsoleEmailService,
    SMTPEmailService,
    get_email_service,
    warn_email_config,
)
from app.services.email_templates import (
    render_custom_notification,
    render_invite,
    render_verification,
)
import pytest


def _part_content(message, content_type: str) -> str:
    for part in message.walk():
        if part.get_content_type() == content_type:
            return part.get_content()
    raise AssertionError(f"缺少 {content_type} 部分")


def test_console_backend_by_default() -> None:
    assert isinstance(get_email_service(), ConsoleEmailService)


def test_warn_email_config_logs_localhost_warning(caplog) -> None:
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        email_backend="smtp",
        frontend_base_url="http://localhost",
    )
    with caplog.at_level(logging.WARNING, logger="app.services.email"):
        warn_email_config(settings)
    assert "localhost" in caplog.text


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
        "a@example.com",
        "邮箱验证码",
        "你的验证码是 123456，10 分钟内有效",
        "<html><body>123456</body></html>",
    )
    assert "noreply@example.com" in message["From"]
    assert "LinPass SSO" in message["From"]
    assert message["To"] == "a@example.com"
    assert "123456" in _part_content(message, "text/plain")


def test_smtp_message_has_date_and_message_id() -> None:
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="noreply@example.com",
        password="pass",
        from_addr="noreply@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    message = service._build_message(
        "a@example.com",
        "邮箱验证码",
        "你的验证码是 123456",
        "<html><body>123456</body></html>",
    )
    assert message["Date"] is not None
    assert message["Message-ID"] is not None
    assert "example.com" in message["Message-ID"]


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
    message = service._build_message(
        "a@example.com", "s", "b", "<html><body>b</body></html>"
    )
    assert "user@example.com" in message["From"]


def test_verification_message_has_branded_html_alternative() -> None:
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
        "a@example.com",
        "LinPass SSO 邮箱验证码",
        "你的验证码是 123456，10 分钟内有效。",
        render_verification("123456"),
    )
    assert message.is_multipart()
    html_text = _part_content(message, "text/html")
    assert "123456" in _part_content(message, "text/plain")
    assert "123456" in html_text
    assert "#0369A1" in html_text
    assert "LinPass SSO" in html_text
    assert "验证你的邮箱" in html_text
    assert "prefers-color-scheme" in html_text


def test_message_embeds_brand_logo_as_cid() -> None:
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
        "a@example.com",
        "LinPass SSO 账号邀请",
        "邀请正文",
        render_invite("https://portal.example.com/invite?token=abc"),
    )
    image_parts = [
        part
        for part in message.walk()
        if part.get_content_maintype() == "image"
    ]
    assert len(image_parts) == 1
    assert image_parts[0]["Content-ID"] == "brand-logo"
    assert image_parts[0].get_content_subtype() == "png"
    assert "cid:brand-logo" in _part_content(message, "text/html")


def test_invite_html_contains_branded_button() -> None:
    html_text = render_invite("https://portal.example.com/invite?token=abc")
    assert 'href="https://portal.example.com/invite?token=abc"' in html_text
    assert "完成注册" in html_text
    assert "#0369A1" in html_text


def test_custom_notification_escapes_and_preserves_breaks() -> None:
    html_text = render_custom_notification(
        "标题 <script>",
        "第一行\n<b>第二行</b>",
        "https://portal.example.com",
    )
    assert "&lt;script&gt;" in html_text
    assert "<script>" not in html_text
    assert "&lt;b&gt;第二行&lt;/b&gt;" in html_text
    assert "white-space:pre-line" in html_text
    assert "第一行\n&lt;b&gt;第二行&lt;/b&gt;" in html_text
    assert "前往用户中心关闭" in html_text
    assert "https://portal.example.com" in html_text


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


def test_smtp_custom_notification_sends_rendered_body(monkeypatch) -> None:
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            sent.append(
                (
                    "message",
                    message["Subject"],
                    _part_content(message, "text/plain").strip(),
                )
            )

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        from_addr="noreply@example.com",
        from_name="Portal",
        use_tls=False,
    )
    service.send_custom_notification(
        "bob@example.com", "维护通知", "您好，Bob：今晚维护"
    )
    assert ("message", "维护通知", "您好，Bob：今晚维护") in sent


def test_smtp_custom_notification_batch_reuses_connection(monkeypatch) -> None:
    connects = {"n": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            connects["n"] += 1

        def login(self, username, password):
            pass

        def send_message(self, message):
            pass

        def close(self):
            pass

        def quit(self):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        from_addr="noreply@example.com",
        from_name="Portal",
        use_tls=False,
    )
    results = service.send_custom_notification_batch(
        [("a@example.com", "s", "b"), ("b@example.com", "s", "b")]
    )
    assert results == [None, None]
    assert connects["n"] == 1


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


def test_smtp_retries_transient_failure_then_succeeds(monkeypatch) -> None:
    attempts = {"n": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise smtplib.SMTPServerDisconnected("transient")

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
        max_retries=2,
        retry_delay_seconds=0,
    )
    service.send_verification("a@example.com", "123456")
    assert attempts["n"] == 3


def test_smtp_raises_after_exhausting_retries(monkeypatch) -> None:
    attempts = {"n": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            attempts["n"] += 1
            raise smtplib.SMTPServerDisconnected("transient")

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
        max_retries=2,
        retry_delay_seconds=0,
    )
    with pytest.raises(smtplib.SMTPServerDisconnected):
        service.send_verification("a@example.com", "123456")
    assert attempts["n"] == 3


def test_smtp_does_not_retry_authentication_error(monkeypatch) -> None:
    attempts = {"n": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            attempts["n"] += 1
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

        def send_message(self, message):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
        max_retries=2,
        retry_delay_seconds=0,
    )
    with pytest.raises(smtplib.SMTPAuthenticationError):
        service.send_verification("a@example.com", "123456")
    assert attempts["n"] == 1


def test_smtp_logs_success(monkeypatch, caplog) -> None:
    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    with caplog.at_level(logging.INFO, logger="app.services.email"):
        service.send_verification("a@example.com", "123456")
    assert "邮件发送成功" in caplog.text


def test_smtp_send_invite_batch_reuses_connection(monkeypatch) -> None:
    state = {"connections": 0, "messages": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            state["connections"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            state["messages"] += 1

        def close(self):
            pass

        def quit(self):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    results = service.send_invite_batch(
        [
            ("a@example.com", "http://localhost/invite?token=a"),
            ("b@example.com", "http://localhost/invite?token=b"),
        ]
    )
    assert results == [None, None]
    assert state["connections"] == 1
    assert state["messages"] == 2


def test_smtp_send_invite_batch_isolates_failure(monkeypatch) -> None:
    state = {"n": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            state["n"] += 1
            if state["n"] == 2:
                raise RuntimeError("boom")

        def close(self):
            pass

        def quit(self):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=465,
        username="user@example.com",
        password="pass",
        from_addr="user@example.com",
        from_name="LinPass SSO",
        use_tls=True,
    )
    results = service.send_invite_batch(
        [
            ("a@example.com", "http://localhost/invite?token=a"),
            ("b@example.com", "http://localhost/invite?token=b"),
            ("c@example.com", "http://localhost/invite?token=c"),
        ]
    )
    assert results[0] is None
    assert isinstance(results[1], RuntimeError)
    assert results[2] is None
    assert state["n"] == 3


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

    def fake_send(to: str, subject: str, body: str, html_body: str) -> None:
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
