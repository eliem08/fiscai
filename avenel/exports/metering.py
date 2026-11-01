"""Usage metering service per ARCHITECTURE.md Phase 5 and Part F.

Enforces:
- Rule A.2 #5: Immutable audit and usage records.
- Invariant: Exactly one monthly_file billable unit recorded per work request.
"""

from __future__ import annotations

import uuid

import psycopg

from avenel.tenancy.auth import require_tenant_context


def record_export_usage(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    price_version: str = "2026.1",
) -> uuid.UUID | None:
    """Records a billable monthly_file unit upon successful approval and export generation."""
    require_tenant_context(conn)

    record_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usage_records (
                id, tenant_id, client_entity_id, work_request_id,
                unit, quantity, price_version, billable
            )
            VALUES (%s, %s, %s, %s, 'monthly_file', 1.0, %s, true)
            ON CONFLICT (tenant_id, work_request_id, unit)
            DO NOTHING
            RETURNING id;
            """,
            (
                record_id,
                tenant_id,
                client_entity_id,
                work_request_id,
                price_version,
            ),
        )
        row = cur.fetchone()
        return row[0] if row else None

