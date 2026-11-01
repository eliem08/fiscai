"""Database tests for ARCHITECTURE.md C.4 Invariants #2, #7, #8, #9."""

import datetime
import uuid

import psycopg
import pytest


def test_invariant_2_cross_client_composite_fk_rejection(db_conn: psycopg.Connection):
    """Invariant #2: Child rows cannot reference parents belonging to another client company in the same tenant."""
    t_id = uuid.uuid4()
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()
    p1_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        # Create one tenant and two client companies with distinct ICE
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Inv2');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name, ice) VALUES (%s, %s, 'Company 1', '001234567000001');", (c1_id, t_id))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name, ice) VALUES (%s, %s, 'Company 2', '001234567000002');", (c2_id, t_id))

        # Create period for Company 1
        cur.execute(
            """INSERT INTO accounting_periods (id, tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, %s, '2026-09', '2026-09-01', '2026-09-30', '2026-12-31', 'MA-2026.10.1');""",
            (p1_id, t_id, c1_id),
        )

        # Attempt to create a work request for Company 2 referencing Company 1's period:
        # Composite FK (tenant_id, client_entity_id, accounting_period_id) -> accounting_periods(tenant_id, client_entity_id, id) MUST REJECT!
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            cur.execute(
                """INSERT INTO work_requests (tenant_id, client_entity_id, accounting_period_id, service_code)
                   VALUES (%s, %s, %s, 'monthly_bookkeeping');""",
                (t_id, c2_id, p1_id),
            )
    db_conn.rollback()


def test_invariant_8_segregation_of_duties_and_registration(db_conn: psycopg.Connection):
    """Invariant #8: Approver cannot be preparer unless single_person_policy is true; approver must have registration."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    u1_id = uuid.uuid4()
    u2_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Inv8');", (t_id,))
        cur.execute("INSERT INTO users (id, identity_subject, email, full_name) VALUES (%s, 's1', 'u1@test.ma', 'User 1'), (%s, 's2', 'u2@test.ma', 'User 2');", (u1_id, u2_id))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Company Inv8');", (c_id, t_id))
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

        # 1. Self-approval violation: prepared_by == decided_by when single_person_policy is false
        cur.execute("SAVEPOINT sp_self;")
        with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
            cur.execute(
                """INSERT INTO approvals (tenant_id, client_entity_id, work_request_id, revision, subject_hash, status, prepared_by, decided_by, decider_registration_no, single_person_policy, reason, decided_at)
                   VALUES (%s, %s, %s, 1, repeat('a', 64), 'approved', %s, %s, 'OEC-12345', false, 'Approved self', now());""",
                (t_id, c_id, w_id, u1_id, u1_id),
            )
        assert "approvals" in str(exc_info.value).lower()
        cur.execute("ROLLBACK TO SAVEPOINT sp_self;")

        # 2. Missing registration number on approval: status='approved' with null decider_registration_no
        cur.execute("SAVEPOINT sp_reg;")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """INSERT INTO approvals (tenant_id, client_entity_id, work_request_id, revision, subject_hash, status, prepared_by, decided_by, decider_registration_no, single_person_policy, reason, decided_at)
                   VALUES (%s, %s, %s, 1, repeat('a', 64), 'approved', %s, %s, null, false, 'Missing reg', now());""",
                (t_id, c_id, w_id, u1_id, u2_id),
            )
        cur.execute("ROLLBACK TO SAVEPOINT sp_reg;")

        # 3. Single-person policy allowed explicitly: prepared_by == decided_by succeeds when single_person_policy=true
        cur.execute(
            """INSERT INTO approvals (tenant_id, client_entity_id, work_request_id, revision, subject_hash, status, prepared_by, decided_by, decider_registration_no, single_person_policy, reason, decided_at)
               VALUES (%s, %s, %s, 1, repeat('a', 64), 'approved', %s, %s, 'OEC-9999', true, 'Single person policy approved', now());""",
            (t_id, c_id, w_id, u1_id, u1_id),
        )
    db_conn.rollback()


def test_invariant_9_overlapping_periods_and_chart_accounts_rejected(db_conn: psycopg.Connection):
    """Invariant #9: Accounting periods for one client never overlap; chart accounts never overlap in effective dates."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Inv9');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Company Inv9');", (c_id, t_id))

        # First period: 2026-09-01 to 2026-09-30
        cur.execute(
            """INSERT INTO accounting_periods (tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, '2026-09', '2026-09-01', '2026-09-30', '2026-12-31', 'MA-2026.10.1');""",
            (t_id, c_id),
        )

        # Overlapping period: 2026-09-15 to 2026-10-15 (must fail GiST exclusion constraint)
        cur.execute("SAVEPOINT sp_p;")
        with pytest.raises(psycopg.errors.ExclusionViolation):
            cur.execute(
                """INSERT INTO accounting_periods (tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
                   VALUES (%s, %s, '2026-10', '2026-09-15', '2026-10-15', '2026-12-31', 'MA-2026.10.1');""",
                (t_id, c_id),
            )
        cur.execute("ROLLBACK TO SAVEPOINT sp_p;")

        # First chart account: effective from 2026-01-01 to 2026-12-31
        cur.execute(
            """INSERT INTO chart_accounts (tenant_id, client_entity_id, account_code, label, effective_from, effective_to)
               VALUES (%s, %s, '611100', 'Achats v1', '2026-01-01', '2026-12-31');""",
            (t_id, c_id),
        )

        # Overlapping chart account: same code 611100 from 2026-06-01 to 2027-06-01 (must fail GiST exclusion constraint)
        cur.execute("SAVEPOINT sp_c;")
        with pytest.raises(psycopg.errors.ExclusionViolation):
            cur.execute(
                """INSERT INTO chart_accounts (tenant_id, client_entity_id, account_code, label, effective_from, effective_to)
               VALUES (%s, %s, '611100', 'Achats v2', '2026-06-01', '2027-06-01');""",
                (t_id, c_id),
            )
        cur.execute("ROLLBACK TO SAVEPOINT sp_c;")
    db_conn.rollback()


