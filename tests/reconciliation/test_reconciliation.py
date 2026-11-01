"""Tests for bank reconciliation candidate generation and matching.

Exit criteria:
- withheld-VAT fixtures matched with the correct difference kind ('vat_withheld').
- no bank line in two accepted matches.
"""

from __future__ import annotations

import datetime
import json
import uuid
import psycopg
import pytest

from avenel.bank.rib import compute_moroccan_rib_key
from avenel.bank.service import create_bank_account, ingest_bank_statement
from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.proposals.service import generate_and_save_proposal_for_document
from avenel.proposals.tax_mapping import seed_approved_client_tax_mappings
from avenel.reconciliation.service import (
    accept_reconciliation_match,
    generate_reconciliation_matches,
    list_reconciliation_matches,
)
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def recon_test_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Reconciliation Test")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Atlas Reconciliation SARL", actor_id=str(user_id))

    # Seed approved tax mappings (including withholding account)
    seed_approved_client_tax_mappings(db_conn, tenant_id, client.id, approver_id=user_id)

    # Seed approved withholding account 3456
    with db_conn.cursor() as cur:
        # Create chart account 3456
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label)
            VALUES (%s, %s, %s, '3456', 'État - Retenue à la source TVA')
            ON CONFLICT DO NOTHING;
            """,
            (uuid.uuid4(), tenant_id, client.id),
        )
        cur.execute(
            "SELECT id FROM chart_accounts WHERE tenant_id = %s AND client_entity_id = %s AND account_code = '3456';",
            (tenant_id, client.id),
        )
        ras_acc_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO client_tax_mappings (
                id, tenant_id, client_entity_id, tax_code, direction, account_id, approved_by, approved_at
            )
            VALUES (%s, %s, %s, 'WITHHOLDING_75', 'withholding', %s, %s, now())
            ON CONFLICT DO NOTHING;
            """,
            (uuid.uuid4(), tenant_id, client.id, ras_acc_id, user_id),
        )

    # Bank account
    prefix = "0077800001234567890123"
    key = compute_moroccan_rib_key(prefix)
    bank_acc = create_bank_account(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client.id,
        rib=f"{prefix}{key:02d}",
        actor_id=str(user_id),
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
        "bank_account_id": bank_acc["id"],
        "work_request_id": wr_id,
        "period_id": period["id"],
    }


def _seed_document_and_proposal(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    wr_id: uuid.UUID,
    doc_type: str,
    extracted_fields: dict,
) -> uuid.UUID:
    """Helper to insert document, version, extraction and generate proposal."""
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    fake_sha = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64]
    doc_type_db = "purchase_invoice" if "purchase" in doc_type else "sales_invoice"

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (
                id, tenant_id, client_entity_id, work_request_id,
                doc_type, status, original_filename, source_channel
            ) VALUES (%s, %s, %s, %s, %s, 'read', 'facture.pdf', 'console');
            """,
            (doc_id, tenant_id, client_id, wr_id, doc_type_db),
        )
        cur.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, client_entity_id, document_id, version_number,
                object_key, sha256, mime_type, byte_size, page_count
            ) VALUES (%s, %s, %s, %s, 1, 'obj_key', %s, 'application/pdf', 1024, 1);
            """,
            (ver_id, tenant_id, client_id, doc_id, fake_sha),
        )
        cur.execute(
            """
            INSERT INTO extractions (
                id, tenant_id, document_version_id, schema_version, engine, engine_version,
                status, fields, validation
            ) VALUES (%s, %s, %s, '1.0', 'paddleocr', '2.7', 'succeeded', %s::jsonb, '{}'::jsonb);
            """,
            (uuid.uuid4(), tenant_id, ver_id, json.dumps(extracted_fields)),
        )

    prop = generate_and_save_proposal_for_document(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=wr_id,
        document_id=doc_id,
    )
    return uuid.UUID(str(prop["id"]))


