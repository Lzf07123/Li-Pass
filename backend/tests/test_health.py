from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_checks_database(client) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_security_headers_include_permissions_policy(client) -> None:
    response = client.get("/healthz")
    assert (
        response.headers["permissions-policy"]
        == "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )


def test_untrusted_host_rejected(client) -> None:
    response = client.get("/healthz", headers={"host": "evil.example"})
    assert response.status_code == 400
