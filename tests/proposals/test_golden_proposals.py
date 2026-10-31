"""Golden tests for each invoice type per ARCHITECTURE.md Part G Phase 3.

Verifies:
1. Standard Purchase Invoice (ACH)
2. Multi-Rate Purchase Invoice (ACH)
3. Sales Invoice (VEN)
4. Purchase Credit Note (Avoir Fournisseur reversing purchase)
5. Sales Credit Note (Avoir Client reversing sale)
6. Fixed Asset Acquisition (Immobilisation, 2355 + 34551 + 4481)
7. Foreign Currency Invoice (EUR with BAM fixing rate)
8. Non-deductible VAT by cash limit (CGI art. 106-II, VAT added to charge account)
9. Non-deductible VAT by nature (CGI art. 106-I, VAT added to charge account)
10. Auto-entrepreneur supplier (no VAT lines, full TTC to charge)
11. Prorata deduction using client_entities.vat_prorata (CGI art. 104)
12. EUR invoice with residual cents (residual posted to explicit rounding line, counterparty unchanged)
13. Evidence refs validation (line with only rule refs rejected)
14. Missing approved tax mapping raises ACCOUNT_UNMAPPED (blocking)
15. Missing FX rate raises FX_RATE_MISSING (blocking)
"""

from __future__ import annotations

import datetime
import uuid
import psycopg
import pytest

