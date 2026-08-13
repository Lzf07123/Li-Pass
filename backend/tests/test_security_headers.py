def test_security_headers(client) -> None:
    response = client.get("/healthz")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_uploads_not_no_store(client) -> None:
    # 公开头像等静态资源不应带 no-store，允许网关/CDN 长缓存。
    response = client.get("/uploads/avatars/does-not-exist.png")
    assert response.status_code == 404
    assert "cache-control" not in response.headers
