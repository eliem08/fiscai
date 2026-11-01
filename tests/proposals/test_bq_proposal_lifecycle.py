"""Test full lifecycle and DB partial unique index for active BQ proposals.

Lifecycle:
1. Bank line ingested -> initial suspense proposal (revision 1, status='proposed').
2. DB partial unique index prevents creating a second active proposal for the same bank line.
3. Match accepted -> suspense proposal superseded, counterparty BQ proposal created (revision 2, status='proposed') in same transaction.
4. Match rejected -> counterparty proposal superseded, suspense proposal restored as new revision (revision 3, status='proposed').
5. At every point in the lifecycle, exactly ONE active proposal exists per bank line.
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
    reject_reconciliation_match,
)
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def bq_lifecycle_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet BQ Lifecycle Test")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Société BQ Lifecycle SARL", actor_id=str(user_id))
    seed_approved_client_tax_mappings(db_conn, tenant_id, client.id, approver_id=user_id)

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
    db_conn.commit()

    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "user_id": user_id,
        "bank_account_id": bank_acc["id"],
        "work_request_id": wr_id,
    }


def test_bq_proposal_full_lifecycle_and_db_unique_index(bq_lifecycle_env, db_conn):
    """Lifecycle test:

    1. Unmatched -> suspense proposal (rev 1).
    2. Attempting to insert a 2nd active proposal violates partial unique index.
    3. Accept match -> suspense superseded, counterparty BQ proposal created (rev 2).
    4. Reject match -> counterparty superseded, suspense restored (rev 3).
    """
    tenant_id = bq_lifecycle_env["tenant_id"]
    client_id = bq_lifecycle_env["client_id"]
    wr_id = bq_lifecycle_env["work_request_id"]
    bank_acc_id = bq_lifecycle_env["bank_account_id"]
    user_id = bq_lifecycle_env["user_id"]

    # 1. Ingest bank statement with one transaction (payment 5000 MAD)
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve_bq.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client_id, wr_id),
        )
    csv_bytes = b"""# Solde initial: 100000.00
