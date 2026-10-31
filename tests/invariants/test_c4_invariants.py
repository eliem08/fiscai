"""Database tests for ARCHITECTURE.md C.4 Invariants #2, #7, #8, #9."""

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


@pytest.mark.skip(reason="Phase 5 Exit Criterion: Invariant #7 export refused when proposal hash changed")
def test_invariant_7_export_refused_on_hash_mismatch():
    """Invariant #7: Export refused when proposal hash changed between approval and export (Phase 5)."""
    pass