from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.proposals.entry_builder import (
    ProposalGenerationBlockedError,
    build_journal_proposal,
    validate_line_evidence_refs,
)
from avenel.proposals.fx import record_fx_rate
from avenel.proposals.service import generate_and_save_proposal_for_document
from avenel.proposals.tax_mapping import seed_approved_client_tax_mappings
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

    # Seed approved tax mappings so standard tests have approved accounts
    seed_approved_client_tax_mappings(db_conn, tenant_id, client.id, approver_id=user_id)

    # Seed BAM fixing FX rate for EUR on 2026-03-15
    record_fx_rate(
        conn=db_conn,
        tenant_id=tenant_id,
        rate_date=datetime.date(2026, 3, 15),
        currency="EUR",
        rate=10.8750,
        source="bam_fixing",
        created_by=user_id,
    )

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
        "work_request_id": wr_id,
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
        "total_vat": {"value": 2500.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
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


def test_golden_purchase_credit_note_reversing_purchase(db_conn: psycopg.Connection, proposal_test_env: dict):
    """4. Golden test: Credit note reversing a purchase (Avoir fournisseur)."""
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

    # Debit Fournisseur (2 400 MAD) - Reverses payable
    assert entry.lines[0].account_code == "4411"
    assert entry.lines[0].debit_mad == 2400.00

    # Credit Charge (2 000 MAD) - Reverses expense
    assert entry.lines[1].account_code == "6111"
    assert entry.lines[1].credit_mad == 2000.00

    # Credit TVA récupérable régularisée (400 MAD) - Reverses input VAT
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


def test_golden_non_deductible_vat_by_cash_limit(db_conn: psycopg.Connection, proposal_test_env: dict):
    """8. Golden test: Non-deductible VAT by cash limit (VAT added to charge account).

    CGI art. 106-II: Cash payment exceeding daily cash limit (5 000 MAD) makes VAT non-deductible.
    VAT is added to the charge account (6111), no VAT line is generated, and issue VAT_NOT_DEDUCTIBLE_CASH_LIMIT is flagged.
    """
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "CASH-2026-001", "page": 1},
        "invoice_date": {"value": "2026-03-12", "page": 1},
        "supplier_name": {"value": "Quincaillerie Moderne", "page": 1},
        "supplier_ice": {"value": "001234567890123", "page": 1},
        "currency": {"value": "MAD"},
        "payment_method": {"value": "espèces"},
        "total_ht": {"value": 6000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 1200.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 7200.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
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

    # Must generate 2 lines: Charge (debit full TTC 7 200) and Supplier (credit 7 200).
    # NO line for 34552!
    assert len(entry.lines) == 2
    assert entry.lines[0].account_code == "6111"
    assert entry.lines[0].debit_mad == 7200.00
    assert entry.lines[0].credit_mad == 0.00

    assert entry.lines[1].account_code == "4411"
    assert entry.lines[1].credit_mad == 7200.00
    assert entry.lines[1].debit_mad == 0.00

    # Rule ref and detected issues
    assert "vat.deduction.cash_limit.daily" in entry.rule_refs
    issue_codes = [iss["code"] for iss in entry.detected_issues]
    assert "VAT_NOT_DEDUCTIBLE_CASH_LIMIT" in issue_codes
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_non_deductible_vat_by_nature(db_conn: psycopg.Connection, proposal_test_env: dict):
    """9. Golden test: Non-deductible VAT by nature (VAT added to charge account).

    CGI art. 106-I: Non-deductible expense natures (e.g. passenger vehicles, gifts).
    VAT is added to the charge account, no VAT line is generated, issue VAT_NOT_DEDUCTIBLE_BY_NATURE is flagged.
    """
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "NAT-2026-002", "page": 1},
        "invoice_date": {"value": "2026-03-14", "page": 1},
        "supplier_name": {"value": "Location Véhicules Tourisme SARL", "page": 1},
        "supplier_ice": {"value": "001234567890123", "page": 1},
        "currency": {"value": "MAD"},
        "expense_nature": {"value": "passenger_vehicles"},
        "total_ht": {"value": 15000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 3000.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 18000.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
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

    assert len(entry.lines) == 2
    assert entry.lines[0].account_code in ("6111", "6131")  # Charge account
    assert entry.lines[0].debit_mad == 18000.00
    assert entry.lines[1].account_code == "4411"
    assert entry.lines[1].credit_mad == 18000.00

    assert "vat.deduction.exclusions_by_nature" in entry.rule_refs
    issue_codes = [iss["code"] for iss in entry.detected_issues]
    assert "VAT_NOT_DEDUCTIBLE_BY_NATURE" in issue_codes
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_auto_entrepreneur_supplier_no_vat_lines(db_conn: psycopg.Connection, proposal_test_env: dict):
    """10. Golden test: Auto-entrepreneur supplier (no VAT lines).

    Loi 114-13 / CGI art. 89: Auto-entrepreneurs cannot charge VAT.
    Full TTC is debited to the charge account, no VAT lines, issue VAT_ON_AUTO_ENTREPRENEUR_INVOICE is flagged if VAT was stated.
    """
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    mock_extracted = {
        "invoice_number": {"value": "AE-2026-007", "page": 1},
        "invoice_date": {"value": "2026-03-16", "page": 1},
        "supplier_name": {"value": "Karim Benani Auto-Entrepreneur", "page": 1},
        "supplier_is_auto_entrepreneur": {"value": True},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 8000.00, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 1600.00, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 9600.00, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
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

    assert len(entry.lines) == 2
    assert entry.lines[0].account_code == "6111"
    assert entry.lines[0].debit_mad == 9600.00
    assert entry.lines[1].account_code == "4411"
    assert entry.lines[1].credit_mad == 9600.00

    assert "invoice.auto_entrepreneur.vat_forbidden" in entry.rule_refs
    issue_codes = [iss["code"] for iss in entry.detected_issues]
    assert "VAT_ON_AUTO_ENTREPRENEUR_INVOICE" in issue_codes
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)


def test_golden_prorata_deduction_using_client_entities_vat_prorata(
    db_conn: psycopg.Connection, proposal_test_env: dict
):
    """11. Golden test: Prorata deduction using client_entities.vat_prorata (CGI art. 104).

    When client entity has vat_prorata = 0.80 (80%):
    Deductible VAT = 2 000 * 0.80 = 1 600 MAD (debited to 34552).
    Non-deductible VAT = 2 000 - 1 600 = 400 MAD (added to charge account 6111).
    Charge debit = 10 000 + 400 = 10 400 MAD.
    Fournisseur credit = 12 000 MAD. Strict balance: 10400 + 1600 == 12000.
    """
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    # Update client entity vat_prorata to 0.8000
    with db_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE client_entities
            SET vat_prorata = 0.8000
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, client_id),
        )

    mock_extracted = {
        "invoice_number": {"value": "PRO-2026-001", "page": 1},
        "invoice_date": {"value": "2026-03-18", "page": 1},
        "supplier_name": {"value": "Fournisseur Prorata", "page": 1},
        "supplier_ice": {"value": "001234567890123", "page": 1},
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

    assert len(entry.lines) == 3

    # Line 1: Charge (10 000 HT + 400 non-deductible VAT = 10 400 MAD)
    l1 = entry.lines[0]
    assert l1.account_code == "6111"
    assert l1.debit_mad == 10400.00

    # Line 2: Deductible VAT at 80% prorata (1 600 MAD)
    l2 = entry.lines[1]
    assert l2.account_code == "34552"
    assert l2.debit_mad == 1600.00

    # Line 3: Supplier Payable (12 000 MAD)
    l3 = entry.lines[2]
    assert l3.account_code == "4411"
    assert l3.credit_mad == 12000.00

    assert "vat.deduction.prorata" in entry.rule_refs
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)
    assert sum(l.debit_mad for l in entry.lines) == 12000.00


