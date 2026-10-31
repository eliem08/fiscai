"""Tests for IdempotencyMiddleware on mutating HTTP routes.

Enforces:
- Required Idempotency-Key on every mutating route (returns 400 if missing)
- Replay: same key and identical body returns cached response
- Body mismatch: same key with different body returns 422 Unprocessable Entity
- Concurrency: concurrent in-flight request returns 409 Conflict
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi.testclient import TestClient
import psycopg
import pytest

from apps.api.main import app
from apps.api.middleware import get_idempotency_store
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture(autouse=True)
def clean_idempotency_store():
    store = get_idempotency_store()
    store.clear()
    yield
    store.clear()


def test_missing_idempotency_key_returns_400(db_conn: psycopg.Connection):
    """Mutating request without Idempotency-Key returns 400 Bad Request Problem Details."""
    t_id = seed_tenant(db_conn, "Cabinet Idempotency Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    # POST without Idempotency-Key header
    res = client.post(
        "/v1/client-entities",
        headers={"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id)},
        json={"legal_name": "Entreprise Sans Cle"},
    )
    assert res.status_code == 400, res.text
    problem = res.json()
    assert problem["status"] == 400
    assert "idempotency-key" in problem["detail"].lower()


def test_idempotent_replay_returns_cached_response(db_conn: psycopg.Connection):
    """Replaying request with same key and same body returns identical cached response."""
    t_id = seed_tenant(db_conn, "Cabinet Replay Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    idem_key = str(uuid.uuid4())
    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(t_id),
        "Idempotency-Key": idem_key,
    }
    payload = {"legal_name": "Societe Replay SARL"}

    # 1. First execution
    res1 = client.post("/v1/client-entities", headers=headers, json=payload)
    assert res1.status_code == 201, res1.text
    data1 = res1.json()

    # 2. Replay with identical key and payload
    res2 = client.post("/v1/client-entities", headers=headers, json=payload)
    assert res2.status_code == 201, res2.text
    data2 = res2.json()

    assert data1["id"] == data2["id"]
    assert data1["legal_name"] == data2["legal_name"]
    assert res2.headers.get("Idempotency-Replay") == "true"


def test_same_key_different_body_returns_422(db_conn: psycopg.Connection):
    """Reusing same idempotency key with a different request payload returns 422."""
    t_id = seed_tenant(db_conn, "Cabinet Mismatch Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    idem_key = str(uuid.uuid4())
    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(t_id),
        "Idempotency-Key": idem_key,
    }

    # 1. First request
    res1 = client.post("/v1/client-entities", headers=headers, json={"legal_name": "Nom Original"})
    assert res1.status_code == 201

    # 2. Second request with different body but same key -> 422
    res2 = client.post("/v1/client-entities", headers=headers, json={"legal_name": "Nom Modifie"})
    assert res2.status_code == 422
    problem = res2.json()
    assert "différent" in problem["detail"].lower() or "mismatch" in problem.get("title", "").lower()


def test_concurrent_in_flight_returns_409(db_conn: psycopg.Connection):
    """Concurrent request with an in-flight key returns 409 Conflict Problem Details."""
    t_id = seed_tenant(db_conn, "Cabinet In-Flight Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    idem_key = str(uuid.uuid4())

    # Pre-register an in-flight key in the store
    payload_bytes = b'{"legal_name":"Concurrent Corp"}'
    req_hash = hashlib.sha256(b"POST:/v1/client-entities:" + payload_bytes).hexdigest()
    store = get_idempotency_store()
    started, _ = store.start(idem_key, req_hash)
    assert started is True

    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(t_id),
        "Idempotency-Key": idem_key,
        "Content-Type": "application/json",
    }

    # Attempt to send request while key is marked in_flight -> 409
    res = client.post("/v1/client-entities", headers=headers, content=payload_bytes)
    assert res.status_code == 409
    problem = res.json()
    assert "en cours" in problem["detail"].lower() or "concurrent" in problem.get("title", "").lower()


def test_non_mutating_get_does_not_require_idempotency_key(db_conn: psycopg.Connection):
    """GET requests do not require Idempotency-Key."""
    t_id = seed_tenant(db_conn, "Cabinet Non-Mutating")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    res = client.get(
        "/v1/client-entities",
        headers={"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id)},
    )
    assert res.status_code == 200
