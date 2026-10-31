"""Cross-tenant isolation tests per ARCHITECTURE.md Invariant 1 and Phase 1 Exit Criteria.

Exit Criteria:
"Cross-tenant tests for every endpoint (read, write, list, ID guessing) return 404 (never 403 or 200)."
"""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_cross_tenant_isolation_every_endpoint_returns_404(
    postgres_url: str,
    db_conn: psycopg.Connection,
):
    """Verifies that accessing, guessing, reading, or writing resources of another tenant returns 404."""
    client = TestClient(app)

    # 1. Setup Tenant A and User A
    tenant_a = seed_tenant(db_conn, "Cabinet A")
    user_a = seed_user(db_conn, "sub-user-a", "user.a@cabinet-a.ma", "Analyste A")
    seed_membership(db_conn, user_a, tenant_a, role="accountant")

    # 2. Setup Tenant B and User B
    tenant_b = seed_tenant(db_conn, "Cabinet B")
    user_b = seed_user(db_conn, "sub-user-b", "user.b@cabinet-b.ma", "Analyste B")
    seed_membership(db_conn, user_b, tenant_b, role="accountant")

    # 3. Create a client company in Tenant B (as User B)
    res_b = client.post(
        "/v1/client-entities",
        headers={
            "X-Identity-Subject": "sub-user-b",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "legal_name": "Société B SARL",
            "ice": "123456789012345",
            "if_number": "9876543",
        },
    )
    assert res_b.status_code == 201, res_b.text
    client_b_id = res_b.json()["id"]

    # Open a period for Client B
    res_p = client.post(
        f"/v1/client-entities/{client_b_id}/periods",
        headers={
            "X-Identity-Subject": "sub-user-b",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "period_code": "2026-09",
            "starts_on": "2026-09-01",
            "ends_on": "2026-09-30",
            "fiscal_year_end": "2026-12-31",
        },
    )
    assert res_p.status_code == 201, res_p.text

    # Seed CGNC chart for Client B
    res_c = client.post(
        f"/v1/client-entities/{client_b_id}/chart-accounts/seed-cgnc",
        headers={
            "X-Identity-Subject": "sub-user-b",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert res_c.status_code == 200, res_c.text

    # 4. Now perform cross-tenant requests as User A against Client B
    def make_headers_a():
        return {
            "X-Identity-Subject": "sub-user-a",
            "Idempotency-Key": str(uuid.uuid4()),
        }

    # (a) List client companies: User A never sees Client B
    list_res = client.get("/v1/client-entities", headers=make_headers_a())
    assert list_res.status_code == 200
    returned_ids = [item["id"] for item in list_res.json()["items"]]
    assert client_b_id not in returned_ids

    # (b) Read Client B details by ID (cross-tenant) -> MUST return 404 (never 403 or 200)
    get_res = client.get(f"/v1/client-entities/{client_b_id}", headers=make_headers_a())
    assert get_res.status_code == 404, f"Expected 404 for cross-tenant GET, got {get_res.status_code}"

    # (c) ID guessing (random non-existent UUID) -> MUST return 404
    random_id = str(uuid.uuid4())
    guess_res = client.get(f"/v1/client-entities/{random_id}", headers=make_headers_a())
    assert guess_res.status_code == 404

    # (d) Update Client B (cross-tenant PUT) -> MUST return 404
    put_res = client.put(
        f"/v1/client-entities/{client_b_id}",
        headers=make_headers_a(),
        json={"legal_name": "Tampered Name"},
    )
    assert put_res.status_code == 404, f"Expected 404 for cross-tenant PUT, got {put_res.status_code}"

    # (e) Archive Client B (cross-tenant archive POST) -> MUST return 404
    archive_res = client.post(f"/v1/client-entities/{client_b_id}/archive", headers=make_headers_a())
    assert archive_res.status_code == 404, f"Expected 404 for cross-tenant archive, got {archive_res.status_code}"

    # (f) Read periods of Client B (cross-tenant GET) -> MUST return 404
    periods_res = client.get(f"/v1/client-entities/{client_b_id}/periods", headers=make_headers_a())
    assert periods_res.status_code == 404, f"Expected 404 for cross-tenant GET periods, got {periods_res.status_code}"

    # (g) Open period for Client B (cross-tenant POST) -> MUST return 404
    post_period_res = client.post(
        f"/v1/client-entities/{client_b_id}/periods",
        headers=make_headers_a(),
        json={
            "period_code": "2026-10",
            "starts_on": "2026-10-01",
            "ends_on": "2026-10-31",
            "fiscal_year_end": "2026-12-31",
        },
    )
    assert post_period_res.status_code == 404, f"Expected 404 for cross-tenant POST period, got {post_period_res.status_code}"

    # (h) Read chart accounts of Client B (cross-tenant GET) -> MUST return 404
    chart_res = client.get(f"/v1/client-entities/{client_b_id}/chart-accounts", headers=make_headers_a())
    assert chart_res.status_code == 404, f"Expected 404 for cross-tenant GET chart, got {chart_res.status_code}"

    # (i) Seed CGNC chart for Client B (cross-tenant POST) -> MUST return 404
    seed_res = client.post(
        f"/v1/client-entities/{client_b_id}/chart-accounts/seed-cgnc",
        headers=make_headers_a(),
    )
    assert seed_res.status_code == 404, f"Expected 404 for cross-tenant POST seed-cgnc, got {seed_res.status_code}"

    # (j) Import chart accounts for Client B (cross-tenant POST) -> MUST return 404
    import_res = client.post(
        f"/v1/client-entities/{client_b_id}/chart-accounts/import",
        headers=make_headers_a(),
        json={"accounts": [{"code": "6111", "label": "Achats"}]},
    )
    assert import_res.status_code == 404, f"Expected 404 for cross-tenant POST import, got {import_res.status_code}"