def test_golden_foreign_currency_eur_with_residual(db_conn: psycopg.Connection, proposal_test_env: dict):
    """12. Golden test: EUR invoice with residual cents.

    Phase 3 Item 1: Post residual cents to explicit rounding line (direction 'rounding' from
    client_tax_mappings or pack default marked needs_expert), NEVER to the counterparty account.
    Counterparty line must strictly equal invoice TTC converted at the stated rate.
    """
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]
    doc_id = uuid.uuid4()

    # Seed fixing rate for 2026-03-20: 10.8523
    record_fx_rate(
        conn=db_conn,
        tenant_id=tenant_id,
        rate_date=datetime.date(2026, 3, 20),
        currency="EUR",
        rate=10.8523,
        source="bam_fixing",
        created_by=user_id,
    )

    # 100.05 EUR HT * 10.8523 = 1085.772615 -> 1085.77 MAD
    # 20.01 EUR TVA * 10.8523 = 217.154523 -> 217.15 MAD
    # Sum of debits = 1302.92 MAD
    # Counterparty: 120.06 EUR TTC * 10.8523 = 1302.927138 -> 1302.93 MAD
    # Imbalance: 0.01 MAD residual!
    mock_extracted = {
        "invoice_number": {"value": "EUR-RESID-01", "page": 1},
        "invoice_date": {"value": "2026-03-20", "page": 1},
        "supplier_name": {"value": "Hosting International SAS", "page": 1},
        "supplier_ice": {"value": "000000000000000", "page": 1},
        "currency": {"value": "EUR"},
        "total_ht": {"value": 100.05, "page": 1, "bbox": [0.6, 0.7, 0.9, 0.75]},
        "total_vat": {"value": 20.01, "page": 1, "bbox": [0.6, 0.76, 0.9, 0.8]},
        "total_ttc": {"value": 120.06, "page": 1, "bbox": [0.6, 0.81, 0.9, 0.85]},
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

    # Must contain 4 lines: Charge + VAT + Counterparty + Rounding line
    assert len(entry.lines) == 4

    charge_line = next(l for l in entry.lines if l.account_code == "6111")
    vat_line = next(l for l in entry.lines if l.account_code == "34552")
    cp_line = next(l for l in entry.lines if l.account_code == "4411")
    rounding_line = next(l for l in entry.lines if l.account_code == "6588")

    assert charge_line.debit_mad == 1085.77
    assert vat_line.debit_mad == 217.15

    # Counterparty line MUST STRICTLY EQUAL invoice TTC converted at the stated rate (1302.93 MAD)
    assert cp_line.credit_mad == 1302.93

    # Residual cents (0.01 MAD) posted to explicit rounding line, NEVER to counterparty
    assert rounding_line.debit_mad == 0.01
    assert rounding_line.credit_mad == 0.00
    assert rounding_line.currency == "MAD"

    # Strict balance verified
    assert sum(l.debit_mad for l in entry.lines) == sum(l.credit_mad for l in entry.lines)
    assert sum(l.debit_mad for l in entry.lines) == 1302.93


def test_evidence_refs_with_only_rule_refs_rejected():
    """13. Service check: A line with only rule refs in evidence_refs is rejected.

    Phase 3 Item 3: evidence_refs must reference document regions or bank lines only.
    Move rule references to journal_proposals.rule_refs.
    """
    invalid_evidence = [{"rule_ref": "cgnc.seed.accounts"}]
    with pytest.raises(ValueError, match="cannot contain only rule references"):
        validate_line_evidence_refs(invalid_evidence)

    # Valid document region evidence passes
    valid_evidence = [{"document_id": str(uuid.uuid4()), "page": 1, "bbox": [0.1, 0.1, 0.4, 0.2]}]
    validate_line_evidence_refs(valid_evidence)


def test_missing_approved_tax_mapping_raises_account_unmapped(db_conn: psycopg.Connection):
    """14. Phase 3 Item 2: If no approved tax mapping exists for a needed tax_code/direction,

    create no proposal line and raise ACCOUNT_UNMAPPED (blocking).
    """
    tenant_id = seed_tenant(db_conn, "Cabinet Unmapped Test")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    # Client entity with NO tax mappings seeded
    client = create_client_entity(db_conn, tenant_id, "Client Sans Mapping SARL", actor_id=str(user_id))

    mock_extracted = {
        "invoice_number": {"value": "UNMAPPED-01"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": "Fournisseur Test"},
        "currency": {"value": "MAD"},
        "total_ht": {"value": 1000.00, "page": 1, "bbox": [0.1, 0.1, 0.4, 0.2]},
        "total_vat": {"value": 200.00, "page": 1, "bbox": [0.1, 0.2, 0.4, 0.3]},
        "total_ttc": {"value": 1200.00, "page": 1, "bbox": [0.1, 0.3, 0.4, 0.4]},
    }

    # Direct builder call raises ProposalGenerationBlockedError
    with pytest.raises(ProposalGenerationBlockedError) as exc_info:
        build_journal_proposal(
            conn=db_conn,
            tenant_id=tenant_id,
            client_entity_id=client.id,
            document_id=uuid.uuid4(),
            doc_type="invoice_purchase",
            extracted_fields=mock_extracted,
        )
    assert exc_info.value.code == "ACCOUNT_UNMAPPED"


def test_missing_fx_rate_raises_fx_rate_missing(db_conn: psycopg.Connection, proposal_test_env: dict):
    """15. Phase 3 Item 7: Missing FX rate in fx_rates table raises FX_RATE_MISSING (blocking)."""
    tenant_id = proposal_test_env["tenant_id"]
    client_id = proposal_test_env["client_id"]
    user_id = proposal_test_env["user_id"]

    # Foreign invoice in USD on 2026-03-25 with NO rate recorded in fx_rates
    mock_extracted = {
        "invoice_number": {"value": "USD-NO-RATE"},
        "invoice_date": {"value": "2026-03-25"},
        "supplier_name": {"value": "US Cloud Provider Inc"},
        "currency": {"value": "USD"},
        "total_ht": {"value": 500.00, "page": 1, "bbox": [0.1, 0.1, 0.4, 0.2]},
        "total_vat": {"value": 0.00, "page": 1, "bbox": [0.1, 0.2, 0.4, 0.3]},
        "total_ttc": {"value": 500.00, "page": 1, "bbox": [0.1, 0.3, 0.4, 0.4]},
    }

    with pytest.raises(ProposalGenerationBlockedError) as exc_info:
        build_journal_proposal(
            conn=db_conn,
            tenant_id=tenant_id,
            client_entity_id=client_id,
            document_id=uuid.uuid4(),
            doc_type="invoice_purchase",
            extracted_fields=mock_extracted,
            actor_id=str(user_id),
        )
    assert exc_info.value.code == "FX_RATE_MISSING"