def test_reconciliation_exact_single_match(db_conn: psycopg.Connection, recon_test_env: dict):
    """Generates exact single match with score >= 0.97."""
    tenant_id = recon_test_env["tenant_id"]
    client_id = recon_test_env["client_id"]
    bank_acc_id = recon_test_env["bank_account_id"]
    wr_id = recon_test_env["work_request_id"]
    user_id = recon_test_env["user_id"]

    # 1. Proposal: Purchase invoice 12 000 MAD TTC
    inv_fields = {
        "invoice_number": {"value": "FA-2026-100"},
        "invoice_date": {"value": "2026-03-10"},
        "supplier_name": {"value": "Atlas Fournitures SARL"},
        "supplier_ice": {"value": "001234567890123"},
        "total_ht": {"value": 10000.00},
        "total_vat": {"value": 2000.00},
        "total_ttc": {"value": 12000.00},
    }
    prop_id = _seed_document_and_proposal(db_conn, tenant_id, client_id, wr_id, "invoice_purchase", inv_fields)

    # 2. Bank statement with payment 12 000 MAD
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client_id, wr_id),
        )
    csv_bytes = b"""# Solde initial: 100000.00
# Solde final: 88000.00
Date,Libelle,Debit,Credit
2026-03-15,VIR ATLAS FOURNITURES,12000.00,0.00
"""
    ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        bank_account_id=bank_acc_id,
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    matches = generate_reconciliation_matches(db_conn, tenant_id, client_id, wr_id)
    assert len(matches) >= 1
    m = matches[0]
    assert m["score"] >= 0.97
    assert m["difference_mad"] == 0.0
    assert m["difference_kind"] is None


def test_reconciliation_withheld_vat_match_and_difference_kind(
    db_conn: psycopg.Connection, recon_test_env: dict
):
    """Exit criterion: withheld-VAT fixtures matched with the correct difference kind ('vat_withheld').

    Invoice TTC = 12 000 MAD (TVA = 2 000 MAD).
    Bank receipt = 10 500 MAD.
    Difference = 1 500 MAD == 75% of invoice TVA.
    Matched with difference_kind = 'vat_withheld'.
    """
    tenant_id = recon_test_env["tenant_id"]
    client_id = recon_test_env["client_id"]
    bank_acc_id = recon_test_env["bank_account_id"]
    wr_id = recon_test_env["work_request_id"]
    user_id = recon_test_env["user_id"]

    # 1. Sales invoice: TTC 12 000 MAD, TVA 2 000 MAD
    inv_fields = {
        "invoice_number": {"value": "VEN-2026-005"},
        "invoice_date": {"value": "2026-03-05"},
        "client_name": {"value": "Grand Client Public SA"},
        "total_ht": {"value": 10000.00},
        "total_vat": {"value": 2000.00},
        "total_ttc": {"value": 12000.00},
    }
    prop_id = _seed_document_and_proposal(db_conn, tenant_id, client_id, wr_id, "invoice_sale", inv_fields)

    # 2. Bank statement receipt with 75% withholding: 12 000 - 1 500 = 10 500 MAD
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve_ras.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client_id, wr_id),
        )
    csv_bytes = b"""# Solde initial: 50000.00
# Solde final: 60500.00
Date,Libelle,Debit,Credit
2026-03-18,VIR GRAND CLIENT PUBLIC NET RETENUE,0.00,10500.00
"""
    ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        bank_account_id=bank_acc_id,
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve_ras.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    matches = generate_reconciliation_matches(db_conn, tenant_id, client_id, wr_id)
    withheld_matches = [m for m in matches if m["difference_kind"] == "vat_withheld"]

    assert len(withheld_matches) == 1
    m = withheld_matches[0]
    assert m["difference_mad"] == 1500.00
    assert m["score"] >= 0.90


