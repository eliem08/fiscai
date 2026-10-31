"""Chart of accounts management service."""

from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg

from avenel.accounting.cgnc import get_standard_cgnc_accounts
from avenel.clients.service import ClientArchivedError, ClientNotFoundError
from avenel.tenancy.auth import require_tenant_context


def seed_cgnc_chart(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    actor_id: str,
) -> int:
    """Seeds standard Moroccan CGNC accounts (classes 0 to 8) for a client company."""
    require_tenant_context(conn)

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

        # Check if already seeded to prevent duplicate work
        cur.execute(
            """
            SELECT count(*) FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s;
            """,
            (tenant_id, client_id),
        )
        count_row = cur.fetchone()
        existing_count = count_row[0] if count_row is not None else 0
        if existing_count > 0:
            return existing_count

        accounts = get_standard_cgnc_accounts()
        count = 0
        for item in accounts:
            cur.execute(
                """
                INSERT INTO chart_accounts (
                    tenant_id, client_entity_id, account_code, label, source
                )
                VALUES (%s, %s, %s, %s, 'cgnc_seed')
                ON CONFLICT DO NOTHING;
                """,
                (tenant_id, client_id, item["code"], item["label"]),
            )
            count += 1

        # Audit event
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'system', %s, 'chart.seed_cgnc', 'chart_accounts', %s, %s::jsonb);
            """,
            (
                tenant_id,
                actor_id,
                str(client_id),
                json.dumps({"seeded_count": count, "standard": "CGNC-Loi-9-88-Classes-0-8"}),
            ),
        )

    return count


def import_chart_accounts(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    actor_id: str,
    accounts: list[tuple[str, str]],
    source: str = "firm_import",
) -> int:
    """Imports chart of accounts entries from parsed (code, label) tuples."""
    require_tenant_context(conn)

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

        if not accounts:
            return 0

        inserted_count = 0
        for code, label in accounts:
            cur.execute(
                """
                INSERT INTO chart_accounts (
                    tenant_id, client_entity_id, account_code, label, source
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (tenant_id, client_id, code, label, source),
            )
            inserted_count += 1

        # Audit event
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'chart.import', 'chart_accounts', %s, %s::jsonb);
            """,
            (
                tenant_id,
                actor_id,
                str(client_id),
                json.dumps({"imported_count": inserted_count, "source": source}),
            ),
        )

    return inserted_count


def list_chart_accounts(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lists chart accounts for a given client company."""
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
            SELECT id, account_code, label, cgnc_class, source, effective_from, effective_to
            FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s
            ORDER BY account_code ASC
            LIMIT %s;
            """,
            (tenant_id, client_id, limit),
        )
        rows = cur.fetchall()

    return [
        {
            "id": str(r[0]),
            "account_code": r[1],
            "label": r[2],
            "cgnc_class": r[3],
            "source": r[4],
            "effective_from": str(r[5]),
            "effective_to": str(r[6]) if r[6] else None,
        }
        for r in rows
    ]
