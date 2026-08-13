import os

from tests.helpers import register_and_login


def test_upload_avatar_and_static_serving(client, captured_email) -> None:
    register_and_login(client, captured_email)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 256
    response = client.post(
        "/api/v1/me/avatar",
        files={"file": ("avatar.png", png, "image/png")},
    )
    assert response.status_code == 200
    avatar_url = response.json()["avatar_url"]
    assert avatar_url.startswith("/uploads/avatars/")

    static = client.get(avatar_url)
    assert static.status_code == 200
    assert static.content == png


def test_upload_avatar_rejects_non_image(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/me/avatar",
        files={"file": ("evil.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_avatar_rejects_oversize(client, captured_email, monkeypatch) -> None:
    register_and_login(client, captured_email)
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)
    response = client.post(
        "/api/v1/me/avatar",
        files={"file": ("avatar.png", big, "image/png")},
    )
    assert response.status_code == 413
