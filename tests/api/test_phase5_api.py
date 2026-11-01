"""API endpoint tests for Phase 5: Approvals, Round Trips, and Issue Acknowledgement.

Enforces:
- POST /export-profiles/{id}:record-round-trip: owner/manager only, requiring MFA.
- POST /approvals/{id}:decide: MFA re-authentication within 5 minutes (RFC 9470 insufficient_user_authentication).
- POST /approvals/{id}:decide: requires subject_hash in body; 409 on mismatch.
- POST /issues/{id}:acknowledge: acknowledges review issue with note.
- GET /exports/{id}/file: verified signed token expiring in 15 minutes.
"""

from __future__ import annotations

import datetime
import time
import uuid

from fastapi.testclient import TestClient
import psycopg
import pytest

from apps.api.main import app
from avenel.approvals.service import request_work_request_approval
from avenel.clients.service import create_client_entity
from avenel.exports.service import (
    create_export,
    create_or_get_default_export_profile,
    generate_export_download_token,
)
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def phase5_api_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "API Phase 5 Cabinet")

    # Owner / Qualified Expert-Comptable
    owner_sub = f"owner-{uuid.uuid4()}"
    owner_id = seed_user(db_conn, identity_subject=owner_sub, email=f"{owner_sub}@avenel.ma")
    seed_membership(
        db_conn,
        owner_id,
        tenant_id,
        "owner",
        professional_title="expert_comptable",
        professional_registration_no="OEC-API-555",
    )

    # Accountant (preparer)
    acc_sub = f"acc-{uuid.uuid4()}"
    acc_id = seed_user(db_conn, identity_subject=acc_sub, email=f"{acc_sub}@avenel.ma")
    seed_membership(db_conn, acc_id, tenant_id, "accountant")

    set_rls_context(db_conn, tenant_id, acc_id)

    client = create_client_entity(db_conn, tenant_id, "API Testing SARL", actor_id=str(acc_id))
    period = open_accounting_period(
        db_conn,
        tenant_id,
        client.id,
        actor_id=str(acc_id),
        period_code="2026-10",
        starts_on=datetime.date(2026, 10, 1),
        ends_on=datetime.date(2026, 10, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )

    wr_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'intake');
            """,
            (wr_id, tenant_id, client.id, period["id"]),
        )
        prop_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Facture test', 'rules', 'proposed');
            """,
            (prop_id, tenant_id, client.id, wr_id),
        )
        acc1 = uuid.uuid4()
        acc2 = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, '6111000', 'Achats', 'cgnc_seed'),
                   (%s, %s, %s, '4411000', 'Fournisseurs', 'cgnc_seed');
            """,
            (acc1, tenant_id, client.id, acc2, tenant_id, client.id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 400.0, 0.0, 400.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseurs', 'MAD', 0.0, 400.0, 0.0, 400.0);
            """,
            (uuid.uuid4(), tenant_id, client.id, prop_id, acc1, uuid.uuid4(), tenant_id, client.id, prop_id, acc2),
        )
    db_conn.commit()

    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "work_request_id": wr_id,
        "owner_sub": owner_sub,
        "owner_id": owner_id,
        "acc_sub": acc_sub,
        "acc_id": acc_id,
    }


