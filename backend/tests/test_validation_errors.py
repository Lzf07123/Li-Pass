def test_invalid_email_returns_chinese_message(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "password123", "nickname": "A"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "邮箱格式不正确"


def test_short_password_returns_chinese_message(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "123", "nickname": "A"},
    )
    assert response.status_code == 422
    assert "请求参数错误" in response.json()["detail"]


def test_weak_password_rejected(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "aaaaaaaa", "nickname": "A"},
    )
    assert response.status_code == 422
    assert "密码强度不足" in response.json()["detail"]
