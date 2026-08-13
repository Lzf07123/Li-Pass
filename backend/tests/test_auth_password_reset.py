def test_password_reset_flow(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )

    response = client.post(
        "/api/v1/auth/password/reset", json={"email": "a@example.com"}
    )
    assert response.status_code == 202
    code = captured_email.messages[-1][2]

    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"email": "a@example.com", "code": code, "new_password": "newpassword456"},
    )
    assert response.status_code == 200

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "newpassword456"},
    )
    assert response.status_code == 200


def test_password_reset_bad_code(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"email": "a@example.com", "code": "000000", "new_password": "newpassword456"},
    )
    assert response.status_code == 400


def test_password_reset_confirm_locked_after_too_many_wrong(
    client, captured_email
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    client.post(
        "/api/v1/auth/password/reset",
        json={"email": "a@example.com"},
    )
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/password/reset/confirm",
                json={
                    "email": "a@example.com",
                    "code": "000000",
                    "new_password": "newpassword456",
                },
            ).status_code
            == 400
        )
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={
            "email": "a@example.com",
            "code": "000000",
            "new_password": "newpassword456",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "验证码错误次数过多，请重新发送验证码"


def test_password_reset_rate_limit_keyed_by_email_not_ip(
    client, captured_email, monkeypatch
) -> None:
    from app.services.rate_limit import MemoryRateLimiter

    limiter = MemoryRateLimiter()
    original_hit = limiter.hit
    keys: list[tuple[str, str]] = []

    def hit(scope, key, window_seconds, increment=1):
        keys.append((scope, key))
        return original_hit(scope, key, window_seconds, increment)

    monkeypatch.setattr(limiter, "hit", hit)
    monkeypatch.setattr("app.api.routes.auth.get_rate_limiter", lambda: limiter)
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    assert (
        client.post(
            "/api/v1/auth/password/reset",
            json={"email": "a@example.com"},
        ).status_code
        == 202
    )
    reset_keys = [key for scope, key in keys if scope == "password_reset"]
    assert reset_keys == ["a@example.com"]
    assert all(":" not in key for key in reset_keys)
