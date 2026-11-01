"""Tests for Rate Limiting and Security Headers Middleware per Phase 5b requirements."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.middleware import get_rate_limit_store


def test_security_headers_present_on_all_responses():
    """All API responses must include strict CSP, HSTS, and frame protection headers."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in headers
    assert "Referrer-Policy" in headers
    assert "Permissions-Policy" in headers


def test_rate_limiting_enforced_on_auth_endpoint():
    """Repeated rapid calls to auth endpoints exceed threshold and return 429 Too Many Requests."""
    import uuid
    from apps.api.deps import get_current_session
    from avenel.tenancy.auth import UserSession

    store = get_rate_limit_store()
    store.reset()

    dummy_session = UserSession(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        membership_id=uuid.uuid4(),
        role="accountant",
        email="test@example.com",
        full_name="Test User",
        client_scope_ids=[],
        auth_time=1234567890,
    )
    app.dependency_overrides[get_current_session] = lambda: dummy_session

    try:
        client = TestClient(app)

        # 1. First 30 calls succeed (200 OK)
        for i in range(30):
            resp = client.get("/v1/me", headers={"X-Forwarded-For": "198.51.100.42"})
            assert resp.status_code == 200
            assert "X-RateLimit-Limit" in resp.headers
            assert resp.headers["X-RateLimit-Remaining"] == str(30 - (i + 1))

        # 2. 31st call violates rate limit -> HTTP 429
        resp_blocked = client.get("/v1/me", headers={"X-Forwarded-For": "198.51.100.42"})
        assert resp_blocked.status_code == 429
        assert resp_blocked.headers.get("Retry-After") is not None
        assert resp_blocked.headers.get("X-RateLimit-Remaining") == "0"

        body = resp_blocked.json()
        assert body["type"] == "https://avenel.ma/errors/rate-limit-exceeded"
        assert body["status"] == 429
        assert "Limite de requêtes atteinte" in body["detail"]

        # 3. Call from different IP succeeds without being throttled
        resp_other = client.get("/v1/me", headers={"X-Forwarded-For": "203.0.113.88"})
        assert resp_other.status_code == 200
        assert resp_other.headers["X-RateLimit-Remaining"] == "29"

    finally:
        app.dependency_overrides.pop(get_current_session, None)
        store.reset()

