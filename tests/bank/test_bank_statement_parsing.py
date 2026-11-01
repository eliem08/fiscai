"""Tests for bank statement parsing and mathematical balance verification.

Exit criterion:
- balance-break fixtures detected (BANK_BALANCE_BREAK blocking issue raised).
"""

from __future__ import annotations

import datetime
import io
import uuid
import psycopg
import pytest
import openpyxl

from avenel.bank.parser import (
    parse_bank_statement,
    parse_bank_statement_csv,
    parse_bank_statement_xlsx,
)
from avenel.bank.rib import compute_moroccan_rib_key
from avenel.bank.service import create_bank_account, ingest_bank_statement
from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def bank_test_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Bank Test")
    sub = f"accountant-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "accountant")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Atlas Trading SARL", actor_id=str(user_id))

    prefix = "0077800001234567890123"
    key = compute_moroccan_rib_key(prefix)
    valid_rib = f"{prefix}{key:02d}"

    bank_acc = create_bank_account(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client.id,
        rib=valid_rib,
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

    # Document placeholder for statement
    doc_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, source_channel, status)
            VALUES (%s, %s, %s, %s, 'bank_statement', 'releve_2026_03.csv', 'console', 'received');
            """,
            (doc_id, tenant_id, client.id, wr_id),
        )

    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "user_id": user_id,
        "bank_account_id": bank_acc["id"],
        "work_request_id": wr_id,
        "document_id": doc_id,
    }


def test_csv_bank_statement_parsing_valid_balance():
    """Parses a valid CSV bank statement where opening + movements == closing."""
    csv_content = """# Solde initial: 100000.00
# Solde final: 125000.00
Date,Libelle,Debit,Credit
2026-03-05,VIR CLIENT ATLAS,0.00,30000.00
2026-03-10,VIR FOURNISSEUR BUREAU,5000.00,0.00
"""
    stmt = parse_bank_statement_csv(csv_content)
    assert len(stmt.transactions) == 2
    assert stmt.opening_balance == 100000.00
    assert stmt.closing_balance == 125000.00
    assert stmt.computed_closing_balance == 125000.00
    assert stmt.balance_check == "ok"
    assert stmt.has_balance_break is False


def test_csv_bank_statement_parsing_balance_break_detected():
    """Detects balance break when opening + movements != stated closing balance."""
    # Stated closing: 140000.00, but movements sum to +25000.00 -> computed: 125000.00
    csv_content = """# Solde initial: 100000.00
# Solde final: 140000.00
Date,Libelle,Debit,Credit
2026-03-05,VIR CLIENT ATLAS,0.00,30000.00
2026-03-10,VIR FOURNISSEUR BUREAU,5000.00,0.00
"""
    stmt = parse_bank_statement_csv(csv_content)
    assert len(stmt.transactions) == 2
    assert stmt.opening_balance == 100000.00
    assert stmt.closing_balance == 140000.00
    assert stmt.computed_closing_balance == 125000.00
    assert stmt.balance_difference == 15000.00
    assert stmt.balance_check == "break"
    assert stmt.has_balance_break is True


def test_xlsx_bank_statement_parsing():
    """Parses an Excel XLSX bank statement with openpyxl."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Relevé"

    ws.append(["Solde initial", 50000.00])
    ws.append(["Solde final", 62000.00])
    ws.append([])
    ws.append(["Date", "Libellé", "Débit", "Crédit"])
    ws.append(["2026-03-02", "Encaissement client", None, 15000.00])
    ws.append(["2026-03-04", "Règlement loyer", 3000.00, None])

    bio = io.BytesIO()
    wb.save(bio)
    xlsx_bytes = bio.getvalue()

    stmt = parse_bank_statement_xlsx(xlsx_bytes)
    assert len(stmt.transactions) == 2
    assert stmt.opening_balance == 50000.00
    assert stmt.closing_balance == 62000.00
    assert stmt.computed_closing_balance == 62000.00
    assert stmt.balance_check == "ok"


def test_ingest_statement_with_balance_break_raises_blocking_issue(
    db_conn: psycopg.Connection, bank_test_env: dict
):
    """Exit criterion: balance-break fixtures detected.

    Statement with broken balance stores balance_check = 'break' and creates
    a blocking issue BANK_BALANCE_BREAK in the issues table.
    """
    tenant_id = bank_test_env["tenant_id"]
    client_id = bank_test_env["client_id"]
    bank_acc_id = bank_test_env["bank_account_id"]
    wr_id = bank_test_env["work_request_id"]
    doc_id = bank_test_env["document_id"]
    user_id = bank_test_env["user_id"]

    # CSV with 50 000 MAD break
    csv_bytes = b"""# Solde initial: 100000.00
# Solde final: 200000.00
Date,Libelle,Debit,Credit
2026-03-01,VIR DEPART,0.00,50000.00
"""
    res = ingest_bank_statement(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        bank_account_id=bank_acc_id,
        document_id=doc_id,
        file_bytes=csv_bytes,
        filename="releve_break.csv",
        work_request_id=wr_id,
        actor_id=str(user_id),
    )

    assert res["balance_check"] == "break"
    assert res["difference"] == 50000.00
    assert res["issue_id"] is not None

    # Verify database issue row
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, severity, status, subject_document_id
            FROM issues
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, res["issue_id"]),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "BANK_BALANCE_BREAK"
        assert row[1] == "blocking"
        assert row[2] == "open"
        assert row[3] == doc_id


def test_bank_statement_fixture_stubs_awaiting_real_samples():
    """Verify that all 4 Moroccan bank layout fixture stubs exist and conform to schema.

    Banks covered: Attijariwafa bank (007), Banque Populaire (013),
    Bank of Africa (011), and CIH Bank (230).
    All are marked status='awaiting_real_samples'.
    """
    import json
    import pathlib
    from avenel.bank.rib import get_known_bank_codes

    fixtures_dir = pathlib.Path(__file__).parent.parent / "fixtures" / "bank_statements"
    expected_banks = {
        "007": "attijariwafa_stub.json",
        "013": "bp_stub.json",
        "011": "bank_of_africa_stub.json",
        "230": "cih_stub.json",
    }

    known_codes = get_known_bank_codes()

    for bank_code, filename in expected_banks.items():
        assert bank_code in known_codes, f"Bank code {bank_code} must be defined in jurisdiction pack"
        stub_file = fixtures_dir / filename
        assert stub_file.exists(), f"Stub file {filename} must exist"

        data = json.loads(stub_file.read_text(encoding="utf-8"))
        assert data["bank_code"] == bank_code
        assert data["status"] == "awaiting_real_samples"
        assert "layout" in data
        layout = data["layout"]
        assert "header_identifiers" in layout and len(layout["header_identifiers"]) > 0
        assert "rib_pattern" in layout
        assert "opening_balance_labels" in layout
        assert "closing_balance_labels" in layout
        assert "table_columns" in layout
        assert len(data.get("sample_stub_lines", [])) >= 5

