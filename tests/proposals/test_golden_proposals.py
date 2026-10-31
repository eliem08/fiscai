"""Golden tests for each invoice type per ARCHITECTURE.md Part G Phase 3.

Verifies:
1. Standard Purchase Invoice (ACH)
2. Multi-Rate Purchase Invoice (ACH)
3. Sales Invoice (VEN)
4. Purchase Credit Note (Avoir Fournisseur)
5. Sales Credit Note (Avoir Client)
6. Fixed Asset Acquisition (Immobilisation, 2355 + 34551 + 4481)
7. Foreign Currency Invoice (EUR with BAM fixing rate)
"""

from __future__ import annotations

import datetime
import uuid
import psycopg
import pytest

from avenel.clients.service import create_client_entity
from avenel.proposals.entry_builder import build_journal_proposal
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def proposal_test_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Golden Proposals")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Atlas Golden SARL", actor_id=str(user_id))
    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "user_id": user_id,
    }


def test_golden_standard_purchase_invoice(db_conn: psycopg.Connection, proposal_test_env: dict):
    """1. Golden test: Standard Purchase invoice (20% VAT) -> 6111 + 34552 + 4411."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "FA-2026-0042", "page": 1, "bbox": [0.1, 0.1, 0.3, 0.15]},
        "invoice_date": {"value": "2026-03-15", "page": 1, "bbox": [0.1, 0.2, 0.3, 0.25]},
        "supplier_ice": {"value": "001234567890123", "page": 1},
        "supplier_if": {"value": "12345678", "page": 1},
        "supplier_name": {"value": "Fournitures Générales Maroc", "page": 1},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 10000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 2000.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 12000.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="invoice_purchase",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert entry.journal_code == "ACH"
    assert entry.entry_date == datetime.date(2026, 3, 15)
    assert len(entry.lines) == 3

    # Line 1: Expense (Debit 10 000 MAD)
    l1 = entry.lines[0]
    assert l1.account_code == "6111"
    assert l1.debit_mad == 10000.00
    assert l1.credit_mad == 0.00
    assert l1.evidence_refs[0]["field"] == "total_ht"

    # Line 2: Deductible VAT on charges (Debit 2 000 MAD)
    l2 = entry.lines[1]
    assert l2.account_code == "34552"
    assert l2.debit_mad == 2000.00
    assert l2.credit_mad == 0.00
    assert l2.tax_code == "STANDARD_20"
    assert l2.evidence_refs[0]["field"] == "total_vat"

    # Line 3: Supplier Payable (Credit 12 000 MAD)
    l3 = entry.lines[2]
    assert l3.account_code == "4411"
    assert l3.debit_mad == 0.00
    assert l3.credit_mad == 12000.00
    assert l3.counterparty_id is not None
    assert l3.evidence_refs[0]["field"] == "total_ttc"

    # Balancing invariant
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_multi_rate_purchase_invoice(db_conn: psycopg.Connection, proposal_test_env: dict):
    """2. Golden test: Multi-rate Purchase invoice (20% and 10% VAT)."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "FA-MULTI-2026", "page": 1},
        "invoice_date": {"value": "2026-03-10", "page": 1},
        "supplier_ice": {"value": "009999999999999", "page": 1},
        "supplier_name": {"value": "Metro Distribution", "page": 1},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 15000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 2500.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},  # 2000 (at 20%) + 500 (at 10%)
        "total_ttc": {"value": 17500.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
        "vat_breakdown": {
            "value": [
                {"rate": 0.20, "base_ht": 10000.00, "vat_amount": 2000.00},
                {"rate": 0.10, "base_ht": 5000.00, "vat_amount": 500.00},
            ]
        },
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="invoice_purchase",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert entry.journal_code == "ACH"
    assert len(entry.lines) == 4  # HT + VAT_20 + VAT_10 + TTC
    assert sum(l.debit_mad for l in entry.lines) == 17500.00
    assert sum(l.credit_mad for l in entry.lines) == 17500.00


def test_golden_sales_invoice(db_conn: psycopg.Connection, proposal_test_env: dict):
    """3. Golden test: Sales invoice (VEN) -> 3421 (Clients) + 7111 (Ventes) + 4455 (TVA facturée)."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "V-2026-088", "page": 1},
        "invoice_date": {"value": "2026-03-25", "page": 1},
        "client_name": {"value": "Client Casablancais SARL", "page": 1},
        "client_ice": {"value": "001122334455667", "page": 1},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 20000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 4000.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 24000.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="invoice_sale",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert entry.journal_code == "VEN"
    assert len(entry.lines) == 3

    # Line 1: Customer Receivable (Debit 24 000 MAD)
    l1 = entry.lines[0]
    assert l1.account_code == "3421"
    assert l1.debit_mad == 24000.00
    assert l1.credit_mad == 0.00

    # Line 2: Revenue (Credit 20 000 MAD)
    l2 = entry.lines[1]
    assert l2.account_code == "7111"
    assert l2.debit_mad == 0.00
    assert l2.credit_mad == 20000.00

    # Line 3: Collected VAT (Credit 4 000 MAD)
    l3 = entry.lines[2]
    assert l3.account_code == "4455"
    assert l3.debit_mad == 0.00
    assert l3.credit_mad == 4000.00

    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_purchase_credit_note(db_conn: psycopg.Connection, proposal_test_env: dict):
    """4. Golden test: Purchase credit note (Avoir fournisseur)."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "AV-2026-003", "page": 1},
        "invoice_date": {"value": "2026-03-28", "page": 1},
        "supplier_name": {"value": "Fournisseur Avoir", "page": 1},
        "supplier_ice": {"value": "005544332211009", "page": 1},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 2000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 400.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 2400.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="purchase_credit_note",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert entry.journal_code == "ACH"
    assert len(entry.lines) == 3

    # Debit Fournisseur (2 400 MAD)
    assert entry.lines[0].account_code == "4411"
    assert entry.lines[0].debit_mad == 2400.00

    # Credit Charge (2 000 MAD)
    assert entry.lines[1].account_code == "6111"
    assert entry.lines[1].credit_mad == 2000.00

    # Credit TVA récupérable régularisée (400 MAD)
    assert entry.lines[2].account_code == "34552"
    assert entry.lines[2].credit_mad == 400.00

    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_sales_credit_note(db_conn: psycopg.Connection, proposal_test_env: dict):
    """5. Golden test: Sales credit note (Avoir client)."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "AV-CLI-2026-01", "page": 1},
        "invoice_date": {"value": "2026-03-29", "page": 1},
        "client_name": {"value": "Client Avoir", "page": 1},
        "client_ice": {"value": "007788990011223", "page": 1},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 3000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 600.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 3600.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="sales_credit_note",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert entry.journal_code == "VEN"
    assert len(entry.lines) == 3

    # Debit Ventes (3 000 MAD)
    assert entry.lines[0].account_code == "7111"
    assert entry.lines[0].debit_mad == 3000.00

    # Debit TVA facturée régularisée (600 MAD)
    assert entry.lines[1].account_code == "4455"
    assert entry.lines[1].debit_mad == 600.00

    # Credit Client (3 600 MAD)
    assert entry.lines[2].account_code == "3421"
    assert entry.lines[2].credit_mad == 3600.00

    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_fixed_asset_acquisition(db_conn: psycopg.Connection, proposal_test_env: dict):
    """6. Golden test: Fixed asset purchase (Immobilisation) -> 2355 + 34551 + 4481."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "IMM-2026-001", "page": 1},
        "invoice_date": {"value": "2026-03-05", "page": 1},
        "supplier_name": {"value": "Dell Maroc Informatique", "page": 1},
        "supplier_ice": {"value": "003344556677889", "page": 1},
        "currency": {"value": "MAD"},
        "line_items": {"value": "Serveurs Dell PowerEdge et ordinateurs portables"},
        "total_ht": {"value": 50000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 10000.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 60000.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="fixed_asset",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert entry.journal_code == "ACH"
    assert len(entry.lines) == 3

    # Debit Classe 2 Asset (2355 Matériel informatique)
    assert entry.lines[0].account_code == "2355"
    assert entry.lines[0].debit_mad == 50000.00

    # Debit TVA sur immobilisations (34551)
    assert entry.lines[1].account_code == "34551"
    assert entry.lines[1].debit_mad == 10000.00

    # Credit Dettes sur acquisitions d'immobilisations (4481)
    assert entry.lines[2].account_code == "4481"
    assert entry.lines[2].credit_mad == 60000.00

    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_foreign_currency_eur_with_bam_rate(db_conn: psycopg.Connection, proposal_test_env: dict):
    """7. Golden test: Foreign currency purchase in EUR converted via Bank Al-Maghrib fixing rate."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "EUR-2026-999", "page": 1},
        "invoice_date": {"value": "2026-03-15", "page": 1},
        "supplier_name": {"value": "European Cloud Provider GmbH", "page": 1},
        "supplier_ice": {"value": "000000000000000", "page": 1},
        "currency": {"value": "EUR"},
        "total_ht": {"value": 1000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 200.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 1200.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
    }

    entry = build_journal_proposal(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type="invoice_purchase",
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert len(entry.lines) == 3
    # BAM rate on 2026-03-15 for EUR is 10.8750
    for line in entry.lines:
        assert line.currency == "EUR"
        assert line.fx_rate == 10.8750
        assert line.fx_source == "BAM"
        assert line.fx_rate_date == "2026-03-15"

    # Line 1: 1000 EUR * 10.8750 = 10 875.00 MAD
    assert entry.lines[0].debit_mad == 10875.00
    # Line 2: 200 EUR * 10.8750 = 2 175.00 MAD
    assert entry.lines[1].debit_mad == 2175.00
    # Line 3: 1200 EUR * 10.8750 = 13 050.00 MAD
    assert entry.lines[2].credit_mad == 13050.00

    # Invariant: Strict balancing in MAD
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)
