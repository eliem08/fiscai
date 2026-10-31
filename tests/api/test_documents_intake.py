"""End-to-end integration and security tests for Phase 2 intake and reading."""

from __future__ import annotations

import datetime
import hashlib
import uuid
import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.clients.service import create_client_entity
from avenel.documents.scanner import EICAR_SIGNATURE
from avenel.infrastructure.storage import get_storage
from avenel.periods.service import open_accounting_period
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


def _seed_work_request(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID, period_id: uuid.UUID) -> uuid.UUID:
    wr_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'intake')
            RETURNING id;
            """,
            (wr_id, tenant_id, client_id, period_id),
        )
        conn.commit()
    return wr_id


def test_document_intake_full_pipeline_success(db_conn: psycopg.Connection):
    """Happy path: upload init, storage put, complete upload, rendering, OCR, extraction, and validation."""
    client = TestClient(app)
    tenant_id = seed_tenant(db_conn, "Cabinet Fiscal Casablanca")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    c_id = create_client_entity(db_conn, tenant_id, "Atlas Négoce SARL", actor_id=str(user_id)).id
    p_id = open_accounting_period(
        db_conn,
        tenant_id,
        c_id,
        actor_id=str(user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    wr_id = _seed_work_request(db_conn, tenant_id, c_id, p_id)

    # Clean invoice payload
    invoice_text = b"""
Societe Atlas Fournitures SARL
ICE: 001234567890123 | IF: 12345678 | RC 45678 Casa
FACTURE N: FAC-2026-999
Date: 15/03/2026
Client: Atlas Negoce SARL
ICE Client: 009876543210987

Total HT: 1000.00 MAD
TVA 20% Base: 1000.00 Montant: 200.00
Total TTC: 1200.00 MAD
"""
    file_sha256 = hashlib.sha256(invoice_text).hexdigest()
    headers = _auth_headers(sub, tenant_id)

    # 1. Initialize upload
    init_res = client.post(
        f"/v1/work-requests/{wr_id}/uploads",
        headers=headers,
        json={
            "original_filename": "facture_atlas.pdf",
            "byte_size": len(invoice_text),
            "mime_type": "application/pdf",
            "sha256": file_sha256,
        },
    )
    assert init_res.status_code == 201, init_res.text
    init_data = init_res.json()
    doc_id = init_data["document_id"]
    object_key = init_data["object_key"]

    # 2. Put file into storage backend
    storage = get_storage()
    storage.put_object(object_key, invoice_text, "application/pdf")

    # 3. Complete upload
    headers["Idempotency-Key"] = f"idemp-{uuid.uuid4()}"
    comp_res = client.post(f"/v1/documents/{doc_id}:complete-upload", headers=headers)
    assert comp_res.status_code == 200, comp_res.text
    comp_data = comp_res.json()
    assert comp_data["document_id"] == doc_id
    assert comp_data["doc_type"] == "purchase_invoice"
    assert comp_data["status"] == "read"

    # 4. Fetch document extraction
    ext_res = client.get(f"/v1/documents/{doc_id}/extraction", headers=headers)
    assert ext_res.status_code == 200
    ext_data = ext_res.json()
    assert ext_data["fields"]["supplier_ice"]["value"] == "001234567890123"
    assert ext_data["fields"]["total_ttc"]["value"] == 1200.0

    # 5. Fetch page image
    page_res = client.get(f"/v1/documents/{doc_id}/pages/1", headers=headers)
    assert page_res.status_code == 200
    assert "image_url" in page_res.json()


def test_exact_duplicate_document_resubmitted_returns_200(db_conn: psycopg.Connection):
    """Exact duplicate upload returns 200 with existing doc ID and logs document.resubmitted."""
    client = TestClient(app)
    tenant_id = seed_tenant(db_conn, "Cabinet Test Duplicate")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    c_id = create_client_entity(db_conn, tenant_id, "Société Alpha", actor_id=str(user_id)).id
    p_id = open_accounting_period(
        db_conn,
        tenant_id,
        c_id,
        actor_id=str(user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    wr_id = _seed_work_request(db_conn, tenant_id, c_id, p_id)

    dummy_content = b"Exact duplicate test content"
    sha256 = hashlib.sha256(dummy_content).hexdigest()

    headers = _auth_headers(sub, tenant_id)
    # First upload -> 201 Created
    res1 = client.post(
        f"/v1/work-requests/{wr_id}/uploads",
        headers=headers,
        json={
            "original_filename": "doc1.pdf",
            "byte_size": len(dummy_content),
            "mime_type": "application/pdf",
            "sha256": sha256,
        },
    )
    assert res1.status_code == 201
    orig_doc_id = res1.json()["document_id"]

    # Second upload with same SHA-256 -> 200 OK with existing ID and document.resubmitted audit
    headers["Idempotency-Key"] = f"idemp-{uuid.uuid4()}"
    res2 = client.post(
        f"/v1/work-requests/{wr_id}/uploads",
        headers=headers,
        json={
            "original_filename": "doc2.pdf",
            "byte_size": len(dummy_content),
            "mime_type": "application/pdf",
            "sha256": sha256,
        },
    )
    assert res2.status_code == 200
    res2_data = res2.json()
    assert res2_data["document_id"] == orig_doc_id
    assert res2_data["resubmitted"] is True

    # Verify audit event document.resubmitted logged in audit chain
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT action, resource_id, data
            FROM audit_events
            WHERE tenant_id = %s AND action = 'document.resubmitted';
            """,
            (tenant_id,),
        )
        audit_row = cur.fetchone()
        assert audit_row is not None
        assert audit_row[0] == "document.resubmitted"
        assert audit_row[1] == orig_doc_id
        assert audit_row[2]["sha256"] == sha256


