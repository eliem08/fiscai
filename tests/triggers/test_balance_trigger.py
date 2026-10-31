"""Tests for proposal balancing trigger per ARCHITECTURE.md C.4 Invariant 3 & D.3."""

import uuid
from datetime import date

import psycopg
import pytest


def _setup_accounting_context(conn: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Helper to set up tenant, client entity, period, accounts, and work request."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    acc1_id = uuid.uuid4()
    acc2_id = uuid.uuid4()

    with conn.cursor() as cur:
        # Tenant
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Test Balance Tenant');", (t_id,))
        # Client entity
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Client Balance');", (c_id, t_id))
        # Period
        cur.execute(
            """INSERT INTO accounting_periods (id, tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, %s, '2026-09', '2026-09-01', '2026-09-30', '2026-12-31', 'MA-2026.10.1');""",
            (p_id, t_id, c_id),
        )
        # Accounts
        cur.execute(
            """INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label)
               VALUES (%s, %s, %s, '611100', 'Achats de marchandises'),
                      (%s, %s, %s, '441100', 'Fournisseurs');""",
            (acc1_id, t_id, c_id, acc2_id, t_id, c_id),
        )
        # Work request
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping');""",
            (w_id, t_id, c_id, p_id),
        )
    conn.commit()
    return t_id, c_id, p_id, w_id, acc1_id, acc2_id


def test_balanced_proposal_commits_successfully(db_conn: psycopg.Connection):
    """Proposal with >= 2 lines and balanced debit_mad == credit_mad commits cleanly."""
    t_id, c_id, _, w_id, acc1_id, acc2_id = _setup_accounting_context(db_conn)
    prop_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by)
               VALUES (%s, %s, %s, %s, 1, 'ACH', %s, 'Achat fournitures', 'rules');""",
            (prop_id, t_id, c_id, w_id, date(2026, 9, 15)),
        )
        # Line 1: Debit 1200.00
        cur.execute(
            """INSERT INTO journal_lines (tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, 1, %s, '611100', 'Achats', 'MAD', 1200.00, 0, 1200.00, 0, 1);""",
            (t_id, c_id, prop_id, acc1_id),
        )
        # Line 2: Credit 1200.00
        cur.execute(
            """INSERT INTO journal_lines (tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, 2, %s, '441100', 'Fournisseurs', 'MAD', 0, 1200.00, 0, 1200.00, 1);""",
            (t_id, c_id, prop_id, acc2_id),
        )
    # Commit must succeed because deferred trigger verifies proposal is balanced
    db_conn.commit()


def test_unbalanced_proposal_fails_on_commit(db_conn: psycopg.Connection):
    """Proposal with debit_mad != credit_mad must fail at transaction commit with error 23514."""
    t_id, c_id, _, w_id, acc1_id, acc2_id = _setup_accounting_context(db_conn)
    prop_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by)
               VALUES (%s, %s, %s, %s, 1, 'ACH', %s, 'Achat fournitures', 'rules');""",
            (prop_id, t_id, c_id, w_id, date(2026, 9, 15)),
        )
        # Line 1: Debit 1200.00
        cur.execute(
            """INSERT INTO journal_lines (tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, 1, %s, '611100', 'Achats', 'MAD', 1200.00, 0, 1200.00, 0, 1);""",
            (t_id, c_id, prop_id, acc1_id),
        )
        # Line 2: Credit 1000.00 (Unbalanced: 1200 != 1000)
        cur.execute(
            """INSERT INTO journal_lines (tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, 2, %s, '441100', 'Fournisseurs', 'MAD', 0, 1000.00, 0, 1000.00, 1);""",
            (t_id, c_id, prop_id, acc2_id),
        )

    with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
        db_conn.commit()
    assert "unbalanced" in str(exc_info.value).lower()
    db_conn.rollback()


def test_proposal_with_single_line_fails_on_commit(db_conn: psycopg.Connection):
    """Proposal with fewer than 2 lines must fail at commit."""
    t_id, c_id, _, w_id, acc1_id, _ = _setup_accounting_context(db_conn)
    prop_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by)
               VALUES (%s, %s, %s, %s, 1, 'ACH', %s, 'Single line', 'rules');""",
            (prop_id, t_id, c_id, w_id, date(2026, 9, 15)),
        )
        cur.execute(
            """INSERT INTO journal_lines (tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, 1, %s, '611100', 'Achats', 'MAD', 500.00, 0, 500.00, 0, 1);""",
            (t_id, c_id, prop_id, acc1_id),
        )

    with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
        db_conn.commit()
    assert "lines=1" in str(exc_info.value)
    db_conn.rollback()


def test_line_with_both_debit_and_credit_rejected(db_conn: psycopg.Connection):
    """Line cannot have both debit and credit (Invariant 4)."""
    t_id, c_id, _, w_id, acc1_id, _ = _setup_accounting_context(db_conn)
    prop_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by)
               VALUES (%s, %s, %s, %s, 1, 'ACH', %s, 'Invalid line test', 'rules');""",
            (prop_id, t_id, c_id, w_id, date(2026, 9, 15)),
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """INSERT INTO journal_lines (tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
                   VALUES (%s, %s, %s, 1, %s, '611100', 'Invalid', 'MAD', 500.00, 500.00, 500.00, 500.00, 1);""",
                (t_id, c_id, prop_id, acc1_id),
            )
    db_conn.rollback()