def test_reconciliation_withheld_vat_unmapped_account_raises_account_unmapped_issue(
    db_conn: psycopg.Connection,
):
    """When VAT withholding is detected but client has NO approved mapping for direction 'withholding',

    raises ACCOUNT_UNMAPPED blocking issue.
    """
    tenant_id = seed_tenant(db_conn, "Cabinet Unmapped Withholding")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Client Sans Retenue SARL", actor_id=str(user_id))
    # Standard tax mappings seeded, but WITHOUT withholding mapping!
    seed_approved_client_tax_mappings(db_conn, tenant_id, client.id, approver_id=user_id)

    prefix = "0117800001234567890123"
    key = compute_moroccan_rib_key(prefix)
    bank_acc = create_bank_account(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client.id,
        rib=f"{prefix}{key:02d}",
        actor_id=str(user_id),
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

    # Sales invoice 12 000 MAD TTC, 2 000 MAD TVA
    inv_fields = {
        "invoice_number": {"value": "VEN-UNMAPPED-01"},
        "invoice_date": {"value": "2026-03-05"},
        "client_name": {"value": "Client RAS"},
        "total_ht": {"value": 10000.00},
        "total_vat": {"value": 2000.00},
        "total_ttc": {"value": 12000.00},
    }
    _seed_document_and_proposal(db_conn, tenant_id, client.id, wr_id, "invoice_sale", inv_fields)

    # Bank statement with receipt 10 500 MAD (75% RAS)
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client.id, wr_id),
        )
    csv_bytes = b"""# Solde initial: 10000.00
# Solde final: 20500.00
Date,Libelle,Debit,Credit
2026-03-10,VIR CLIENT RAS,0.00,10500.00
"""
    ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client.id,
        bank_account_id=bank_acc["id"],
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    generate_reconciliation_matches(db_conn, tenant_id, client.id, wr_id)

    # Must raise ACCOUNT_UNMAPPED blocking issue
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, severity, status
            FROM issues
            WHERE tenant_id = %s AND work_request_id = %s AND code = 'ACCOUNT_UNMAPPED';
            """,
            (tenant_id, wr_id),
        )
        issue_row = cur.fetchone()
        assert issue_row is not None
        assert issue_row[0] == "ACCOUNT_UNMAPPED"
        assert issue_row[1] == "blocking"
        assert issue_row[2] == "open"


def test_reconciliation_no_bank_line_in_two_accepted_matches(
    db_conn: psycopg.Connection, recon_test_env: dict
):
    """Exit criterion: no bank line in two accepted matches.

    Verifies that accepting a match locks its bank transactions, and any attempt
    to accept another match containing the same bank transaction is rejected with an error.
    """
    tenant_id = recon_test_env["tenant_id"]
    client_id = recon_test_env["client_id"]
    bank_acc_id = recon_test_env["bank_account_id"]
    wr_id = recon_test_env["work_request_id"]
    user_id = recon_test_env["user_id"]

    # 1. Bank statement with ONE transaction of 5 000 MAD
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve_single.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client_id, wr_id),
        )
    csv_bytes = b"""# Solde initial: 50000.00
# Solde final: 45000.00
Date,Libelle,Debit,Credit
2026-03-12,VIR FOURNISSEUR UNIQUE,5000.00,0.00
"""
    stmt_res = ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        bank_account_id=bank_acc_id,
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve_single.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    # Fetch bank transaction id
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM bank_transactions WHERE tenant_id = %s AND bank_statement_id = %s LIMIT 1;",
            (tenant_id, stmt_res["statement_id"]),
        )
        bank_tx_id = cur.fetchone()[0]

    # 2. Two different proposals (e.g. Candidate A and Candidate B)
    inv_a = {
        "invoice_number": {"value": "FA-CANDIDATE-A"},
        "invoice_date": {"value": "2026-03-10"},
        "supplier_name": {"value": "Fournisseur A"},
        "total_ht": {"value": 4166.67},
        "total_vat": {"value": 833.33},
        "total_ttc": {"value": 5000.00},
    }
    prop_a = _seed_document_and_proposal(db_conn, tenant_id, client_id, wr_id, "invoice_purchase", inv_a)

    inv_b = {
        "invoice_number": {"value": "FA-CANDIDATE-B"},
        "invoice_date": {"value": "2026-03-11"},
        "supplier_name": {"value": "Fournisseur B"},
        "total_ht": {"value": 4166.67},
        "total_vat": {"value": 833.33},
        "total_ttc": {"value": 5000.00},
    }
    prop_b = _seed_document_and_proposal(db_conn, tenant_id, client_id, wr_id, "invoice_purchase", inv_b)

    # 3. Create candidate Match 1 (proposed)
    match_1_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reconciliation_matches (id, tenant_id, client_entity_id, work_request_id, status, score, reasons, difference_mad)
            VALUES (%s, %s, %s, %s, 'proposed', 0.95, '["Montant identique"]'::jsonb, 0.0);
            """,
            (match_1_id, tenant_id, client_id, wr_id),
        )
        cur.execute(
            """
            INSERT INTO reconciliation_match_items (id, tenant_id, client_entity_id, match_id, bank_transaction_id, amount_mad)
            VALUES (%s, %s, %s, %s, %s, -5000.00);
            """,
            (uuid.uuid4(), tenant_id, client_id, match_1_id, bank_tx_id),
        )
        cur.execute(
            """
            INSERT INTO reconciliation_match_items (id, tenant_id, client_entity_id, match_id, journal_proposal_id, amount_mad)
            VALUES (%s, %s, %s, %s, %s, 5000.00);
            """,
            (uuid.uuid4(), tenant_id, client_id, match_1_id, prop_a),
        )

    # 4. Two proposed candidates for the same bank line COEXIST (fix spec bug D.3)
    match_2_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reconciliation_matches (id, tenant_id, client_entity_id, work_request_id, status, score, reasons, difference_mad)
            VALUES (%s, %s, %s, %s, 'proposed', 0.95, '["Montant identique rival"]'::jsonb, 0.0);
            """,
            (match_2_id, tenant_id, client_id, wr_id),
        )
        cur.execute(
            """
            INSERT INTO reconciliation_match_items (id, tenant_id, client_entity_id, match_id, bank_transaction_id, amount_mad)
            VALUES (%s, %s, %s, %s, %s, -5000.00);
            """,
            (uuid.uuid4(), tenant_id, client_id, match_2_id, bank_tx_id),
        )
        cur.execute(
            """
            INSERT INTO reconciliation_match_items (id, tenant_id, client_entity_id, match_id, journal_proposal_id, amount_mad)
            VALUES (%s, %s, %s, %s, %s, 5000.00);
            """,
            (uuid.uuid4(), tenant_id, client_id, match_2_id, prop_b),
        )

    # Assert both candidates coexist with match_status = 'proposed'
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM reconciliation_match_items WHERE tenant_id = %s AND bank_transaction_id = %s;",
            (tenant_id, bank_tx_id),
        )
        assert cur.fetchone()[0] == 2

    # 5. Accepting a second match for an already-matched line FAILS
    # Accept Match 1
    res1 = accept_reconciliation_match(db_conn, tenant_id, match_1_id, actor_id=str(user_id))
    assert res1["status"] == "accepted"

    # Accepting Match 2 must fail (app logic and DB unique index block it)
    with pytest.raises((ValueError, psycopg.errors.UniqueViolation)):
        accept_reconciliation_match(db_conn, tenant_id, match_2_id, actor_id=str(user_id))

    # 6. A rejected match does NOT block a new match
    # Reject Match 1
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE reconciliation_matches SET status = 'rejected' WHERE tenant_id = %s AND id = %s;",
            (tenant_id, match_1_id),
        )

    # Now Match 2 can be accepted cleanly!
    res2 = accept_reconciliation_match(db_conn, tenant_id, match_2_id, actor_id=str(user_id))
    assert res2["status"] == "accepted"

    # Invariant verified: exactly ONE accepted match for bank_tx_id
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM reconciliation_match_items
            WHERE tenant_id = %s AND bank_transaction_id = %s AND match_status = 'accepted';
            """,
            (tenant_id, bank_tx_id),
        )
        assert cur.fetchone()[0] == 1


