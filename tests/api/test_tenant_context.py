"""Tests for Tenant Context specification alignment and zero-row visibility without context.

Enforces:
- app.current_tenant() reads 'app.tenant_id' and app.current_user_id() reads 'app.user_id'
- Without tenant context (app.current_tenant() is NULL), zero rows are returned across all tenant tables
- Application code never runs queries without active tenant context (raises TenantContextMissingError)
"""

from __future__ import annotations

import datetime
import uuid

from fastapi.testclient import TestClient
import psycopg
import pytest

from apps.api.main import app
from avenel.accounting.service import list_chart_accounts, seed_cgnc_chart
from avenel.clients.service import (
    create_client_entity,
    get_client_entity,
    list_client_entities,
)
from avenel.periods.service import list_accounting_periods, open_accounting_period
from avenel.tenancy.auth import (
    TenantContextMissingError,
    require_tenant_context,
    set_rls_context,
)
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_db_spec_function_definitions(db_conn: psycopg.Connection):
    """Verifies that DB functions app.current_tenant() and app.current_user_id() read spec variables."""
    with db_conn.cursor() as cur:
        # Check app.current_tenant()
        cur.execute(
            """
            SELECT p.prosrc
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'app' AND p.proname = 'current_tenant';
            """
        )
        row_tenant = cur.fetchone()
        assert row_tenant is not None
        tenant_sql = row_tenant[0].lower()
        assert "app.tenant_id" in tenant_sql, f"Expected app.tenant_id in current_tenant(), got {tenant_sql}"

        # Check app.current_user_id()
        cur.execute(
            """
            SELECT p.prosrc
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'app' AND p.proname = 'current_user_id';
            """
        )
        row_user = cur.fetchone()
        assert row_user is not None
        user_sql = row_user[0].lower()
        assert "app.user_id" in user_sql, f"Expected app.user_id in current_user_id(), got {user_sql}"


def test_no_tenant_context_sees_zero_rows(db_conn: psycopg.Connection, app_conn: psycopg.Connection):
    """When app.tenant_id is not set, RLS hides 100% of rows from avenel_app."""
    # 1. Seed tenant and rows as owner
    t_id = seed_tenant(db_conn, "Cabinet Isolated Context")
    client_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO client_entities (id, tenant_id, legal_name)
            VALUES (%s, %s, 'Visible Corp');
            """,
            (client_id, t_id),
        )
        cur.execute(
            """
            INSERT INTO chart_accounts (tenant_id, client_entity_id, account_code, label)
            VALUES (%s, %s, '3421', 'Clients');
            """,
            (t_id, client_id),
        )
        cur.execute(
            """
            INSERT INTO accounting_periods (tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
            VALUES (%s, %s, '2026-01', '2026-01-01', '2026-01-31', '2026-12-31', 'MA-2026.10.1');
            """,
            (t_id, client_id),
        )
        cur.execute(
            """
            INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id)
            VALUES (%s, 'system', 'sys', 'test.event', 'test', %s);
            """,
            (t_id, str(client_id)),
        )
    db_conn.commit()

    # 2. Check via unprivileged app_conn WITHOUT setting app.tenant_id
    with app_conn.cursor() as cur:
        # Verify app.current_tenant() is NULL
        cur.execute("SELECT app.current_tenant();")
        cur_t = cur.fetchone()
        assert cur_t is not None and cur_t[0] is None

        # All queries return 0 rows
        cur.execute("SELECT count(*) FROM client_entities;")
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM chart_accounts;")
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM accounting_periods;")
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM audit_events;")
        assert cur.fetchone()[0] == 0

    # 3. Now set app.tenant_id with set_rls_context on app_conn and verify rows appear!
    set_rls_context(app_conn, t_id)
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM client_entities;")
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT count(*) FROM chart_accounts;")
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT count(*) FROM accounting_periods;")
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT count(*) FROM audit_events;")
        assert cur.fetchone()[0] == 1


def test_app_never_runs_query_without_tenant_context(app_conn: psycopg.Connection):
    """Service layer methods refuse to execute without active tenant context."""
    dummy_tenant = uuid.uuid4()
    dummy_client = uuid.uuid4()

    # 1. require_tenant_context
    with pytest.raises(TenantContextMissingError):
        require_tenant_context(app_conn)

    # 2. create_client_entity
    with pytest.raises(TenantContextMissingError):
        create_client_entity(app_conn, dummy_tenant, "Refused Corp", "actor-1")

    # 3. list_client_entities
    with pytest.raises(TenantContextMissingError):
        list_client_entities(app_conn, dummy_tenant)

    # 4. get_client_entity
    with pytest.raises(TenantContextMissingError):
        get_client_entity(app_conn, dummy_tenant, dummy_client)

    # 5. seed_cgnc_chart
    with pytest.raises(TenantContextMissingError):
        seed_cgnc_chart(app_conn, dummy_tenant, dummy_client, "actor-1")

    # 6. list_chart_accounts
    with pytest.raises(TenantContextMissingError):
        list_chart_accounts(app_conn, dummy_tenant, dummy_client)

    # 7. open_accounting_period
    with pytest.raises(TenantContextMissingError):
        open_accounting_period(
            app_conn, dummy_tenant, dummy_client, "actor-1",
            "2026-03", datetime.date(2026, 3, 1), datetime.date(2026, 3, 31), datetime.date(2026, 12, 31)
        )

    # 8. list_accounting_periods
    with pytest.raises(TenantContextMissingError):
        list_accounting_periods(app_conn, dummy_tenant, dummy_client)


def test_api_unauthenticated_request_refused_before_query():
    """Unauthenticated request is rejected with 401 without running any tenant queries."""
    client = TestClient(app)
    endpoints = [
        ("GET", "/v1/me"),
        ("GET", "/v1/client-entities"),
        ("POST", "/v1/client-entities"),
        ("GET", f"/v1/client-entities/{uuid.uuid4()}"),
        ("GET", f"/v1/client-entities/{uuid.uuid4()}/periods"),
        ("GET", f"/v1/client-entities/{uuid.uuid4()}/chart-accounts"),
        ("GET", "/v1/compliance/dpa"),
        ("GET", "/v1/compliance/cndp-dossier"),
    ]
    for method, path in endpoints:
        headers = {"Idempotency-Key": str(uuid.uuid4())}
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, headers=headers, json={"legal_name": "Test"})
        assert res.status_code == 401, f"{method} {path} expected 401, got {res.status_code}"
