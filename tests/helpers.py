"""Test helper functions for seeding tenants, users, and memberships."""

from __future__ import annotations

import uuid

import psycopg


def seed_tenant(conn: psycopg.Connection, legal_name: str = "Cabinet Test") -> uuid.UUID:
    t_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, legal_name, status) VALUES (%s, %s, 'active');",
            (t_id, legal_name),
        )
    conn.commit()
    return t_id


def seed_user(
    conn: psycopg.Connection,
    identity_subject: str,
    email: str,
    full_name: str = "Test User",
) -> uuid.UUID:
    u_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, identity_subject, email, full_name, status)
            VALUES (%s, %s, %s, %s, 'active');
            """,
            (u_id, identity_subject, email, full_name),
        )
    conn.commit()
    return u_id


def seed_membership(
    conn: psycopg.Connection,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str = "accountant",
) -> uuid.UUID:
    m_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memberships (id, user_id, tenant_id, role, status)
            VALUES (%s, %s, %s, %s, 'active');
            """,
            (m_id, user_id, tenant_id, role),
        )
    conn.commit()
    return m_id


def seed_client_scope(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    client_entity_id: uuid.UUID,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO membership_client_scopes (tenant_id, membership_id, client_entity_id)
            VALUES (%s, %s, %s);
            """,
            (tenant_id, membership_id, client_entity_id),
        )
    conn.commit()