# Solde final: 95000.00
Date,Libelle,Debit,Credit
2026-03-12,VIR FOURNISSEUR BUREAU SERVICE,5000.00,0.00
"""
    stmt_res = ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        bank_account_id=bank_acc_id,
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve_bq.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    # Fetch bank transaction ID
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM bank_transactions WHERE tenant_id = %s AND bank_statement_id = %s;",
            (tenant_id, stmt_res["statement_id"]),
        )
        bt_id = cur.fetchone()[0]

        # Verify initial suspense proposal is created
        cur.execute(
            """
            SELECT id, revision, status, rule_refs
            FROM journal_proposals
            WHERE tenant_id = %s AND source_bank_transaction_id = %s;
            """,
            (tenant_id, bt_id),
        )
        props = cur.fetchall()
        assert len(props) == 1
        suspense_prop_id, rev1, status1, rules1 = props[0]
        assert rev1 == 1
        assert status1 == "proposed"
        assert "bank.proposal.unmatched" in rules1

    # 2. Verify DB partial unique index: attempting to insert another active proposal for the same bank line fails!
    second_prop_id = uuid.uuid4()
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db_conn.transaction():
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO journal_proposals (
                        id, tenant_id, client_entity_id, work_request_id, revision,
                        journal_code, entry_date, label, source_bank_transaction_id, proposed_by, status
                    )
                    VALUES (%s, %s, %s, %s, 1, 'BQ', '2026-03-12', 'Duplicate BQ', %s, 'rules', 'proposed');
                    """,
                    (second_prop_id, tenant_id, client_id, wr_id, bt_id),
                )

    # 3. Seed invoice proposal for this supplier (5000 MAD TTC)
    inv_doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    inv_sha = f"{inv_doc_id.hex[:32]}{ver_id.hex[:32]}"
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'purchase_invoice', 'facture_bureau.pdf', 'console', 'received');
            """,
            (inv_doc_id, tenant_id, client_id, wr_id),
        )
        cur.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, client_entity_id, document_id, version_number,
                object_key, sha256, mime_type, byte_size, page_count
            ) VALUES (%s, %s, %s, %s, 1, 'obj_key_inv', %s, 'application/pdf', 1024, 1);
            """,
            (ver_id, tenant_id, client_id, inv_doc_id, inv_sha),
        )
    inv = {
        "invoice_number": {"value": "FA-BUR-2026-09"},
        "invoice_date": {"value": "2026-03-10"},
        "supplier_name": {"value": "Fournisseur Bureau Service SARL"},
        "total_ht": {"value": 4166.67},
        "total_vat": {"value": 833.33},
        "total_ttc": {"value": 5000.00},
    }
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extractions (
                id, tenant_id, document_version_id, schema_version, engine, engine_version,
                status, fields, validation
            ) VALUES (%s, %s, %s, '1.0', 'paddleocr', '2.7', 'succeeded', %s::jsonb, '{}'::jsonb);
            """,
            (uuid.uuid4(), tenant_id, ver_id, json.dumps(inv)),
        )
    generate_and_save_proposal_for_document(db_conn, tenant_id, client_id, wr_id, inv_doc_id, str(user_id))

    # 4. Generate reconciliation matches
    matches = generate_reconciliation_matches(db_conn, tenant_id, client_id, wr_id)
    assert len(matches) >= 1
    match_id = matches[0]["id"]

    # 5. Accept match -> suspense proposal superseded, counterparty BQ proposal created in same transaction
    accept_reconciliation_match(db_conn, tenant_id, match_id, actor_id=str(user_id))

    with db_conn.cursor() as cur:
        # Check all proposals for this bank line
        cur.execute(
            """
            SELECT id, revision, status, supersedes_id, rule_refs
            FROM journal_proposals
            WHERE tenant_id = %s AND source_bank_transaction_id = %s
            ORDER BY revision ASC;
            """,
            (tenant_id, bt_id),
        )
        rows = cur.fetchall()
        assert len(rows) == 2

        # Revision 1 (suspense) is now superseded
        assert rows[0][1] == 1
        assert rows[0][2] == "superseded"

        # Revision 2 (supplier payment) is now proposed and active
        p2_id, p2_rev, p2_status, p2_super, p2_rules = rows[1]
        assert p2_rev == 2
        assert p2_status == "proposed"
        assert p2_super == rows[0][0]
        assert "bank.proposal.supplier_payment" in p2_rules

        # Exactly ONE active proposal in the database
        cur.execute(
            """
            SELECT count(*)
            FROM journal_proposals
            WHERE tenant_id = %s AND source_bank_transaction_id = %s
              AND status IN ('proposed', 'edited', 'approved');
            """,
            (tenant_id, bt_id),
        )
        assert cur.fetchone()[0] == 1

    # 6. Reject match -> counterparty proposal superseded, suspense proposal restored as rev 3
    reject_reconciliation_match(db_conn, tenant_id, match_id, actor_id=str(user_id))

    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, revision, status, supersedes_id, rule_refs
            FROM journal_proposals
            WHERE tenant_id = %s AND source_bank_transaction_id = %s
            ORDER BY revision ASC;
            """,
            (tenant_id, bt_id),
        )
        rows = cur.fetchall()
        assert len(rows) == 3

        # Rev 1: superseded
        assert rows[0][1] == 1
        assert rows[0][2] == "superseded"

        # Rev 2: superseded
        assert rows[1][1] == 2
        assert rows[1][2] == "superseded"

        # Rev 3: restored suspense proposal, active
        p3_id, p3_rev, p3_status, p3_super, p3_rules = rows[2]
        assert p3_rev == 3
        assert p3_status == "proposed"
        assert p3_super == rows[1][0]
        assert "bank.proposal.unmatched" in p3_rules

        # Exactly ONE active proposal in the database
        cur.execute(
            """
            SELECT count(*)
            FROM journal_proposals
            WHERE tenant_id = %s AND source_bank_transaction_id = %s
              AND status IN ('proposed', 'edited', 'approved');
            """,
            (tenant_id, bt_id),
        )
        assert cur.fetchone()[0] == 1