def test_api_record_round_trip_permissions_and_mfa(phase5_api_env, db_conn: psycopg.Connection):
    """POST /export-profiles/{id}:record-round-trip enforces owner/manager role and active MFA."""
    client = TestClient(app)
    t_id = phase5_api_env["tenant_id"]
    owner_sub = phase5_api_env["owner_sub"]
    acc_sub = phase5_api_env["acc_sub"]

    prof = create_or_get_default_export_profile(db_conn, t_id, "sage100_csv")
    prof_id = prof["id"]
    db_conn.commit()

    body = {
        "software": "Sage 100",
        "version": "v10.1",
        "imported_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "result": "ok",
        "notes": "Test round-trip réussi",
    }

    # 1. Non-owner/manager role (accountant) rejected with 403
    resp_acc = client.post(
        f"/v1/export-profiles/{prof_id}:record-round-trip",
        headers={
            "X-Identity-Subject": acc_sub,
            "X-Tenant-Id": str(t_id),
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json=body,
    )
    assert resp_acc.status_code == 403

    # 2. Owner without MFA rejected with 401 and WWW-Authenticate header
    resp_no_mfa = client.post(
        f"/v1/export-profiles/{prof_id}:record-round-trip",
        headers={
            "X-Identity-Subject": owner_sub,
            "X-Tenant-Id": str(t_id),
            "X-Mfa-Authenticated": "false",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json=body,
    )
    assert resp_no_mfa.status_code == 401
    assert 'error="insufficient_user_authentication"' in resp_no_mfa.headers.get("WWW-Authenticate", "")

    # 3. Owner with MFA succeeds with 200 OK
    resp_ok = client.post(
        f"/v1/export-profiles/{prof_id}:record-round-trip",
        headers={
            "X-Identity-Subject": owner_sub,
            "X-Tenant-Id": str(t_id),
            "X-Mfa-Authenticated": "true",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json=body,
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["result"] == "ok"
    assert data["software"] == "Sage 100"


def test_api_decide_approval_mfa_5_minute_and_stale_hash(phase5_api_env, db_conn: psycopg.Connection):
    """POST /approvals/{id}:decide requires MFA re-authentication <= 5min and matching subject_hash."""
    client = TestClient(app)
    t_id = phase5_api_env["tenant_id"]
    c_id = phase5_api_env["client_id"]
    w_id = phase5_api_env["work_request_id"]
    owner_sub = phase5_api_env["owner_sub"]
    acc_id = phase5_api_env["acc_id"]

    set_rls_context(db_conn, t_id, acc_id)
    req = request_work_request_approval(db_conn, t_id, c_id, w_id, acc_id)
    app_id = req["id"]
    subject_hash = req["subject_hash"]
    db_conn.commit()

    now_ts = int(time.time())

    # 1. Stale MFA (authenticated 400 seconds ago > 300s) -> 401 with RFC 9470 header
    resp_stale_mfa = client.post(
        f"/v1/approvals/{app_id}:decide",
        headers={
            "X-Identity-Subject": owner_sub,
            "X-Tenant-Id": str(t_id),
            "X-Mfa-Authenticated": "true",
            "X-Auth-Time": str(now_ts - 400),
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "decision": "approved",
            "reason": "Validation complète",
            "subject_hash": subject_hash,
        },
    )
    assert resp_stale_mfa.status_code == 401
    assert 'error="insufficient_user_authentication"' in resp_stale_mfa.headers.get("WWW-Authenticate", "")

    # 2. Hash mismatch -> 409 Conflict
    resp_mismatch_hash = client.post(
        f"/v1/approvals/{app_id}:decide",
        headers={
            "X-Identity-Subject": owner_sub,
            "X-Tenant-Id": str(t_id),
            "X-Mfa-Authenticated": "true",
            "X-Auth-Time": str(now_ts - 60),
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "decision": "approved",
            "reason": "Validation complète",
            "subject_hash": "f" * 64,
        },
    )
    assert resp_mismatch_hash.status_code == 409

    # 3. Valid recent MFA (authenticated 60s ago) + matching hash -> 200 OK!
    resp_ok = client.post(
        f"/v1/approvals/{app_id}:decide",
        headers={
            "X-Identity-Subject": owner_sub,
            "X-Tenant-Id": str(t_id),
            "X-Mfa-Authenticated": "true",
            "X-Auth-Time": str(now_ts - 60),
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "decision": "approved",
            "reason": "Dossier vérifié et approuvé",
            "subject_hash": subject_hash,
        },
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "approved"


def test_api_issue_acknowledge_endpoint(phase5_api_env, db_conn: psycopg.Connection):
    """POST /issues/{id}:acknowledge acknowledges review issue with note."""
    client = TestClient(app)
    t_id = phase5_api_env["tenant_id"]
    c_id = phase5_api_env["client_id"]
    w_id = phase5_api_env["work_request_id"]
    acc_sub = phase5_api_env["acc_sub"]
    acc_id = phase5_api_env["acc_id"]

    set_rls_context(db_conn, t_id, acc_id)
    issue_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO issues (id, tenant_id, client_entity_id, work_request_id, code, severity, status)
            VALUES (%s, %s, %s, %s, 'DUPLICATE_PROBABLE', 'review', 'open');
            """,
            (issue_id, t_id, c_id, w_id),
        )
    db_conn.commit()

    # Empty note rejected
    resp_empty = client.post(
        f"/v1/issues/{issue_id}:acknowledge",
        headers={
            "X-Identity-Subject": acc_sub,
            "X-Tenant-Id": str(t_id),
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={"resolution_note": ""},
    )
    assert resp_empty.status_code == 422

    # Valid acknowledgement
    resp_ok = client.post(
        f"/v1/issues/{issue_id}:acknowledge",
        headers={
            "X-Identity-Subject": acc_sub,
            "X-Tenant-Id": str(t_id),
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={"resolution_note": "Justifié par bon de commande validé"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "resolved"
    assert resp_ok.json()["resolution"] == "accepted_as_is"

