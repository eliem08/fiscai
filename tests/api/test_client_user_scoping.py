"""Client user scoping tests per ARCHITECTURE.md Phase 1 Exit Criteria.

Exit Criteria:
"Client user cannot see another company."
"""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import (
    seed_client_scope,
    seed_membership,
    seed_tenant,
    seed_user,
)


def test_client_user_cannot_see_unscoped_company(
    postgres_url: str,
    db_conn: psycopg.Connection,
):
    """Verifies that a client_user can only access assigned companies, receiving 404 for any other."""
    client = TestClient(app)

    # 1. Setup Tenant and Firm Admin
    tenant_id = seed_tenant(db_conn, "Cabinet Scoping Test")
    admin_user = seed_user(db_conn, "sub-firm-admin", "admin@cabinet-scope.ma", "Admin Firm")
    seed_membership(db_conn, admin_user, tenant_id, role="owner")

    # 2. Create Company 1 and Company 2 in the tenant
    admin_headers = {
        "X-Identity-Subject": "sub-firm-admin",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    res_1 = client.post(
        "/v1/client-entities",
        headers=admin_headers,
        json={"legal_name": "Société Alpha SARL", "ice": "111111111111111"},
    )
    assert res_1.status_code == 201
    company_1_id = uuid.UUID(res_1.json()["id"])

    res_2 = client.post(
        "/v1/client-entities",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"legal_name": "Société Beta SARL", "ice": "222222222222222"},
    )
    assert res_2.status_code == 201
    company_2_id = uuid.UUID(res_2.json()["id"])

    # 3. Create client_user scoped exclusively to Company 1
    client_user = seed_user(db_conn, "sub-client-user-1", "user@alpha.ma", "Client Alpha User")
    m_id = seed_membership(db_conn, client_user, tenant_id, role="client_user")
    seed_client_scope(db_conn, tenant_id, m_id, company_1_id)

    client_headers = {
        "X-Identity-Subject": "sub-client-user-1",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    # 4. Verification

    # (a) List companies: Client user sees ONLY Company 1
    list_res = client.get("/v1/client-entities", headers=client_headers)
    assert list_res.status_code == 200
    returned_ids = [item["id"] for item in list_res.json()["items"]]
    assert str(company_1_id) in returned_ids
    assert str(company_2_id) not in returned_ids, "Client user must NEVER see another company in list!"

    # (b) Direct read of scoped Company 1 succeeds
    get_res_1 = client.get(f"/v1/client-entities/{company_1_id}", headers=client_headers)
    assert get_res_1.status_code == 200
    assert get_res_1.json()["legal_name"] == "Société Alpha SARL"

    # (c) Direct read of unscoped Company 2 MUST return 404 (never 403 or 200)
    get_res_2 = client.get(f"/v1/client-entities/{company_2_id}", headers=client_headers)
    assert get_res_2.status_code == 404, f"Expected 404 for unscoped company read, got {get_res_2.status_code}"

    # (d) Attempting to update Company 2 returns 404
    put_res = client.put(
        f"/v1/client-entities/{company_2_id}",
        headers={**client_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"legal_name": "Hacked Name"},
    )
    assert put_res.status_code == 404

    # (e) Attempting to archive Company 2 returns 404
    archive_res = client.post(
        f"/v1/client-entities/{company_2_id}/archive",
        headers={**client_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert archive_res.status_code == 404

    # (f) Attempting to read periods of Company 2 returns 404
    periods_res = client.get(f"/v1/client-entities/{company_2_id}/periods", headers=client_headers)
    assert periods_res.status_code == 404

    # (g) Attempting to read chart accounts of Company 2 returns 404
    chart_res = client.get(f"/v1/client-entities/{company_2_id}/chart-accounts", headers=client_headers)
    assert chart_res.status_code == 404
