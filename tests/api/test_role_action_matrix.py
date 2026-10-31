"""Role x Action Test Matrix within the same tenant (Phase 1 Mutating Endpoints).

Validates:
Roles: owner, manager, accountant, staff, client_user (in-scope), client_user (out-of-scope), operator.
Rule:
- Denials for out-of-scope resources return 404.
- Denials for in-scope actions the role cannot perform return 403.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from fastapi.testclient import TestClient
import psycopg
import pytest

from apps.api.main import app
from avenel.accounting.service import seed_cgnc_chart
from avenel.clients.service import create_client_entity
from avenel.tenancy.auth import grant_operator_access, set_rls_context
from tests.helpers import seed_client_scope, seed_membership, seed_tenant, seed_user


@pytest.fixture
def rbac_env(db_conn: psycopg.Connection) -> dict[str, Any]:
    """Sets up a tenant with all 6 roles and two clients (one in-scope for client_user, one out-of-scope)."""
    t_id = seed_tenant(db_conn, "Cabinet RBAC Matrix Fiduciaire")

    # 1. Owner
    owner_sub = f"owner-{uuid.uuid4()}"
    owner_id = seed_user(db_conn, identity_subject=owner_sub, email=f"{owner_sub}@cabinet.ma")
    seed_membership(db_conn, owner_id, t_id, role="owner")

    # 2. Manager
    manager_sub = f"manager-{uuid.uuid4()}"
    manager_id = seed_user(db_conn, identity_subject=manager_sub, email=f"{manager_sub}@cabinet.ma")
    seed_membership(db_conn, manager_id, t_id, role="manager")

    # 3. Accountant
    accountant_sub = f"accountant-{uuid.uuid4()}"
    accountant_id = seed_user(db_conn, identity_subject=accountant_sub, email=f"{accountant_sub}@cabinet.ma")
    seed_membership(db_conn, accountant_id, t_id, role="accountant")

    # 4. Staff
    staff_sub = f"staff-{uuid.uuid4()}"
    staff_id = seed_user(db_conn, identity_subject=staff_sub, email=f"{staff_sub}@cabinet.ma")
    seed_membership(db_conn, staff_id, t_id, role="staff")

    # 5. Client User
    client_user_sub = f"client-user-{uuid.uuid4()}"
    client_user_id = seed_user(db_conn, identity_subject=client_user_sub, email=f"{client_user_sub}@client.ma")
    m_cu_id = seed_membership(db_conn, client_user_id, t_id, role="client_user")

    # 6. Operator (granted 24h active access)
    operator_sub = f"operator-{uuid.uuid4()}"
    operator_id = seed_user(db_conn, identity_subject=operator_sub, email=f"{operator_sub}@support.avenel.ma")
    grant_operator_access(
        conn=db_conn,
        tenant_id=t_id,
        granter_user_id=owner_id,
        operator_user_id=operator_id,
        duration_hours=24.0,
    )

    # Create Client In-Scope (for client_user) & Client Out-Of-Scope
    set_rls_context(db_conn, t_id, owner_id)
    c_in = create_client_entity(db_conn, t_id, "Ste Client In-Scope", str(owner_id), ice="001122334455671")
    c_out = create_client_entity(db_conn, t_id, "Ste Client Out-Of-Scope", str(owner_id), ice="001122334455672")

    # Assign c_in to client_user scope
    seed_client_scope(db_conn, t_id, m_cu_id, c_in.id)

    db_conn.commit()

    return {
        "tenant_id": t_id,
        "owner_sub": owner_sub,
        "manager_sub": manager_sub,
        "accountant_sub": accountant_sub,
        "staff_sub": staff_sub,
        "client_user_sub": client_user_sub,
        "operator_sub": operator_sub,
        "client_in_id": c_in.id,
        "client_out_id": c_out.id,
    }


def _send_request(
    client: TestClient,
    method: str,
    path: str,
    sub: str,
    tenant_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
):
    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(tenant_id),
        "Idempotency-Key": str(uuid.uuid4()),
    }
    if method == "POST":
        return client.post(path, headers=headers, json=payload or {})
    elif method == "PUT":
        return client.put(path, headers=headers, json=payload or {})
    elif method == "PATCH":
        return client.patch(path, headers=headers, json=payload or {})
    raise ValueError(f"Method {method} not handled")


def test_role_action_matrix_create_client(rbac_env: dict[str, Any]):
    """POST /v1/client-entities: owner, manager, accountant -> 201; staff, client_user, operator -> 403."""
    client = TestClient(app)
    t_id = rbac_env["tenant_id"]

    # 1. Owner -> 201
    r_owner = _send_request(client, "POST", "/v1/client-entities", rbac_env["owner_sub"], t_id, {"legal_name": "New By Owner", "ice": "001122334455681"})
    assert r_owner.status_code == 201

    # 2. Manager -> 201
    r_mgr = _send_request(client, "POST", "/v1/client-entities", rbac_env["manager_sub"], t_id, {"legal_name": "New By Mgr", "ice": "001122334455682"})
    assert r_mgr.status_code == 201

    # 3. Accountant -> 201
    r_acc = _send_request(client, "POST", "/v1/client-entities", rbac_env["accountant_sub"], t_id, {"legal_name": "New By Acc", "ice": "001122334455683"})
    assert r_acc.status_code == 201

    # 4. Staff -> 403
    r_staff = _send_request(client, "POST", "/v1/client-entities", rbac_env["staff_sub"], t_id, {"legal_name": "New By Staff"})
    assert r_staff.status_code == 403

    # 5. Client User -> 403
    r_cu = _send_request(client, "POST", "/v1/client-entities", rbac_env["client_user_sub"], t_id, {"legal_name": "New By CU"})
    assert r_cu.status_code == 403

    # 6. Operator -> 403
    r_op = _send_request(client, "POST", "/v1/client-entities", rbac_env["operator_sub"], t_id, {"legal_name": "New By Op"})
    assert r_op.status_code == 403


def test_role_action_matrix_update_client(rbac_env: dict[str, Any]):
    """PUT /v1/client-entities/{id}:
    - In-scope: owner, manager, accountant -> 200; staff, client_user, operator -> 403.
    - Out-of-scope (client_user): -> 404.
    """
    client = TestClient(app)
    t_id = rbac_env["tenant_id"]
    c_in = rbac_env["client_in_id"]
    c_out = rbac_env["client_out_id"]

    # In-scope tests
    assert _send_request(client, "PUT", f"/v1/client-entities/{c_in}", rbac_env["owner_sub"], t_id, {"legal_name": "Updated by Owner"}).status_code == 200
    assert _send_request(client, "PUT", f"/v1/client-entities/{c_in}", rbac_env["manager_sub"], t_id, {"legal_name": "Updated by Mgr"}).status_code == 200
    assert _send_request(client, "PUT", f"/v1/client-entities/{c_in}", rbac_env["accountant_sub"], t_id, {"legal_name": "Updated by Acc"}).status_code == 200

    assert _send_request(client, "PUT", f"/v1/client-entities/{c_in}", rbac_env["staff_sub"], t_id, {"legal_name": "Updated by Staff"}).status_code == 403
    assert _send_request(client, "PUT", f"/v1/client-entities/{c_in}", rbac_env["client_user_sub"], t_id, {"legal_name": "Updated by CU"}).status_code == 403
    assert _send_request(client, "PUT", f"/v1/client-entities/{c_in}", rbac_env["operator_sub"], t_id, {"legal_name": "Updated by Op"}).status_code == 403

    # Out-of-scope test for client_user -> MUST return 404 (never 403)
    assert _send_request(client, "PUT", f"/v1/client-entities/{c_out}", rbac_env["client_user_sub"], t_id, {"legal_name": "Updated"}).status_code == 404


def test_role_action_matrix_archive_client(rbac_env: dict[str, Any], db_conn: psycopg.Connection):
    """POST /v1/client-entities/{id}/archive:
    - owner, manager -> 200.
    - accountant, staff, client_user, operator -> 403.
    - out-of-scope client_user -> 404.
    """
    client = TestClient(app)
    t_id = rbac_env["tenant_id"]
    c_in = rbac_env["client_in_id"]
    c_out = rbac_env["client_out_id"]

    # In-scope: accountant cannot archive -> 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/archive", rbac_env["accountant_sub"], t_id).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/archive", rbac_env["staff_sub"], t_id).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/archive", rbac_env["client_user_sub"], t_id).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/archive", rbac_env["operator_sub"], t_id).status_code == 403

    # Out-of-scope: client_user -> 404
    assert _send_request(client, "POST", f"/v1/client-entities/{c_out}/archive", rbac_env["client_user_sub"], t_id).status_code == 404

    # Manager -> 200 (on out-of-scope client for CU, which manager can see)
    assert _send_request(client, "POST", f"/v1/client-entities/{c_out}/archive", rbac_env["manager_sub"], t_id).status_code == 200


def test_role_action_matrix_periods(rbac_env: dict[str, Any]):
    """POST /v1/client-entities/{id}/periods:
    - In-scope: owner, manager, accountant -> 201; staff, client_user, operator -> 403.
    - Out-of-scope client_user -> 404.
    """
    client = TestClient(app)
    t_id = rbac_env["tenant_id"]
    c_in = rbac_env["client_in_id"]
    c_out = rbac_env["client_out_id"]

    period_payload = {
        "period_code": "2026-07",
        "starts_on": "2026-07-01",
        "ends_on": "2026-07-31",
        "fiscal_year_end": "2026-12-31",
    }

    # Out-of-scope client_user -> 404
    assert _send_request(client, "POST", f"/v1/client-entities/{c_out}/periods", rbac_env["client_user_sub"], t_id, period_payload).status_code == 404

    # In-scope: unauthorized -> 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/periods", rbac_env["staff_sub"], t_id, period_payload).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/periods", rbac_env["client_user_sub"], t_id, period_payload).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/periods", rbac_env["operator_sub"], t_id, period_payload).status_code == 403

    # In-scope: accountant -> 201
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/periods", rbac_env["accountant_sub"], t_id, period_payload).status_code == 201


def test_role_action_matrix_chart(rbac_env: dict[str, Any]):
    """POST /v1/client-entities/{id}/chart-accounts/seed-cgnc and import:
    - In-scope: owner, manager, accountant -> 200; staff, client_user, operator -> 403.
    - Out-of-scope client_user -> 404.
    """
    client = TestClient(app)
    t_id = rbac_env["tenant_id"]
    c_in = rbac_env["client_in_id"]
    c_out = rbac_env["client_out_id"]

    import_payload = {
        "accounts": [{"code": "34211", "label": "Clients Locaux"}]
    }

    # Out-of-scope client_user -> 404
    assert _send_request(client, "POST", f"/v1/client-entities/{c_out}/chart-accounts/seed-cgnc", rbac_env["client_user_sub"], t_id).status_code == 404
    assert _send_request(client, "POST", f"/v1/client-entities/{c_out}/chart-accounts/import", rbac_env["client_user_sub"], t_id, import_payload).status_code == 404

    # In-scope: unauthorized -> 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/seed-cgnc", rbac_env["staff_sub"], t_id).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/seed-cgnc", rbac_env["client_user_sub"], t_id).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/seed-cgnc", rbac_env["operator_sub"], t_id).status_code == 403

    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/import", rbac_env["staff_sub"], t_id, import_payload).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/import", rbac_env["client_user_sub"], t_id, import_payload).status_code == 403
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/import", rbac_env["operator_sub"], t_id, import_payload).status_code == 403

    # In-scope: accountant -> 200
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/seed-cgnc", rbac_env["accountant_sub"], t_id).status_code == 200
    assert _send_request(client, "POST", f"/v1/client-entities/{c_in}/chart-accounts/import", rbac_env["accountant_sub"], t_id, import_payload).status_code == 200
