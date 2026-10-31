"""RLS and Tenant Isolation Tests per ARCHITECTURE.md C.4, C.5 and Part G Phase 0 exit criteria."""

import uuid

import psycopg
import pytest

from scripts.rls_check import check_rls


def test_make_rls_check_passes(postgres_url: str):
    """Exit criterion: `make rls-check` passes on every table with tenant_id."""
    assert check_rls(postgres_url) is True


def test_tenant_isolation_and_row_level_security(postgres_url: str, db_conn: psycopg.Connection, app_conn: psycopg.Connection):
    """Test that avenel_app connection strictly adheres to RLS isolation between tenants."""
    t1_id = uuid.uuid4()
    t2_id = uuid.uuid4()

    # 1. Create two separate tenants and client companies as db_owner
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, legal_name, data_residency_policy) VALUES (%s, %s, %s);",
            (t1_id, "Tenant Alpha", "MA_ONLY"),
        )
        cur.execute(
            "INSERT INTO tenants (id, legal_name, data_residency_policy) VALUES (%s, %s, %s);",
            (t2_id, "Tenant Beta", "MA_ONLY"),
        )
        cur.execute(
            "INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, %s);",
            (uuid.uuid4(), t1_id, "Client Alpha 1"),
        )
        cur.execute(
            "INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, %s);",
            (uuid.uuid4(), t2_id, "Client Beta 1"),
        )
    db_conn.commit()

    # 2. Query as avenel_app with Tenant Alpha context in a transaction
    with app_conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true);", (str(t1_id),))
        cur.execute("SELECT legal_name FROM client_entities;")
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Client Alpha 1"

        # Tenant Beta company must be completely invisible
        cur.execute("SELECT count(*) FROM client_entities WHERE tenant_id = %s;", (str(t2_id),))
        assert cur.fetchone()[0] == 0

        # Tenants table self policy: only sees Tenant Alpha
        cur.execute("SELECT id, legal_name FROM tenants;")
        t_rows = cur.fetchall()
        assert len(t_rows) == 1
        assert t_rows[0][0] == t1_id

    # Reset transaction: transaction-local setting clears on rollback/commit
    app_conn.rollback()

    # 3. Query without setting app.tenant_id in a new transaction: everything is hidden
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM client_entities;")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM tenants;")
        assert cur.fetchone()[0] == 0

    # 4. Attempting to insert a row with mismatched tenant_id fails WITH CHECK
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with app_conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true);", (str(t1_id),))
            cur.execute(
                "INSERT INTO client_entities (tenant_id, legal_name) VALUES (%s, %s);",
                (str(t2_id), "Illegal Cross-Tenant Entity"),
            )
