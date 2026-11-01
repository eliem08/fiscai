"""Tests for review effort tracking and internal operational metrics per Phase 5b Item 1."""

from __future__ import annotations

import uuid
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.deps import get_db, get_current_session
from avenel.tenancy.auth import UserSession


@pytest.fixture
def mock_session_owner() -> UserSession:
    return UserSession(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role="owner",
        email="owner@fiduciaire-atlas.ma",
        full_name="Fatima Zahra (Associée)",
        client_scope_ids=None,
    )


@pytest.fixture
def mock_session_operator() -> UserSession:
    return UserSession(
        user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role="operator",
        email="ops@avenel.ma",
        full_name="Avenel Ops Support",
        client_scope_ids=None,
    )


@pytest.fixture
def mock_session_staff() -> UserSession:
    return UserSession(
        user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role="staff",
        email="assistant@fiduciaire-atlas.ma",
        full_name="Youssef Bennani (Collaborateur)",
        client_scope_ids=None,
    )


def test_internal_metrics_rbac_owner_and_operator_allowed(mock_session_owner, mock_session_operator, mock_session_staff):
    """Owner and operator are permitted to access internal metrics; staff is denied with 403."""
    
    # 1. Staff is rejected with 403
    app.dependency_overrides[get_current_session] = lambda: mock_session_staff
    client = TestClient(app)
    resp = client.get("/v1/metrics/internal")
    assert resp.status_code == 403
    assert "Accès réservé" in resp.json()["detail"]

    # 2. Owner is allowed
    # (Mock DB connection for internal query)
    class FakeCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, *args, **kwargs):
            pass
        def fetchall(self):
            return []
        def fetchone(self):
            return (0.0, 0, 0, 0)

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        def commit(self):
            pass

    app.dependency_overrides[get_current_session] = lambda: mock_session_owner
    app.dependency_overrides[get_db] = lambda: FakeConn()
    resp = client.get("/v1/metrics/internal")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "total_active_review_seconds" in data["summary"]

    # 3. Operator is allowed
    app.dependency_overrides[get_current_session] = lambda: mock_session_operator
    resp = client.get("/v1/metrics/internal")
    assert resp.status_code == 200

    app.dependency_overrides.clear()
