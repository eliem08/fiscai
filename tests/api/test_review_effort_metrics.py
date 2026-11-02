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
        membership_id=uuid.UUID("99999999-1111-1111-1111-111111111111"),
        role="owner",
        email="owner@fiduciaire-atlas.ma",
        full_name="Fatima Zahra (Associée)",
        client_scope_ids=[],
    )


@pytest.fixture
def mock_session_operator() -> UserSession:
    return UserSession(
        user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        membership_id=uuid.UUID("99999999-2222-2222-2222-222222222222"),
        role="operator",
        email="ops@avenel.ma",
        full_name="Avenel Ops Support",
        client_scope_ids=[],
    )


@pytest.fixture
def mock_session_staff() -> UserSession:
    return UserSession(
        user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        membership_id=uuid.UUID("99999999-3333-3333-3333-333333333333"),
        role="staff",
        email="assistant@fiduciaire-atlas.ma",
        full_name="Youssef Bennani (Collaborateur)",
        client_scope_ids=[],
    )


def test_internal_metrics_rbac_owner_and_operator_allowed(mock_session_owner, mock_session_operator, mock_session_staff):
    """Owner and operator are permitted to access internal metrics; staff is denied with 403."""
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

    def fake_db():
        yield FakeConn()

    app.dependency_overrides[get_db] = fake_db

    try:
        # 1. Staff is rejected with 403
        app.dependency_overrides[get_current_session] = lambda: mock_session_staff
        client = TestClient(app)
        resp = client.get("/v1/metrics/internal")
        assert resp.status_code == 403
        assert "Accès réservé" in resp.json()["detail"]

        # 2. Owner is allowed
        app.dependency_overrides[get_current_session] = lambda: mock_session_owner
        resp = client.get("/v1/metrics/internal")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "total_active_review_seconds" in data["summary"]

        # 3. Operator is allowed
        app.dependency_overrides[get_current_session] = lambda: mock_session_operator
        resp = client.get("/v1/metrics/internal")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_no_identifier_values_in_metrics_responses(mock_session_owner):
    """Review metrics must store/return counts and field keys only, NEVER raw identifiers (e.g. ICE, RIB) or field values."""
    import re
    from avenel.telemetry.review_effort import get_internal_metrics_summary

    wr_id = uuid.uuid4()
    u_id = uuid.uuid4()
    t_id = mock_session_owner.tenant_id

    # Mock DB cursor returning effort rows and provider costs
    class FakeCursor:
        def __init__(self):
            self.query_count = 0
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            self.query_count += 1
        def fetchall(self):
            if self.query_count == 1:
                # effort_rows: wr_id, status, client_name, period_name, user_id, user_name, user_email,
                # active_review_seconds, fields_corrected, entries_edited, issues_resolved, updated_at
                return [
                    (
                        wr_id,
                        "approved",
                        "Société Atlas SARL",
                        "2026-10",
                        u_id,
                        "Youssef Bennani",
                        "youssef@atlas.ma",
                        180,
                        2,
                        1,
                        1,
                        "2026-11-01T12:00:00Z",
                    )
                ]
            return []
        def fetchone(self):
            # provider_calls summary: total_cost, total_calls, succeeded, refused
            return (0.042, 3, 3, 0)

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    metrics = get_internal_metrics_summary(FakeConn(), t_id)

    # 1. Verify response structure contains counts and field keys only
    summary = metrics["summary"]
    assert summary["total_fields_corrected"] == 2
    assert summary["total_entries_edited"] == 1
    assert summary["total_issues_resolved"] == 1
    assert summary["provider_cost_label_fr"] == "Coût fournisseurs par dossier validé"
    assert summary["provider_cost_label_en"] == "Provider cost per accepted file"

    # 2. Verify compute and reviewer cost placeholders are clearly labelled and marked not_computed_yet
    assert summary["compute_cost"]["status"] == "not_computed_yet"
    assert "Coût calcul" in summary["compute_cost"]["label_fr"]
    assert summary["compute_cost"]["amount_mad"] is None

    assert summary["reviewer_cost"]["status"] == "not_computed_yet"
    assert "Coût réviseur" in summary["reviewer_cost"]["label_fr"]
    assert summary["reviewer_cost"]["amount_mad"] is None

    # 3. String representation scan: verify zero 15-digit ICE or 24-digit RIB values appear
    response_str = str(metrics)

    # Must NOT contain 'client_ice' key
    assert "client_ice" not in response_str

    # Must NOT contain any 15-digit numeric sequence (Moroccan ICE)
    assert not re.search(r"\b\d{15}\b", response_str)

    # Must NOT contain any 24-digit numeric sequence (Moroccan RIB)
    assert not re.search(r"\b\d{24}\b", response_str)

    # In files list, client_ice must not be present
    for f in metrics["files"]:
        assert "client_ice" not in f
        assert f["client_name"] == "Société Atlas SARL"
        assert f["compute_cost"]["status"] == "not_computed_yet"
        assert f["reviewer_cost"]["status"] == "not_computed_yet"

