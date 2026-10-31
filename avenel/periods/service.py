"""Accounting periods service with GiST exclusion overlap protection."""

from __future__ import annotations

import datetime
import json
import re
import uuid
from typing import Any

import psycopg
from psycopg.errors import ExclusionViolation, UniqueViolation

from avenel.clients.service import ClientArchivedError, ClientNotFoundError
from avenel.tenancy.auth import require_tenant_context

PERIOD_CODE_REGEX = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


class PeriodOverlapError(Exception):
    """Raised when an accounting period overlaps an existing period for the client."""


class PeriodAlreadyExistsError(Exception):
    """Raised when an accounting period code already exists for the client."""


def open_accounting_period(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    actor_id: str,
    period_code: str,
    starts_on: datetime.date,
    ends_on: datetime.date,
    fiscal_year_end: datetime.date,
    pack_version: str = "MA-2026.10.1",
) -> dict[str, Any]:
    """Opens a new monthly accounting period for a client company with overlap protection."""
    require_tenant_context(conn)
    if not PERIOD_CODE_REGEX.match(period_code):
        raise ValueError("Le code de période doit respecter le format YYYY-MM (ex: 2026-09).")
    if ends_on < starts_on:
        raise ValueError("La date de fin de période doit être postérieure ou égale à la date de début.")

    with conn.cursor() as cur:
        # Check client exists and is not archived
        cur.execute(
            "SELECT status FROM client_entities WHERE tenant_id = %s AND id = %s;",
            (tenant_id, client_id),
        )
        row = cur.fetchone()
        if not row:
            raise ClientNotFoundError(f"L'entreprise cliente {client_id} est introuvable.")
        if row[0] == "archived":
            raise ClientArchivedError("L'entreprise cliente est archivée et en lecture seule.")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO accounting_periods (
                    tenant_id, client_entity_id, period_code,
                    starts_on, ends_on, fiscal_year_end,
                    status, jurisdiction_pack_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)
                RETURNING id, status, created_at;
                """,
                (
                    tenant_id, client_id, period_code,
                    starts_on, ends_on, fiscal_year_end,
                    pack_version,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            period_id, status, created_at = row

            # Record audit event
            audit_data = json.dumps({
                "period_code": period_code,
                "starts_on": str(starts_on),
                "ends_on": str(ends_on),
                "jurisdiction_pack_version": pack_version,
            })
            cur.execute(
                """
                INSERT INTO audit_events (
                    tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
                )
                VALUES (%s, 'user', %s, 'period.open', 'accounting_period', %s, %s::jsonb);
                """,
                (tenant_id, actor_id, str(period_id), audit_data),
            )

        return {
            "id": str(period_id),
            "tenant_id": str(tenant_id),
            "client_entity_id": str(client_id),
            "period_code": period_code,
            "starts_on": str(starts_on),
            "ends_on": str(ends_on),
            "fiscal_year_end": str(fiscal_year_end),
            "status": status,
            "jurisdiction_pack_version": pack_version,
            "created_at": str(created_at),
        }
    except ExclusionViolation as e:
        raise PeriodOverlapError(
            f"La période {period_code} ({starts_on} à {ends_on}) chevauche une période existante."
        ) from e
    except UniqueViolation as e:
        raise PeriodAlreadyExistsError(
            f"La période {period_code} existe déjà pour cette entreprise."
        ) from e


def list_accounting_periods(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Lists accounting periods for a client company."""
    require_tenant_context(conn)
    with conn.cursor() as cur:
        # Check client exists
        cur.execute(
            "SELECT id FROM client_entities WHERE tenant_id = %s AND id = %s;",
            (tenant_id, client_id),
        )
        if not cur.fetchone():
            raise ClientNotFoundError(f"L'entreprise cliente {client_id} est introuvable.")

        cur.execute(
            """
            SELECT id, tenant_id, client_entity_id, period_code,
                   starts_on, ends_on, fiscal_year_end, status,
                   jurisdiction_pack_version, created_at
            FROM accounting_periods
            WHERE tenant_id = %s AND client_entity_id = %s
            ORDER BY period_code DESC;
            """,
            (tenant_id, client_id),
        )
        rows = cur.fetchall()

    return [
        {
            "id": str(r[0]),
            "tenant_id": str(r[1]),
            "client_entity_id": str(r[2]),
            "period_code": r[3],
            "starts_on": str(r[4]),
            "ends_on": str(r[5]),
            "fiscal_year_end": str(r[6]),
            "status": r[7],
            "jurisdiction_pack_version": r[8],
            "created_at": str(r[9]),
        }
        for r in rows
    ]
