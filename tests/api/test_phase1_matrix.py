"""Comprehensive test matrix for every Phase 1 endpoint.

Tests:
Every Phase 1 endpoint x {
    same-tenant: 200 (or 201 for creation) with expected data,
    cross-tenant: 404 (never 403 or 200),
    client_user out-of-scope: 404 (never 403 or 200),
    unauthenticated: 401
}
"""

from __future__ import annotations

import datetime
import uuid

from fastapi.testclient import TestClient
import psycopg
import pytest

from apps.api.main import app
from avenel.accounting.service import seed_cgnc_chart
from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_client_scope, seed_membership, seed_tenant, seed_user


@pytest.fixture
def matrix_env(db_conn: psycopg.Connection):
    """Sets up two isolated tenants, an accountant user in tenant 1, an accountant in tenant 2,
    and a client_user in tenant 1 restricted to client 1.
    """
    # Tenant 1 & Client 1A (in scope for client_user), Client 1B (out of scope for client_user)
    t1_id = seed_tenant(db_conn, "Tenant Alpha Fiduciaire")
    u1_sub = f"manager-t1-{uuid.uuid4()}"
    u1_id = seed_user(db_conn, identity_subject=u1_sub, email=f"{u1_sub}@t1.ma")
    seed_membership(db_conn, u1_id, t1_id, role="manager")

    # Client user in Tenant 1
    cu_sub = f"client-user-{uuid.uuid4()}"
    cu_id = seed_user(db_conn, identity_subject=cu_sub, email=f"{cu_sub}@client.ma")
    m_cu_id = seed_membership(db_conn, cu_id, t1_id, role="client_user")

    # Tenant 2 (Cross-tenant attacker)
    t2_id = seed_tenant(db_conn, "Tenant Beta Fiduciaire")
    u2_sub = f"accountant-t2-{uuid.uuid4()}"
    u2_id = seed_user(db_conn, identity_subject=u2_sub, email=f"{u2_sub}@t2.ma")
    seed_membership(db_conn, u2_id, t2_id, role="accountant")

    # Create clients in Tenant 1
    # Create clients in Tenant 1 (using distinct valid ICEs per UNIQUE NULLS NOT DISTINCT constraint)
    set_rls_context(db_conn, t1_id, u1_id)
    c1a = create_client_entity(db_conn, t1_id, "Societe Alpha 1A", str(u1_id), ice="001122334455661")
    c1b = create_client_entity(db_conn, t1_id, "Societe Alpha 1B", str(u1_id), ice="001122334455662")

    # Grant client_user access ONLY to Client 1A
    seed_client_scope(db_conn, t1_id, m_cu_id, c1a.id)

    # Seed chart accounts and periods on Client 1A
    seed_cgnc_chart(db_conn, t1_id, c1a.id, str(u1_id))
    open_accounting_period(
        conn=db_conn,
        tenant_id=t1_id,
        client_id=c1a.id,
        actor_id=str(u1_id),
        period_code="2026-05",
        starts_on=datetime.date(2026, 5, 1),
        ends_on=datetime.date(2026, 5, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )

    # Create a separate client for archive testing
    c1_archive = create_client_entity(db_conn, t1_id, "Societe To Archive", str(u1_id), ice="001122334455663")

    db_conn.commit()

    return {
        "t1_id": t1_id,
        "t2_id": t2_id,
        "u1_sub": u1_sub,
        "u2_sub": u2_sub,
        "cu_sub": cu_sub,
        "c1a_id": c1a.id,
        "c1b_id": c1b.id,
        "c1_archive_id": c1_archive.id,
    }


# Matrix test definition
# Format: (name, method, path_template, json_payload, expected_success_status)
ENDPOINTS_MATRIX = [
    ("get_session", "GET", "/v1/me", None, 200),
    ("list_client_entities", "GET", "/v1/client-entities", None, 200),
    ("create_client_entity", "POST", "/v1/client-entities", {"legal_name": "New Client Test"}, 201),
    ("get_client_entity", "GET", "/v1/client-entities/{c1_id}", None, 200),
    ("put_client_entity", "PUT", "/v1/client-entities/{c1_id}", {"legal_name": "Updated Name"}, 200),
    ("patch_client_entity", "PATCH", "/v1/client-entities/{c1_id}", {"display_name": "Patched Name"}, 200),
    ("archive_client_entity", "POST", "/v1/client-entities/{c1_archive_id}/archive", {}, 200),
    ("list_accounting_periods", "GET", "/v1/client-entities/{c1_id}/periods", None, 200),
    ("open_accounting_period", "POST", "/v1/client-entities/{c1_id}/periods", {
        "period_code": "2026-06",
        "starts_on": "2026-06-01",
        "ends_on": "2026-06-30",
        "fiscal_year_end": "2026-12-31",
    }, 201),
    ("list_chart_accounts", "GET", "/v1/client-entities/{c1_id}/chart-accounts", None, 200),
    ("seed_cgnc_chart", "POST", "/v1/client-entities/{c1_id}/chart-accounts/seed-cgnc", {}, 200),
    ("import_chart_accounts", "POST", "/v1/client-entities/{c1_id}/chart-accounts/import", {
        "accounts": [{"code": "34211", "label": "Clients Divers"}]
    }, 200),
    ("get_dpa", "GET", "/v1/compliance/dpa", None, 200),
    ("get_cndp", "GET", "/v1/compliance/cndp-dossier", None, 200),
]


@pytest.mark.parametrize("name,method,path_tmpl,payload,expected_status", ENDPOINTS_MATRIX)
def test_phase1_matrix_four_quadrants(matrix_env: dict, name: str, method: str, path_tmpl: str, payload: dict | None, expected_status: int):
    """Executes the 4-quadrant security matrix for each Phase 1 endpoint:
    1. Positive same-tenant (200/201 with expected data)
    2. Cross-tenant isolation (404, never 403 or 200)
    3. client_user out-of-scope (404, never 403 or 200)
    4. Unauthenticated (401)
    """
    client = TestClient(app)
    t1_id = matrix_env["t1_id"]
    t2_id = matrix_env["t2_id"]
    u1_sub = matrix_env["u1_sub"]
    u2_sub = matrix_env["u2_sub"]
    cu_sub = matrix_env["cu_sub"]
    c1a_id = matrix_env["c1a_id"]
    c1b_id = matrix_env["c1b_id"]
    c1_archive_id = matrix_env["c1_archive_id"]

    # Resolve URL paths
    url_positive = path_tmpl.format(c1_id=c1a_id, c1_archive_id=c1_archive_id)
    url_out_of_scope = path_tmpl.format(c1_id=c1b_id, c1_archive_id=c1_archive_id)

    # -------------------------------------------------------------
    # Quadrant 1: POSITIVE TEST (Same-Tenant Accountant)
    # -------------------------------------------------------------
    pos_headers = {
        "X-Identity-Subject": u1_sub,
        "X-Tenant-Id": str(t1_id),
        "Idempotency-Key": str(uuid.uuid4()),
    }
    if method == "GET":
        res_pos = client.get(url_positive, headers=pos_headers)
    elif method == "POST":
        res_pos = client.post(url_positive, headers=pos_headers, json=payload)
    elif method == "PUT":
        res_pos = client.put(url_positive, headers=pos_headers, json=payload)
    elif method == "PATCH":
        res_pos = client.patch(url_positive, headers=pos_headers, json=payload)
    else:
        raise ValueError(f"Unsupported method {method}")

    assert res_pos.status_code == expected_status, (
        f"POSITIVE FAILED for {name} ({method} {url_positive}): expected {expected_status}, got {res_pos.status_code}: {res_pos.text}"
    )
    # Verify response contains data
    assert len(res_pos.text) > 0

    # -------------------------------------------------------------
    # Quadrant 2: CROSS-TENANT ISOLATION (Tenant 2 user accessing Tenant 1)
    # Must return 404 (never 403 or 200)
    # -------------------------------------------------------------
    cross_headers = {
        "X-Identity-Subject": u2_sub,
        "X-Tenant-Id": str(t1_id),  # Accessing Tenant 1
        "Idempotency-Key": str(uuid.uuid4()),
    }
    if method == "GET":
        res_cross = client.get(url_positive, headers=cross_headers)
    elif method == "POST":
        res_cross = client.post(url_positive, headers=cross_headers, json=payload)
    elif method == "PUT":
        res_cross = client.put(url_positive, headers=cross_headers, json=payload)
    elif method == "PATCH":
        res_cross = client.patch(url_positive, headers=cross_headers, json=payload)

    assert res_cross.status_code == 404, (
        f"CROSS-TENANT INVARIANT 1 FAILED for {name} ({method} {url_positive}): "
        f"expected 404, got {res_cross.status_code}: {res_cross.text}"
    )

    # -------------------------------------------------------------
    # Quadrant 3: CLIENT_USER SCOPING & PERMISSION ISOLATION
    # Expected denials return 404 for out-of-scope resources and 403 for in-scope actions role cannot perform.
    # -------------------------------------------------------------
    def _cu_headers() -> dict[str, str]:
        return {
            "X-Identity-Subject": cu_sub,
            "X-Tenant-Id": str(t1_id),
            "Idempotency-Key": str(uuid.uuid4()),
        }

    if "{c1_id}" in path_tmpl:
        # 1. Out-of-scope resource test -> MUST return 404 (never 403 or 200)
        if method == "GET":
            res_out = client.get(url_out_of_scope, headers=_cu_headers())
        elif method == "POST":
            res_out = client.post(url_out_of_scope, headers=_cu_headers(), json=payload)
        elif method == "PUT":
            res_out = client.put(url_out_of_scope, headers=_cu_headers(), json=payload)
        elif method == "PATCH":
            res_out = client.patch(url_out_of_scope, headers=_cu_headers(), json=payload)
        assert res_out.status_code == 404, (
            f"CLIENT_USER OUT-OF-SCOPE REFUSAL FAILED for {name}: expected 404, got {res_out.status_code}"
        )

        # 2. In-scope mutating action -> MUST return 403 (in-scope action client_user cannot perform)
        if method in ("POST", "PUT", "PATCH"):
            if method == "POST":
                res_in = client.post(url_positive, headers=_cu_headers(), json=payload)
            elif method == "PUT":
                res_in = client.put(url_positive, headers=_cu_headers(), json=payload)
            elif method == "PATCH":
                res_in = client.patch(url_positive, headers=_cu_headers(), json=payload)
            assert res_in.status_code == 403, (
                f"CLIENT_USER IN-SCOPE FORBIDDEN FAILED for {name}: expected 403, got {res_in.status_code}"
            )
    elif "{c1_archive_id}" in path_tmpl:
        # 1. Out-of-scope archive attempt (c1_archive_id is not in client_user scope) -> MUST return 404
        res_arch_out = client.post(url_positive, headers=_cu_headers(), json=payload)
        assert res_arch_out.status_code == 404, (
            f"CLIENT_USER ARCHIVE OUT-OF-SCOPE FAILED: expected 404, got {res_arch_out.status_code}"
        )
        # 2. In-scope archive attempt (c1a_id IS in client_user scope) -> MUST return 403
        res_arch_in = client.post(f"/v1/client-entities/{c1a_id}/archive", headers=_cu_headers(), json=payload)
        assert res_arch_in.status_code == 403, (
            f"CLIENT_USER ARCHIVE IN-SCOPE FORBIDDEN FAILED: expected 403, got {res_arch_in.status_code}"
        )
    else:
        # Tenant-level or compliance endpoints
        if method == "GET":
            res_scope = client.get(url_positive, headers=_cu_headers())
            if "compliance" in path_tmpl:
                assert res_scope.status_code == 404
            else:
                assert res_scope.status_code == 200
        else:
            # POST /v1/client-entities -> client_user cannot create clients -> 403
            res_scope = client.post(url_positive, headers=_cu_headers(), json=payload)
            assert res_scope.status_code == 403

    # -------------------------------------------------------------
    # Quadrant 4: UNAUTHENTICATED REQUEST (No token / subject)
    # Must return 401
    # -------------------------------------------------------------
    unauth_headers = {"Idempotency-Key": str(uuid.uuid4())}
    if method == "GET":
        res_unauth = client.get(url_positive, headers=unauth_headers)
    elif method == "POST":
        res_unauth = client.post(url_positive, headers=unauth_headers, json=payload)
    elif method == "PUT":
        res_unauth = client.put(url_positive, headers=unauth_headers, json=payload)
    elif method == "PATCH":
        res_unauth = client.patch(url_positive, headers=unauth_headers, json=payload)

    assert res_unauth.status_code == 401, (
        f"UNAUTHENTICATED CHECK FAILED for {name}: expected 401, got {res_unauth.status_code}"
    )
