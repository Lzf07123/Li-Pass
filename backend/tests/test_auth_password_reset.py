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
