"""Tests for periods with overlap protection and chart of accounts."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.accounting.chart_import import parse_csv_chart
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_periods_overlap_protection_returns_409(
    postgres_url: str,
    db_conn: psycopg.Connection,
):
    """Opening an overlapping accounting period must return 409 Conflict per Invariant 9."""
    client = TestClient(app)

    tenant_id = seed_tenant(db_conn, "Cabinet Period Test")
    user_id = seed_user(db_conn, "sub-period-tester", "period@test.ma", "Period Tester")
    seed_membership(db_conn, user_id, tenant_id, role="accountant")

    headers = {
        "X-Identity-Subject": "sub-period-tester",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    # 1. Create client company
    res_c = client.post(
        "/v1/client-entities",
        headers=headers,
        json={"legal_name": "Société Période SARL"},
    )
    assert res_c.status_code == 201
    client_id = res_c.json()["id"]

    # 2. Open first period: September 2026 (2026-09-01 to 2026-09-30)
    res_p1 = client.post(
        f"/v1/client-entities/{client_id}/periods",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "period_code": "2026-09",
            "starts_on": "2026-09-01",
            "ends_on": "2026-09-30",
            "fiscal_year_end": "2026-12-31",
        },
    )
    assert res_p1.status_code == 201
    assert res_p1.json()["period_code"] == "2026-09"

    # 3. Attempt to open overlapping period (e.g. 2026-09-15 to 2026-10-15) -> MUST return 409 Conflict
    res_p2 = client.post(
        f"/v1/client-entities/{client_id}/periods",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "period_code": "2026-10",
            "starts_on": "2026-09-15",
            "ends_on": "2026-10-15",
            "fiscal_year_end": "2026-12-31",
        },
    )
    assert res_p2.status_code == 409, f"Expected 409 Conflict for overlapping period, got {res_p2.status_code}"
    problem = res_p2.json()
    assert problem["status"] == 409
    assert "chevauche" in problem["detail"] or "existe déjà" in problem["detail"]

    # 4. Open non-overlapping period: October 2026 (2026-10-01 to 2026-10-31) -> Succeeds 201
    res_p3 = client.post(
        f"/v1/client-entities/{client_id}/periods",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "period_code": "2026-10",
            "starts_on": "2026-10-01",
            "ends_on": "2026-10-31",
            "fiscal_year_end": "2026-12-31",
        },
    )
    assert res_p3.status_code == 201


def test_chart_accounts_seed_and_import(
    postgres_url: str,
    db_conn: psycopg.Connection,
):
    """Tests seeding Moroccan CGNC core accounts and importing custom accounts."""
    client = TestClient(app)

    tenant_id = seed_tenant(db_conn, "Cabinet Chart Test")
    user_id = seed_user(db_conn, "sub-chart-tester", "chart@test.ma", "Chart Tester")
    seed_membership(db_conn, user_id, tenant_id, role="accountant")

    headers = {
        "X-Identity-Subject": "sub-chart-tester",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    # 1. Create client company
    res_c = client.post(
        "/v1/client-entities",
        headers=headers,
        json={"legal_name": "Société Chart SARL"},
    )
    assert res_c.status_code == 201
    client_id = res_c.json()["id"]

    # 2. Seed CGNC core accounts
    res_seed = client.post(
        f"/v1/client-entities/{client_id}/chart-accounts/seed-cgnc",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res_seed.status_code == 200
    assert res_seed.json()["seeded_count"] > 30

    # 3. List chart accounts
    res_list = client.get(
        f"/v1/client-entities/{client_id}/chart-accounts",
        headers=headers,
    )
    assert res_list.status_code == 200
    accounts = res_list.json()["items"]
    account_codes = [a["account_code"] for a in accounts]
    assert "3421" in account_codes  # Clients
    assert "4411" in account_codes  # Fournisseurs
    assert "5141" in account_codes  # Banques

    # 4. Import additional custom chart accounts from CSV
    csv_sample = """Code;Libellé
34210001;Client Atlas SARL
44110001;Fournisseur Maroc Telecom
61110001;Achats composants électroniques
"""
    parsed = parse_csv_chart(csv_sample)
    assert len(parsed) == 3

    res_import = client.post(
        f"/v1/client-entities/{client_id}/chart-accounts/import",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"accounts": [{"code": code, "label": label} for code, label in parsed]},
    )
    assert res_import.status_code == 200
    assert res_import.json()["imported_count"] == 3