def test_same_file_different_client_entities_creates_two_separate_documents(db_conn: psycopg.Connection):
    """Uploading the exact same file for client A and client B in one tenant
    creates two separate documents; neither response reveals the other's id.
    Exact duplicate scope is (tenant_id, client_entity_id, sha256).
    """
    client = TestClient(app)
    tenant_id = seed_tenant(db_conn, "Cabinet Multiclient Ingestion")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client_a_id = create_client_entity(db_conn, tenant_id, "Client Alpha SARL", actor_id=str(user_id)).id
    client_b_id = create_client_entity(db_conn, tenant_id, "Client Beta SARL", actor_id=str(user_id)).id

    p_a_id = open_accounting_period(
        db_conn,
        tenant_id,
        client_a_id,
        actor_id=str(user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    p_b_id = open_accounting_period(
        db_conn,
        tenant_id,
        client_b_id,
        actor_id=str(user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]

    wr_a_id = _seed_work_request(db_conn, tenant_id, client_a_id, p_a_id)
    wr_b_id = _seed_work_request(db_conn, tenant_id, client_b_id, p_b_id)

    shared_content = b"%PDF-1.4 Identical Shared Supplier Invoice Content"
    content_sha256 = hashlib.sha256(shared_content).hexdigest()

    # Upload for Client A -> 201 Created
    headers_a = _auth_headers(sub, tenant_id)
    res_a = client.post(
        f"/v1/work-requests/{wr_a_id}/uploads",
        headers=headers_a,
        json={
            "original_filename": "shared_invoice.pdf",
            "byte_size": len(shared_content),
            "mime_type": "application/pdf",
            "sha256": content_sha256,
        },
    )
    assert res_a.status_code == 201
    doc_a_id = res_a.json()["document_id"]
    assert res_a.json()["resubmitted"] is False

    # Upload identical file for Client B -> 201 Created (NOT 200 duplicate, NOT 409)
    headers_b = _auth_headers(sub, tenant_id)
    headers_b["Idempotency-Key"] = f"idemp-{uuid.uuid4()}"
    res_b = client.post(
        f"/v1/work-requests/{wr_b_id}/uploads",
        headers=headers_b,
        json={
            "original_filename": "shared_invoice.pdf",
            "byte_size": len(shared_content),
            "mime_type": "application/pdf",
            "sha256": content_sha256,
        },
    )
    assert res_b.status_code == 201
    doc_b_id = res_b.json()["document_id"]
    assert res_b.json()["resubmitted"] is False

    # Separate documents created; neither response reveals the other's id
    assert doc_a_id != doc_b_id
    assert doc_b_id not in json.dumps(res_a.json())
    assert doc_a_id not in json.dumps(res_b.json())


def test_malware_quarantined_with_immutable_evidence(db_conn: psycopg.Connection):
    """Files containing EICAR test signature are quarantined with an append-only evidence record."""
    client = TestClient(app)
    tenant_id = seed_tenant(db_conn, "Cabinet Test Malware")
    sub = f"security-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    c_id = create_client_entity(db_conn, tenant_id, "Client Sécurité", actor_id=str(user_id)).id
    p_id = open_accounting_period(
        db_conn,
        tenant_id,
        c_id,
        actor_id=str(user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    wr_id = _seed_work_request(db_conn, tenant_id, c_id, p_id)

    malicious_payload = b"Sample Invoice Prefix\n" + EICAR_SIGNATURE
    sha256 = hashlib.sha256(malicious_payload).hexdigest()

    headers = _auth_headers(sub, tenant_id)
    init_res = client.post(
        f"/v1/work-requests/{wr_id}/uploads",
        headers=headers,
        json={
            "original_filename": "infected.pdf",
            "byte_size": len(malicious_payload),
            "mime_type": "application/pdf",
            "sha256": sha256,
        },
    )
    assert init_res.status_code == 201
    doc_id = init_res.json()["document_id"]
    object_key = init_res.json()["object_key"]

    storage = get_storage()
    storage.put_object(object_key, malicious_payload, "application/pdf")

    # Complete upload should detect malware and quarantine
    headers["Idempotency-Key"] = f"idemp-{uuid.uuid4()}"
    comp_res = client.post(f"/v1/documents/{doc_id}:complete-upload", headers=headers)
    assert comp_res.status_code == 422
    assert "quarantined" in comp_res.text.lower()

    # Verify document status in DB is 'quarantined'
    with db_conn.cursor() as cur:
        cur.execute("SELECT status FROM documents WHERE id = %s;", (uuid.UUID(doc_id),))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "quarantined"

        # Verify evidence_records row was appended
        cur.execute(
            """
            SELECT kind, payload
            FROM evidence_records
            WHERE subject_id = %s AND kind = 'malware_scan';
            """,
            (uuid.UUID(doc_id),),
        )
        ev_row = cur.fetchone()
        assert ev_row is not None
        assert ev_row[1]["is_clean"] is False
        assert ev_row[1]["threat_name"] == "EICAR_TEST_FILE"


def test_field_correction_generates_immutable_evidence(db_conn: psycopg.Connection):
    """Field corrections create an append-only evidence record and trigger re-validation."""
    client = TestClient(app)
    tenant_id = seed_tenant(db_conn, "Cabinet Correction Test")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    c_id = create_client_entity(db_conn, tenant_id, "Société Négoce", actor_id=str(user_id)).id
    p_id = open_accounting_period(
        db_conn,
        tenant_id,
        c_id,
        actor_id=str(user_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    wr_id = _seed_work_request(db_conn, tenant_id, c_id, p_id)

    incomplete_invoice = b"""
Societe Atlas SARL
FACTURE N: FAC-CORR-01
Date: 15/03/2026
Total HT: 1000.00 MAD
Total TVA: 200.00 MAD
Total TTC: 1200.00 MAD
"""
    sha256 = hashlib.sha256(incomplete_invoice).hexdigest()
    headers = _auth_headers(sub, tenant_id)

    init_res = client.post(
        f"/v1/work-requests/{wr_id}/uploads",
        headers=headers,
        json={
            "original_filename": "facture_missing_ice.pdf",
            "byte_size": len(incomplete_invoice),
            "mime_type": "application/pdf",
            "sha256": sha256,
        },
    )
    doc_id = init_res.json()["document_id"]
    object_key = init_res.json()["object_key"]
    get_storage().put_object(object_key, incomplete_invoice, "application/pdf")

    headers["Idempotency-Key"] = f"idemp-{uuid.uuid4()}"
    comp_res = client.post(f"/v1/documents/{doc_id}:complete-upload", headers=headers)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "needs_review"

    # Now accountant corrects the ICE
    headers["Idempotency-Key"] = f"idemp-{uuid.uuid4()}"
    patch_res = client.patch(
        f"/v1/documents/{doc_id}/extraction",
        headers=headers,
        json={"fields": {"supplier_ice": "001234567890123", "supplier_if": "12345678", "client_name": "Societe Negoce"}},
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["fields"]["supplier_ice"]["value"] == "001234567890123"

    # Verify evidence_records appended
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT kind, payload
            FROM evidence_records
            WHERE subject_id = %s AND kind = 'field_correction';
            """,
            (uuid.UUID(patch_data["extraction_id"]),),
        )
        ev_row = cur.fetchone()
        assert ev_row is not None
        assert "supplier_ice" in ev_row[1]["field_updates"]


def test_scope_first_and_role_permissions(db_conn: psycopg.Connection):
    """Scope-first rule returns 404 for out-of-scope; unauthorized in-scope returns 403."""
    client = TestClient(app)
    tenant1_id = seed_tenant(db_conn, "Cabinet Alpha 1")
    tenant2_id = seed_tenant(db_conn, "Cabinet Beta 2")

    owner1_sub = f"owner-{uuid.uuid4()}"
    owner1_id = seed_user(db_conn, identity_subject=owner1_sub, email=f"{owner1_sub}@alpha.ma")
    seed_membership(db_conn, owner1_id, tenant1_id, "owner")

    staff_sub = f"staff-{uuid.uuid4()}"
    staff_id = seed_user(db_conn, identity_subject=staff_sub, email=f"{staff_sub}@alpha.ma")
    seed_membership(db_conn, staff_id, tenant1_id, "staff")

    op_sub = f"operator-{uuid.uuid4()}"
    op_id = seed_user(db_conn, identity_subject=op_sub, email=f"{op_sub}@avenel.ma")
    owner2_sub = f"owner2-{uuid.uuid4()}"
    owner2_id = seed_user(db_conn, identity_subject=owner2_sub, email=f"{owner2_sub}@beta.ma")
    seed_membership(db_conn, owner2_id, tenant2_id, "owner")

    grant_operator_access(
        conn=db_conn,
        tenant_id=tenant1_id,
        granter_user_id=owner1_id,
        operator_user_id=op_id,
        duration_hours=24.0,
    )

    set_rls_context(db_conn, tenant1_id, owner1_id)
    c1_id = create_client_entity(db_conn, tenant1_id, "Client Alpha", actor_id=str(owner1_id)).id
    p1_id = open_accounting_period(
        db_conn,
        tenant1_id,
        c1_id,
        actor_id=str(owner1_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    wr1 = _seed_work_request(db_conn, tenant1_id, c1_id, p1_id)

    set_rls_context(db_conn, tenant2_id, owner2_id)
    c2_id = create_client_entity(db_conn, tenant2_id, "Client Beta", actor_id=str(owner2_id)).id
    p2_id = open_accounting_period(
        db_conn,
        tenant2_id,
        c2_id,
        actor_id=str(owner2_id),
        period_code="2026-03",
        starts_on=datetime.date(2026, 3, 1),
        ends_on=datetime.date(2026, 3, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )["id"]
    wr2 = _seed_work_request(db_conn, tenant2_id, c2_id, p2_id)

    # 1. Staff accessing Tenant 2's work request -> 404 Not Found (Scope-first)
    headers_staff = _auth_headers(staff_sub, tenant1_id)
    res_cross = client.get(f"/v1/work-requests/{wr2}", headers=headers_staff)
    assert res_cross.status_code == 404

    # 2. Operator attempting to upload document to Tenant 1 -> 403 Forbidden (in-scope action forbidden)
    headers_op = _auth_headers(op_sub, tenant1_id)
    res_op = client.post(
        f"/v1/work-requests/{wr1}/uploads",
        headers=headers_op,
        json={
            "original_filename": "test.pdf",
            "byte_size": 100,
            "mime_type": "application/pdf",
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    assert res_op.status_code == 403