def test_unique_nulls_not_distinct_duplicates_rejected(db_conn: psycopg.Connection):
    """UNIQUE NULLS NOT DISTINCT constraint rejects multiple rows with NULL ice in the same tenant."""
    t_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Nulls');", (t_id,))
        # First company with NULL ice
        cur.execute(
            "INSERT INTO client_entities (tenant_id, legal_name, ice) VALUES (%s, 'Company Null ICE 1', NULL);",
            (t_id,),
        )
        # Second company with NULL ice in the same tenant MUST FAIL UNIQUE NULLS NOT DISTINCT!
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO client_entities (tenant_id, legal_name, ice) VALUES (%s, 'Company Null ICE 2', NULL);",
                (t_id,),
            )
    db_conn.rollback()


def test_export_fk_requires_approval(db_conn: psycopg.Connection):
    """Invariant #7 (FK): Export must reference a valid approval in the same tenant."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    prof_id = uuid.uuid4()
    fake_approval_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Inv7');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Company Inv7');", (c_id, t_id))
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
            """INSERT INTO export_profiles (id, tenant_id, name, target, config)
               VALUES (%s, %s, 'Sage Profile', 'sage100_csv', '{}'::jsonb);""",
            (prof_id, t_id),
        )

        # Attempt to insert export referencing non-existent approval
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            cur.execute(
                """INSERT INTO exports (tenant_id, client_entity_id, work_request_id, approval_id, export_profile_id)
                   VALUES (%s, %s, %s, %s, %s);""",
                (t_id, c_id, w_id, fake_approval_id, prof_id),
            )
    db_conn.rollback()


from avenel.approvals.service import (
    decide_work_request_approval,
    request_work_request_approval,
)
from avenel.clients.service import create_client_entity
from avenel.exports.service import (
    ExportHashMismatchError,
    create_export,
    create_or_get_default_export_profile,
)
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_invariant_7_export_refused_on_hash_mismatch(db_conn: psycopg.Connection):
    """Invariant #7: Export refused when proposal hash changed between approval and export (Phase 5)."""
    tenant_id = seed_tenant(db_conn, "Cabinet Invariant 7 Audit")

    preparer_sub = f"prep-{uuid.uuid4()}"
    preparer_id = seed_user(db_conn, identity_subject=preparer_sub, email=f"{preparer_sub}@avenel.ma")
    seed_membership(db_conn, preparer_id, tenant_id, "accountant")

    decider_sub = f"decider-{uuid.uuid4()}"
    decider_id = seed_user(db_conn, identity_subject=decider_sub, email=f"{decider_sub}@avenel.ma")
    seed_membership(
        db_conn,
        decider_id,
        tenant_id,
        "owner",
        professional_title="expert_comptable",
        professional_registration_no="OEC-998877",
    )

    set_rls_context(db_conn, tenant_id, preparer_id)

    client = create_client_entity(db_conn, tenant_id, "Atlas Trading SARL", actor_id=str(preparer_id))
    period = open_accounting_period(
        db_conn,
        tenant_id,
        client.id,
        actor_id=str(preparer_id),
        period_code="2026-09",
        starts_on=datetime.date(2026, 9, 1),
        ends_on=datetime.date(2026, 9, 30),
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

    # Seed accounts
    acc_6111 = uuid.uuid4()
    acc_4411 = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, '6111000', 'Achats de marchandises', 'cgnc_seed'),
                   (%s, %s, %s, '4411000', 'Fournisseurs', 'cgnc_seed');
            """,
            (acc_6111, tenant_id, client.id, acc_4411, tenant_id, client.id),
        )

    # Seed a balanced proposal
    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (
                id, tenant_id, client_entity_id, work_request_id, revision,
                journal_code, entry_date, label, proposed_by, status
            )
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-09-15', 'Achat fournitures', 'rules', 'proposed');
            """,
            (prop_id, tenant_id, client.id, wr_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (
                id, tenant_id, client_entity_id, journal_proposal_id, line_no,
                account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad
            )
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 2400.00, 0.00, 2400.00, 0.00),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseurs', 'MAD', 0.00, 2400.00, 0.00, 2400.00);
            """,
            (uuid.uuid4(), tenant_id, client.id, prop_id, acc_6111, uuid.uuid4(), tenant_id, client.id, prop_id, acc_4411),
        )
    db_conn.commit()

    # 1. Request approval (preparer)
    app_res = request_work_request_approval(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client.id,
        work_request_id=wr_id,
        prepared_by=preparer_id,
    )
    approval_id = uuid.UUID(app_res["id"])
    approved_hash = app_res["subject_hash"]

    # 2. Decide approval (decider - segregated)
    set_rls_context(db_conn, tenant_id, decider_id)
    dec_res = decide_work_request_approval(
        conn=db_conn,
        tenant_id=tenant_id,
        approval_id=approval_id,
        decider_id=decider_id,
        decision="approved",
        reason="Dossier vérifié et équilibré",
        expected_subject_hash=approved_hash,
    )
    assert dec_res["status"] == "approved"
    db_conn.commit()

    # 3. Create default export profile
    prof = create_or_get_default_export_profile(db_conn, tenant_id, "sage100_csv")
    prof_id = prof["id"]
    db_conn.commit()

    # 4. Simulate hash mismatch (e.g. data tampered or subject_hash out of sync with proposals)
    tampered_hash = "0" * 64
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE approvals SET subject_hash = %s WHERE tenant_id = %s AND id = %s;",
            (tampered_hash, tenant_id, approval_id),
        )
    db_conn.commit()

    # 5. Invariant #7: Export MUST be refused with ExportHashMismatchError!
    with pytest.raises(ExportHashMismatchError) as exc_info:
        create_export(
            conn=db_conn,
            tenant_id=tenant_id,
            client_entity_id=client.id,
            work_request_id=wr_id,
            approval_id=approval_id,
            export_profile_id=prof_id,
            actor_id=str(decider_id),
        )
    assert "Le dossier a changé depuis la validation" in str(exc_info.value)
    db_conn.rollback()

    # 6. Revert subject_hash so hash matches the actual proposals again
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE approvals SET subject_hash = %s WHERE tenant_id = %s AND id = %s;",
            (approved_hash, tenant_id, approval_id),
        )
    db_conn.commit()

    # 7. With matching hash, export succeeds cleanly!
    exp = create_export(
        conn=db_conn,
        tenant_id=tenant_id,
        client_entity_id=client.id,
        work_request_id=wr_id,
        approval_id=approval_id,
        export_profile_id=prof_id,
        actor_id=str(decider_id),
    )
    assert exp["status"] == "ready"
    assert exp["subject_hash"] == approved_hash

    # Verify usage record inserted
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT unit, quantity, billable
            FROM usage_records
            WHERE tenant_id = %s AND work_request_id = %s;
            """,
            (tenant_id, wr_id),
        )
        usage = cur.fetchone()
        assert usage is not None
        assert usage[0] == "monthly_file"
        assert float(usage[1]) == 1.0
        assert usage[2] is True

        # Verify export profile verified_round_trip_at is NOT modified by export (requirement #1)
        cur.execute(
            "SELECT verified_round_trip_at FROM export_profiles WHERE tenant_id = %s AND id = %s;",
            (tenant_id, prof_id),
        )
        verified_at = cur.fetchone()[0]
        assert verified_at is None


