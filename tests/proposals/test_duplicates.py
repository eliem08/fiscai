"""Tests for probable duplicate detection per ARCHITECTURE.md Part G & Part H.

Gate: Probable duplicate recall >= 99% on fixtures.
Enforces:
- Same counterparty AND (same invoice number OR (same TTC AND |date delta| <= window from pack)).
- Window lives in the pack (`invoice.duplicate_window_days`).
- Issue code `DUPLICATE_PROBABLE` from issues.yaml.
- Negative tests:
  1. Monthly rent: same amount same supplier different invoice numbers 30 days apart is NOT flagged
     when numbers differ and dates are a month apart beyond the window.
  2. Two different suppliers same amount never flagged.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
import psycopg
import pytest

from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.proposals.duplicates import (
    ProbableDuplicateMatch,
    detect_probable_duplicates,
    get_duplicate_window_days,
    record_duplicate_issues_if_any,
)
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def duplicate_test_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Duplicate Tests")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Atlas Négoce Doublons", actor_id=str(user_id))
    period = open_accounting_period(
        db_conn,
        tenant_id,
        client.id,
        actor_id=str(user_id),
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
            (wr_id, tenant_id, client.id, period["id"]),
        )

    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "user_id": user_id,
        "period_id": period["id"],
        "work_request_id": wr_id,
    }


def _seed_document_with_extraction(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    supplier_ice: str,
    supplier_name: str,
    invoice_number: str,
    total_ttc: float,
    invoice_date: str,
    work_request_id: uuid.UUID | None = None,
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
            ) VALUES (%s, %s, %s, %s, 'test_invoice.pdf', 'read', 'purchase_invoice', 'console');
            """,
            (doc_id, tenant_id, client_id, work_request_id),
        )
        cur.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, client_entity_id, document_id, version_number,
                byte_size, sha256, mime_type, object_key
            ) VALUES (%s, %s, %s, %s, 1, 1024, %s, 'application/pdf', %s);
            """,
            (ver_id, tenant_id, client_id, doc_id, hashlib.sha256(uuid.uuid4().bytes).hexdigest(), f"docs/{doc_id}.pdf"),
        )
        fields = {
            "supplier_ice": {"value": supplier_ice},
            "supplier_name": {"value": supplier_name},
            "invoice_number": {"value": invoice_number},
            "total_ttc": {"value": total_ttc},
            "invoice_date": {"value": invoice_date},
        }
        cur.execute(
            """
            INSERT INTO extractions (
                id, tenant_id, document_version_id, schema_version,
                engine, engine_version, status, fields, validation
            ) VALUES (%s, %s, %s, 'v1', 'synthetic', '1.0', 'succeeded', %s::jsonb, '{}'::jsonb);
            """,
            (ext_id, tenant_id, ver_id, json.dumps(fields)),
        )
    return doc_id


def test_duplicate_window_reads_from_pack():
    """Window lives in the pack (invoice.duplicate_window_days)."""
    window = get_duplicate_window_days()
    assert window == 20


def test_probable_duplicate_detected_by_exact_invoice_number(db_conn: psycopg.Connection, duplicate_test_env: dict):
    """Detects probable duplicate when invoice number matches from the same supplier."""
    tenant_id = duplicate_test_env["tenant_id"]
    client_id = duplicate_test_env["client_id"]
    wr_id = duplicate_test_env["work_request_id"]

    existing_doc_id = _seed_document_with_extraction(
        conn=db_conn,
        tenant_id=tenant_id,
        client_id=client_id,
        supplier_ice="001234567890123",
        supplier_name="Fournitures Maroc",
        invoice_number="FA-2026-999",
        total_ttc=5000.00,
        invoice_date="2026-03-01",
        work_request_id=wr_id,
    )

    new_doc_id = uuid.uuid4()
    matches = detect_probable_duplicates(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        current_document_id=new_doc_id,
        supplier_ice="001234567890123",
        supplier_name="Fournitures Maroc",
        invoice_number="FA-2026-999",
        total_ttc=5000.00,
        invoice_date="2026-03-01",
    )

    assert len(matches) == 1
    assert matches[0].conflicting_document_id == existing_doc_id
    assert matches[0].match_kind == "exact_number"
    assert matches[0].confidence >= 0.99


def test_probable_duplicate_detected_by_amount_and_date_window(db_conn: psycopg.Connection, duplicate_test_env: dict):
    """Detects probable duplicate when amount matches within pack window (<= 20 days) for same supplier."""
    tenant_id = duplicate_test_env["tenant_id"]
    client_id = duplicate_test_env["client_id"]
    wr_id = duplicate_test_env["work_request_id"]

    existing_doc_id = _seed_document_with_extraction(
        conn=db_conn,
        tenant_id=tenant_id,
        client_id=client_id,
        supplier_ice="001234567890123",
        supplier_name="Fournitures Maroc",
        invoice_number="FA-100",
        total_ttc=4250.75,
        invoice_date="2026-03-10",
        work_request_id=wr_id,
    )

    new_doc_id = uuid.uuid4()
    matches = detect_probable_duplicates(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        current_document_id=new_doc_id,
        supplier_ice="001234567890123",
        supplier_name="Fournitures Maroc",
        invoice_number="DIFFERENT-NO",  # Number differs
        total_ttc=4250.75,             # Exactly matches amount
        invoice_date="2026-03-22",      # 12 days apart (<= 20 days window)
    )

    assert len(matches) == 1
    assert matches[0].conflicting_document_id == existing_doc_id
    assert matches[0].match_kind == "amount_and_date_window"
    assert matches[0].confidence >= 0.90


def test_negative_monthly_rent_30_days_apart_not_flagged(db_conn: psycopg.Connection, duplicate_test_env: dict):
    """Negative test: monthly rent same amount same supplier different invoice numbers 30 days apart

    is NOT flagged when numbers differ and dates are a month apart beyond the window.
    """
    tenant_id = duplicate_test_env["tenant_id"]
    client_id = duplicate_test_env["client_id"]
    wr_id = duplicate_test_env["work_request_id"]

    _seed_document_with_extraction(
        conn=db_conn,
        tenant_id=tenant_id,
        client_id=client_id,
        supplier_ice="002345678901234",
        supplier_name="Bailleur Immobilier SARL",
        invoice_number="LOYER-JAN-2026",
        total_ttc=15000.00,
        invoice_date="2026-01-05",
        work_request_id=wr_id,
    )

    new_doc_id = uuid.uuid4()
    # February rent: 30 days later, different invoice number
    matches = detect_probable_duplicates(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        current_document_id=new_doc_id,
        supplier_ice="002345678901234",
        supplier_name="Bailleur Immobilier SARL",
        invoice_number="LOYER-FEV-2026",
        total_ttc=15000.00,
        invoice_date="2026-02-05",  # 31 days apart (> 20 days window from pack)
    )

    assert len(matches) == 0, "Monthly recurring invoices 30 days apart must NOT be flagged as duplicates"


def test_negative_two_different_suppliers_same_amount_never_flagged(db_conn: psycopg.Connection, duplicate_test_env: dict):
    """Negative test: two different suppliers same amount never flagged."""
    tenant_id = duplicate_test_env["tenant_id"]
    client_id = duplicate_test_env["client_id"]
    wr_id = duplicate_test_env["work_request_id"]

    _seed_document_with_extraction(
        conn=db_conn,
        tenant_id=tenant_id,
        client_id=client_id,
        supplier_ice="001111111111111",
        supplier_name="Fournisseur Alpha",
        invoice_number="FAC-001",
        total_ttc=7500.00,
        invoice_date="2026-03-15",
        work_request_id=wr_id,
    )

    new_doc_id = uuid.uuid4()
    # Same amount (7500.00 MAD) on the same date, but completely different supplier
    matches = detect_probable_duplicates(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        current_document_id=new_doc_id,
        supplier_ice="002222222222222",
        supplier_name="Fournisseur Beta",
        invoice_number="FAC-001",
        total_ttc=7500.00,
        invoice_date="2026-03-15",
    )

    assert len(matches) == 0, "Invoices from different suppliers must NEVER be flagged as duplicates"


def test_record_duplicate_issues_inserts_duplicate_probable(db_conn: psycopg.Connection, duplicate_test_env: dict):
    """Confirms record_duplicate_issues_if_any inserts issue row with DUPLICATE_PROBABLE from issues.yaml."""
    tenant_id = duplicate_test_env["tenant_id"]
    client_id = duplicate_test_env["client_id"]
    wr_id = duplicate_test_env["work_request_id"]
    doc_id = uuid.uuid4()

    # Seed the subject document
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (
                id, tenant_id, client_entity_id, work_request_id,
                original_filename, status, doc_type, source_channel
            ) VALUES (%s, %s, %s, %s, 'subject.pdf', 'received', 'purchase_invoice', 'console');
            """,
            (doc_id, tenant_id, client_id, wr_id),
        )

    conflicting_id = uuid.uuid4()
    fake_matches = [
        ProbableDuplicateMatch(
            conflicting_document_id=conflicting_id,
            conflicting_proposal_id=None,
            conflicting_invoice_number="FA-999",
            conflicting_total_ttc=1000.0,
            conflicting_invoice_date="2026-03-01",
            match_kind="exact_number",
            confidence=0.99,
            reason="Même numéro détecté",
        )
    ]

    record_duplicate_issues_if_any(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=wr_id,
        document_id=doc_id,
        matches=fake_matches,
    )

    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, severity, status, evidence_refs
            FROM issues
            WHERE tenant_id = %s AND subject_document_id = %s;
            """,
            (tenant_id, doc_id),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "DUPLICATE_PROBABLE", "Issue code must be DUPLICATE_PROBABLE per issues.yaml"
        assert row[1] == "review"
        assert row[2] == "open"
        assert str(conflicting_id) in json.dumps(row[3])
