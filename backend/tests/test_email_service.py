from app.services.email import ConsoleEmailService, SMTPEmailService, get_email_service


def test_console_backend_by_default() -> None:
    assert isinstance(get_email_service(), ConsoleEmailService)


def test_smtp_message_builds_with_from_and_code() -> None:
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        from_addr="noreply@example.com",
        from_name="Portal OSS",
        use_tls=True,
    )
    message = service._build_message(
        "a@example.com", "邮箱验证码", "你的验证码是 123456，10 分钟内有效"
    )
    assert "noreply@example.com" in message["From"]
    assert "Portal OSS" in message["From"]
    assert message["To"] == "a@example.com"
    assert "123456" in message.get_body().get_content()
