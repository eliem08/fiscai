"""Tests for append-only immutability triggers per ARCHITECTURE.md Rule A.2 #5, C.4 Invariant 5 & 6, D.3."""

import uuid
from datetime import date

import psycopg
import pytest


def test_audit_events_is_append_only(db_conn: psycopg.Connection):
    """UPDATE and DELETE on audit_events must be blocked by trigger."""
    t_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Audit');", (t_id,))
        cur.execute(
            """INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
               VALUES (%s, 'system', 'system', 'test.action', 'tenant', %s, '{}'::jsonb)
               RETURNING id;""",
            (t_id, str(t_id)),
        )
        event_id = cur.fetchone()[0]
    db_conn.commit()

    # Attempt UPDATE
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("UPDATE audit_events SET action = 'modified' WHERE id = %s;", (event_id,))
    assert "append-only" in str(exc_info.value).lower()
    db_conn.rollback()

    # Attempt DELETE
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM audit_events WHERE id = %s;", (event_id,))
    assert "append-only" in str(exc_info.value).lower()
    db_conn.rollback()


def test_evidence_records_is_append_only(db_conn: psycopg.Connection):
    """UPDATE and DELETE on evidence_records must be blocked."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    ev_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Evidence');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Client Ev');", (c_id, t_id))
        cur.execute(
            """INSERT INTO accounting_periods (id, tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, %s, '2026-09', '2026-09-01', '2026-09-30', '2026-12-31', 'MA-2026.10.1');""",
            (p_id, t_id, c_id),
        )
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping');""",
            (w_id, t_id, c_id, p_id),
        )
        cur.execute(
            """INSERT INTO evidence_records (id, tenant_id, work_request_id, subject_type, subject_id, kind, payload, content_sha256)
               VALUES (%s, %s, %s, 'document', %s, 'malware_scan', '{\"status\":\"clean\"}'::jsonb, repeat('a', 64));""",
            (ev_id, t_id, w_id, uuid.uuid4()),
        )
    db_conn.commit()

    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("UPDATE evidence_records SET kind = 'hacked' WHERE id = %s;", (ev_id,))
    assert "append-only" in str(exc_info.value).lower()
    db_conn.rollback()

    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM evidence_records WHERE id = %s;", (ev_id,))
    assert "append-only" in str(exc_info.value).lower()
    db_conn.rollback()


def test_frozen_proposal_lines_cannot_be_mutated(db_conn: psycopg.Connection):
    """Lines of an approved, exported, or superseded proposal are immutable (Rule A.2 #5)."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    acc1_id = uuid.uuid4()
    acc2_id = uuid.uuid4()
    prop_id = uuid.uuid4()
    line_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Freeze');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Client Freeze');", (c_id, t_id))
        cur.execute(
            """INSERT INTO accounting_periods (id, tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, %s, '2026-09', '2026-09-01', '2026-09-30', '2026-12-31', 'MA-2026.10.1');""",
            (p_id, t_id, c_id),
        )
        cur.execute(
            """INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label)
               VALUES (%s, %s, %s, '611100', 'Achats'), (%s, %s, %s, '441100', 'Fournisseurs');""",
            (acc1_id, t_id, c_id, acc2_id, t_id, c_id),
        )
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping');""",
            (w_id, t_id, c_id, p_id),
        )
        cur.execute(
            """INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
               VALUES (%s, %s, %s, %s, 1, 'ACH', %s, 'Proposal', 'rules', 'approved');""",
            (prop_id, t_id, c_id, w_id, date(2026, 9, 15)),
        )
        cur.execute(
            """INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, %s, 1, %s, '611100', 'Debit Line', 'MAD', 100.00, 0, 100.00, 0, 1),
                      (%s, %s, %s, %s, 2, %s, '441100', 'Credit Line', 'MAD', 0, 100.00, 0, 100.00, 1);""",
            (line_id, t_id, c_id, prop_id, acc1_id, uuid.uuid4(), t_id, c_id, prop_id, acc2_id),
        )
    db_conn.commit()

    # Attempting to update line of approved proposal must fail
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("UPDATE journal_lines SET debit_mad = 200.00 WHERE id = %s;", (line_id,))
    assert "immutable" in str(exc_info.value).lower()
    db_conn.rollback()

    # Attempting to delete line of approved proposal must fail
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM journal_lines WHERE id = %s;", (line_id,))
    assert "immutable" in str(exc_info.value).lower()
    db_conn.rollback()


def test_cannot_move_line_to_another_proposal(db_conn: psycopg.Connection):
    """Moving a line to another proposal is forbidden."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    acc1_id = uuid.uuid4()
    acc2_id = uuid.uuid4()
    prop1_id = uuid.uuid4()
    prop2_id = uuid.uuid4()
    line1_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Move');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Client Move');", (c_id, t_id))
        cur.execute(
            """INSERT INTO accounting_periods (id, tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, %s, '2026-09', '2026-09-01', '2026-09-30', '2026-12-31', 'MA-2026.10.1');""",
            (p_id, t_id, c_id),
        )
        cur.execute(
            """INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label)
               VALUES (%s, %s, %s, '611100', 'Achats'), (%s, %s, %s, '441100', 'Fournisseurs');""",
            (acc1_id, t_id, c_id, acc2_id, t_id, c_id),
        )
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping');""",
            (w_id, t_id, c_id, p_id),
        )
        cur.execute(
            """INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
               VALUES (%s, %s, %s, %s, 1, 'ACH', %s, 'P1', 'rules', 'proposed'),
                      (%s, %s, %s, %s, 1, 'ACH', %s, 'P2', 'rules', 'proposed');""",
            (prop1_id, t_id, c_id, w_id, date(2026, 9, 15), prop2_id, t_id, c_id, w_id, date(2026, 9, 15)),
        )
        cur.execute(
            """INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad, fx_rate)
               VALUES (%s, %s, %s, %s, 1, %s, '611100', 'Debit', 'MAD', 100.00, 0, 100.00, 0, 1),
                      (%s, %s, %s, %s, 2, %s, '441100', 'Credit', 'MAD', 0, 100.00, 0, 100.00, 1);""",
            (line1_id, t_id, c_id, prop1_id, acc1_id, uuid.uuid4(), t_id, c_id, prop1_id, acc2_id),
        )
    db_conn.commit()

    with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
        with db_conn.cursor() as cur:
            cur.execute("UPDATE journal_lines SET journal_proposal_id = %s WHERE id = %s;", (prop2_id, line1_id))
    assert "cannot move a line to another proposal" in str(exc_info.value).lower()
    db_conn.rollback()
