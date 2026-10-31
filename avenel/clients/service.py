"""Client entities (companies) management service.

Handles:
- Client company CRUD operations (archiving instead of deletion per spec)
- Validation of Moroccan identifiers (ICE 15 digits, IF number) via jurisdiction pack
- Audit event generation with hash chaining (client.create, client.update, client.archive)
- Tenant isolation and client scoping enforcement
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import psycopg

from avenel.jurisdiction.loader import get_identifier_regex
from avenel.tenancy.auth import require_tenant_context


class ClientNotFoundError(Exception):
    """Raised when a client company is not found or not accessible."""


class ClientArchivedError(Exception):
    """Raised when an operation is attempted on an archived (read-only) client company."""


@dataclass
class ClientEntity:
    id: uuid.UUID
    tenant_id: uuid.UUID
    legal_name: str
    display_name: str | None = None
    ice: str | None = None
    if_number: str | None = None
    rc_number: str | None = None
    rc_city: str | None = None
    tp_number: str | None = None
    legal_form: str | None = None
    vat_regime: str = "encaissement"
    vat_filing_frequency: str = "quarterly"
    vat_prorata: float | None = None
    is_auto_entrepreneur: bool = False
    functional_currency: str = "MAD"
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["tenant_id"] = str(self.tenant_id)
        return d


def validate_client_identifiers(ice: str | None, if_number: str | None) -> None:
    ice_regex = get_identifier_regex("ice")
    if_regex = get_identifier_regex("if")

    if ice is not None and not ice_regex.match(ice):
        raise ValueError("L'identifiant commun de l'entreprise (ICE) doit comporter exactement 15 chiffres.")
    if if_number is not None and not if_regex.match(if_number):
        raise ValueError("L'identifiant fiscal (IF) doit comporter entre 1 et 10 chiffres.")


def create_client_entity(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    legal_name: str,
    actor_id: str,
    ice: str | None = None,
    if_number: str | None = None,
    rc_number: str | None = None,
    rc_city: str | None = None,
    tp_number: str | None = None,
    legal_form: str | None = None,
    vat_regime: str = "encaissement",
    vat_filing_frequency: str = "quarterly",
    vat_prorata: float | None = None,
    is_auto_entrepreneur: bool = False,
    display_name: str | None = None,
) -> ClientEntity:
    require_tenant_context(conn)
    validate_client_identifiers(ice, if_number)
    legal_name = legal_name.strip()
    if not legal_name:
        raise ValueError("Le nom légal de l'entreprise est obligatoire.")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO client_entities (
                tenant_id, legal_name, display_name, ice, if_number,
                rc_number, rc_city, tp_number, legal_form, vat_regime,
                vat_filing_frequency, vat_prorata, is_auto_entrepreneur, functional_currency
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, 'MAD'
            )
            RETURNING id, created_at, updated_at;
            """,
            (
                tenant_id, legal_name, display_name, ice, if_number,
                rc_number, rc_city, tp_number, legal_form, vat_regime,
                vat_filing_frequency, vat_prorata, is_auto_entrepreneur,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        client_id, created_at, updated_at = row

        # Record hash-chained audit event
        audit_data = json.dumps({
            "legal_name": legal_name,
            "ice": ice,
            "if_number": if_number,
            "vat_regime": vat_regime,
        })
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'client.create', 'client_entity', %s, %s::jsonb);
            """,
            (tenant_id, actor_id, str(client_id), audit_data),
        )

    return ClientEntity(
        id=client_id,
        tenant_id=tenant_id,
        legal_name=legal_name,
        display_name=display_name,
        ice=ice,
        if_number=if_number,
        rc_number=rc_number,
        rc_city=rc_city,
        tp_number=tp_number,
        legal_form=legal_form,
        vat_regime=vat_regime,
        vat_filing_frequency=vat_filing_frequency,
        vat_prorata=vat_prorata,
        is_auto_entrepreneur=is_auto_entrepreneur,
        functional_currency="MAD",
        status="active",
        created_at=str(created_at),
        updated_at=str(updated_at),
    )


def _row_to_client_entity(r: tuple[Any, ...]) -> ClientEntity:
    (
        c_id, t_id, legal_name, display_name, ice,
        if_num, rc_num, rc_city, tp_num, legal_form,
        regime, filing_freq, prorata,
        auto_ent, currency, status, created_at, updated_at,
    ) = r
    return ClientEntity(
        id=c_id,
        tenant_id=t_id,
        legal_name=legal_name,
        display_name=display_name,
        ice=ice,
        if_number=if_num,
        rc_number=rc_num,
        rc_city=rc_city,
        tp_number=tp_num,
        legal_form=legal_form,
        vat_regime=regime,
        vat_filing_frequency=filing_freq,
        vat_prorata=float(prorata) if prorata is not None else None,
        is_auto_entrepreneur=auto_ent,
        functional_currency=currency,
        status=status,
        created_at=str(created_at),
        updated_at=str(updated_at),
    )


def list_client_entities(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_scope_ids: list[uuid.UUID] | None = None,
    limit: int = 50,
) -> list[ClientEntity]:
    """Lists client entities for current tenant, restricted to client_scope_ids if provided."""
    require_tenant_context(conn)
    with conn.cursor() as cur:
        if client_scope_ids is not None:
            if not client_scope_ids:
                return []
            cur.execute(
                """
                SELECT id, tenant_id, legal_name, display_name, ice, if_number,
                       rc_number, rc_city, tp_number, legal_form, vat_regime,
                       vat_filing_frequency, vat_prorata, is_auto_entrepreneur,
                       functional_currency, status, created_at, updated_at
                FROM client_entities
                WHERE tenant_id = %s AND id = ANY(%s)
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (tenant_id, [str(c) for c in client_scope_ids], limit),
            )
        else:
            cur.execute(
                """
                SELECT id, tenant_id, legal_name, display_name, ice, if_number,
                       rc_number, rc_city, tp_number, legal_form, vat_regime,
                       vat_filing_frequency, vat_prorata, is_auto_entrepreneur,
                       functional_currency, status, created_at, updated_at
                FROM client_entities
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (tenant_id, limit),
            )

        rows = cur.fetchall()

    return [_row_to_client_entity(r) for r in rows]


def get_client_entity(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    client_scope_ids: list[uuid.UUID] | None = None,
) -> ClientEntity | None:
    """Fetches single client entity. Enforces client scoping and returns None if not found or unauthorized."""
    require_tenant_context(conn)
    if client_scope_ids is not None and client_id not in client_scope_ids:
        return None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, legal_name, display_name, ice, if_number,
                   rc_number, rc_city, tp_number, legal_form, vat_regime,
                   vat_filing_frequency, vat_prorata, is_auto_entrepreneur,
                   functional_currency, status, created_at, updated_at
            FROM client_entities
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, client_id),
        )
        r = cur.fetchone()
        if not r:
            return None

    return _row_to_client_entity(r)


def update_client_entity(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    actor_id: str,
    updates: dict[str, Any],
    client_scope_ids: list[uuid.UUID] | None = None,
) -> ClientEntity | None:
    require_tenant_context(conn)
    existing = get_client_entity(conn, tenant_id, client_id, client_scope_ids)
    if not existing:
        return None

    if existing.status == "archived":
        raise ClientArchivedError("L'entreprise cliente est archivée et en lecture seule.")

    ice = updates.get("ice", existing.ice)
    if_number = updates.get("if_number", existing.if_number)
    validate_client_identifiers(ice, if_number)

    legal_name = updates.get("legal_name", existing.legal_name)
    display_name = updates.get("display_name", existing.display_name)
    rc_number = updates.get("rc_number", existing.rc_number)
    rc_city = updates.get("rc_city", existing.rc_city)
    tp_number = updates.get("tp_number", existing.tp_number)
    legal_form = updates.get("legal_form", existing.legal_form)
    vat_regime = updates.get("vat_regime", existing.vat_regime)
    vat_filing_frequency = updates.get("vat_filing_frequency", existing.vat_filing_frequency)
    vat_prorata = updates.get("vat_prorata", existing.vat_prorata)
    status = updates.get("status", existing.status)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE client_entities
            SET legal_name = %s, display_name = %s, ice = %s, if_number = %s,
                rc_number = %s, rc_city = %s, tp_number = %s, legal_form = %s,
                vat_regime = %s, vat_filing_frequency = %s, vat_prorata = %s,
                status = %s, updated_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING updated_at;
            """,
            (
                legal_name, display_name, ice, if_number,
                rc_number, rc_city, tp_number, legal_form,
                vat_regime, vat_filing_frequency, vat_prorata,
                status, tenant_id, client_id,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        updated_at = row[0]

        # Audit event
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'client.update', 'client_entity', %s, %s::jsonb);
            """,
            (tenant_id, actor_id, str(client_id), json.dumps(updates)),
        )

    return ClientEntity(
        id=client_id,
        tenant_id=tenant_id,
        legal_name=legal_name,
        display_name=display_name,
        ice=ice,
        if_number=if_number,
        rc_number=rc_number,
        rc_city=rc_city,
        tp_number=tp_number,
        legal_form=legal_form,
        vat_regime=vat_regime,
        vat_filing_frequency=vat_filing_frequency,
        vat_prorata=vat_prorata,
        is_auto_entrepreneur=existing.is_auto_entrepreneur,
        functional_currency="MAD",
        status=status,
        created_at=existing.created_at,
        updated_at=str(updated_at),
    )


def archive_client_entity(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    actor_id: str,
    client_scope_ids: list[uuid.UUID] | None = None,
) -> bool:
    """Archives client company. Archived companies become strictly read-only."""
    require_tenant_context(conn)
    existing = get_client_entity(conn, tenant_id, client_id, client_scope_ids)
    if not existing:
        return False

    if existing.status == "archived":
        return True

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE client_entities
            SET status = 'archived', updated_at = now()
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, client_id),
        )
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'client.archive', 'client_entity', %s, '{"status":"archived"}'::jsonb);
            """,
            (tenant_id, actor_id, str(client_id)),
        )
    return True