def test_reconciliation_withholding_other_5_pct_is_detected(recon_test_env, db_conn):
    """LF 2026 5% IS withholding on listed services/rents produces difference_kind 'withholding_other'."""
    tenant_id = recon_test_env["tenant_id"]
    client_id = recon_test_env["client_id"]
    wr_id = recon_test_env["work_request_id"]
    bank_acc_id = recon_test_env["bank_account_id"]
    user_id = recon_test_env["user_id"]

    # 1. Invoice TTC: 10,000.00 MAD (5% IS withholding = 500.00 MAD)
    inv = {
        "invoice_number": {"value": "FA-SERVICE-2026-001"},
        "invoice_date": {"value": "2026-03-05"},
        "supplier_name": {"value": "Client Prestation SARL"},
        "total_ht": {"value": 8333.33},
        "total_vat": {"value": 1666.67},
        "total_ttc": {"value": 10000.00},
    }
    prop_id = _seed_document_and_proposal(db_conn, tenant_id, client_id, wr_id, "invoice_sale", inv)

    # 2. Bank receipt of 9,500.00 MAD (10,000 - 500)
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve_is_5pct.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client_id, wr_id),
        )
    csv_bytes = b"""# Solde initial: 100000.00
# Solde final: 109500.00
Date,Libelle,Debit,Credit
2026-03-08,VIR ENCAISSEMENT CLIENT SERVICE PRESTATION,0.00,9500.00
"""
    ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        bank_account_id=bank_acc_id,
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve_is_5pct.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    matches = generate_reconciliation_matches(db_conn, tenant_id, client_id, wr_id, date_window_days=60)
    withholding_other_matches = [m for m in matches if m.get("difference_kind") == "withholding_other"]

    assert len(withholding_other_matches) == 1
    m = withholding_other_matches[0]
    assert m["difference_mad"] == 500.00
    assert m["difference_kind"] == "withholding_other"

