"""End-to-end API tests for Phase 3 proposals module."""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.proposals.tax_mapping import seed_approved_client_tax_mappings
from avenel.tenancy.auth import grant_operator_access, set_rls_context
from tests.helpers import (
    seed_membership,
    seed_tenant,
    seed_user,
)


def _auth_headers(subject: str, tenant_id: uuid.UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        "X-Tenant-Id": str(tenant_id),
        "Idempotency-Key": f"idemp-{uuid.uuid4()}",
    }


@pytest.fixture
def proposal_api_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Fiscal API Proposals")

    sub_owner = f"owner-{uuid.uuid4()}"
    owner_user_id = seed_user(db_conn, identity_subject=sub_owner, email=f"{sub_owner}@avenel.ma")
    seed_membership(db_conn, owner_user_id, tenant_id, "owner")

    sub_acc = f"accountant-{uuid.uuid4()}"
    acc_user_id = seed_user(db_conn, identity_subject=sub_acc, email=f"{sub_acc}@avenel.ma")
    seed_membership(db_conn, acc_user_id, tenant_id, "accountant")

    sub_staff = f"staff-{uuid.uuid4()}"
    staff_user_id = seed_user(db_conn, identity_subject=sub_staff, email=f"{sub_staff}@avenel.ma")
    seed_membership(db_conn, staff_user_id, tenant_id, "staff")

    sub_op = f"operator-{uuid.uuid4()}"
    op_user_id = seed_user(db_conn, identity_subject=sub_op, email=f"{sub_op}@avenel.ma")
    grant_operator_access(
        conn=db_conn,
        tenant_id=tenant_id,
        granter_user_id=owner_user_id,
        operator_user_id=op_user_id,
        duration_hours=24.0,
    )

    set_rls_context(db_conn, tenant_id, acc_user_id)
    client_entity = create_client_entity(db_conn, tenant_id, "Société Alpha SARL", actor_id=str(acc_user_id))

    # Seed approved tax mappings so proposals can resolve VAT accounts
    seed_approved_client_tax_mappings(db_conn, tenant_id, client_entity.id, approver_id=acc_user_id)

    period = open_accounting_period(
        db_conn,
        tenant_id,
        client_entity.id,
        actor_id=str(acc_user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )

    wr_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'intake');
            """,
            (wr_id, tenant_id, client_entity.id, period["id"]),
        )
    db_conn.commit()

    return {
        "tenant_id": tenant_id,
        "client_id": client_entity.id,
        "work_request_id": wr_id,
        "sub_acc": sub_acc,
        "sub_staff": sub_staff,
        "sub_op": sub_op,
        "acc_user_id": acc_user_id,
        "staff_user_id": staff_user_id,
        "op_user_id": op_user_id,
    }


def _seed_document_for_proposal(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    work_request_id: uuid.UUID,
    fields: dict,
    doc_type: str = "purchase_invoice",
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    ext_id = uuid.uuid4()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (
                id, tenant_id, client_entity_id, work_request_id,
                original_filename, status, doc_type, source_channel
            ) VALUES (%s, %s, %s, %s, 'facture_sample.pdf', 'read', %s, 'console');
            """,
            (doc_id, tenant_id, client_id, work_request_id, doc_type),
        )
        cur.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, client_entity_id, document_id, version_number,
                byte_size, sha256, mime_type, object_key
            ) VALUES (%s, %s, %s, %s, 1, 2048, %s, 'application/pdf', %s);
            """,
            (ver_id, tenant_id, client_id, doc_id, hashlib.sha256(uuid.uuid4().bytes).hexdigest(), f"docs/{doc_id}.pdf"),
        )
        cur.execute(
            """
            INSERT INTO extractions (
                id, tenant_id, document_version_id, schema_version,
                engine, engine_version, status, fields, validation
            ) VALUES (%s, %s, %s, 'v1', 'synthetic', '1.0', 'succeeded', %s::jsonb, '{}'::jsonb);
            """,
            (ext_id, tenant_id, ver_id, json.dumps(fields)),
        )
    conn.commit()
    return doc_id


def test_proposal_generate_retrieve_and_list(db_conn: psycopg.Connection, proposal_api_env: dict):
    client = TestClient(app)
    tenant_id = proposal_api_env["tenant_id"]
    client_id = proposal_api_env["client_id"]
    wr_id = proposal_api_env["work_request_id"]
    sub_acc = proposal_api_env["sub_acc"]

    fields = {
        "invoice_number": {"value": "FA-2026-001", "page": 1, "bbox": [0.1, 0.1, 0.4, 0.15]},
        "invoice_date": {"value": "2026-03-15", "page": 1, "bbox": [0.1, 0.2, 0.4, 0.25]},
        "supplier_name": {"value": "Papeterie Marocaine", "page": 1},
        "supplier_ice": {"value": "001234567890123", "page": 1},
        "total_ht": {"value": 1000.0, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "tax_lines": [{"rate": 0.20, "base_ht": 1000.0, "amount_tva": 200.0}],
        "total_tva": {"value": 200.0, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 1200.0, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
        "currency": {"value": "MAD"},
    }

    doc_id = _seed_document_for_proposal(db_conn, tenant_id, client_id, wr_id, fields)

    # 1. Generate proposal
    gen_resp = client.post(
        f"/v1/documents/{doc_id}:generate-proposal",
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert gen_resp.status_code == 200, gen_resp.text
    prop_data = gen_resp.json()
    assert prop_data["revision"] == 1
    assert prop_data["status"] == "proposed"
    assert len(prop_data["lines"]) >= 3
    assert prop_data["lines"][0]["currency"] == "MAD"

    # Verify balance
    tot_debit = sum(float(line["debit_mad"]) for line in prop_data["lines"])
    tot_credit = sum(float(line["credit_mad"]) for line in prop_data["lines"])
    assert round(tot_debit, 2) == round(tot_credit, 2)
    assert round(tot_debit, 2) == 1200.00

    prop_id = prop_data["id"]

    # 2. Retrieve single proposal
    get_resp = client.get(
        f"/v1/proposals/{prop_id}",
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == prop_id

    # 3. List proposals for work request
    list_resp = client.get(
        f"/v1/work-requests/{wr_id}/proposals",
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert list_resp.status_code == 200
    props = list_resp.json()
    assert any(p["id"] == prop_id for p in props)


def test_proposal_revision_flow_and_no_per_entry_approval(db_conn: psycopg.Connection, proposal_api_env: dict):
    """Verifies proposal revisioning and confirms no per-entry approval endpoint exists."""
    client = TestClient(app)
    tenant_id = proposal_api_env["tenant_id"]
    client_id = proposal_api_env["client_id"]
    wr_id = proposal_api_env["work_request_id"]
    sub_acc = proposal_api_env["sub_acc"]

    fields = {
        "invoice_number": {"value": "FA-REV-01", "page": 1, "bbox": [0.1, 0.1, 0.4, 0.15]},
        "invoice_date": {"value": "2026-03-20", "page": 1, "bbox": [0.1, 0.2, 0.4, 0.25]},
        "supplier_name": {"value": "Service Informatique", "page": 1},
        "supplier_ice": {"value": "009876543210123", "page": 1},
        "total_ht": {"value": 5000.0, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "tax_lines": [{"rate": 0.20, "base_ht": 5000.0, "amount_tva": 1000.0}],
        "total_tva": {"value": 1000.0, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 6000.0, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
        "currency": {"value": "MAD"},
    }

    doc_id = _seed_document_for_proposal(db_conn, tenant_id, client_id, wr_id, fields)

    # 1. Generate
    gen_resp = client.post(
        f"/v1/documents/{doc_id}:generate-proposal",
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert gen_resp.status_code == 200
    rev1 = gen_resp.json()
    rev1_id = rev1["id"]

    # 2. Revise lines (change line label, keep balance)
    lines = rev1["lines"]
    lines[0]["label"] = "Charges informatiques révisées"

    rev_resp = client.put(
        f"/v1/proposals/{rev1_id}",
        json={"lines": lines},
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert rev_resp.status_code == 200, rev_resp.text
    rev2 = rev_resp.json()
    assert rev2["revision"] == 2
    assert rev2["status"] == "edited"
    rev2_id = rev2["id"]

    # Verify original is now superseded
    orig_resp = client.get(
        f"/v1/proposals/{rev1_id}",
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert orig_resp.status_code == 200
    assert orig_resp.json()["status"] == "superseded"

    # 3. Confirm NO per-entry approval endpoint exists (returns 404/405)
    app_resp = client.post(
        f"/v1/proposals/{rev2_id}:approve",
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert app_resp.status_code in (404, 405), "Per-entry approval endpoint must not exist (approval is monthly-file level)"


def test_proposal_role_based_access(db_conn: psycopg.Connection, proposal_api_env: dict):
    """Verifies RBAC: staff cannot edit proposals (403), accountant can edit proposals (200)."""
    client = TestClient(app)
    tenant_id = proposal_api_env["tenant_id"]
    client_id = proposal_api_env["client_id"]
    wr_id = proposal_api_env["work_request_id"]
    sub_acc = proposal_api_env["sub_acc"]
    sub_staff = proposal_api_env["sub_staff"]
    sub_op = proposal_api_env["sub_op"]

    fields = {
        "invoice_number": {"value": "FA-ROLE-01", "page": 1, "bbox": [0.1, 0.1, 0.4, 0.15]},
        "invoice_date": {"value": "2026-03-22", "page": 1, "bbox": [0.1, 0.2, 0.4, 0.25]},
        "supplier_name": {"value": "Fournisseur Test", "page": 1},
        "supplier_ice": {"value": "001122334455667", "page": 1},
        "total_ht": {"value": 100.0, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "tax_lines": [{"rate": 0.20, "base_ht": 100.0, "amount_tva": 20.0}],
        "total_tva": {"value": 20.0, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 120.0, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
        "currency": {"value": "MAD"},
    }

    doc_id = _seed_document_for_proposal(db_conn, tenant_id, client_id, wr_id, fields)

    # 1. Operator cannot generate proposal (403)
    op_gen_resp = client.post(
        f"/v1/documents/{doc_id}:generate-proposal",
        headers=_auth_headers(sub_op, tenant_id),
    )
    assert op_gen_resp.status_code == 403

    # 2. Staff can generate proposal (200)
    staff_gen_resp = client.post(
        f"/v1/documents/{doc_id}:generate-proposal",
        headers=_auth_headers(sub_staff, tenant_id),
    )
    assert staff_gen_resp.status_code == 200
    prop = staff_gen_resp.json()
    prop_id = prop["id"]
    lines = prop["lines"]

    # 3. Staff CANNOT edit proposals (403 - requires accountant / manager / owner)
    staff_edit_resp = client.put(
        f"/v1/proposals/{prop_id}",
        json={"lines": lines},
        headers=_auth_headers(sub_staff, tenant_id),
    )
    assert staff_edit_resp.status_code == 403

    # 4. Accountant CAN edit proposals (200)
    lines[0]["label"] = "Charges modifiées par comptable"
    acc_edit_resp = client.put(
        f"/v1/proposals/{prop_id}",
        json={"lines": lines},
        headers=_auth_headers(sub_acc, tenant_id),
    )
    assert acc_edit_resp.status_code == 200
