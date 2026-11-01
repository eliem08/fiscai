"""Tenant authentication, membership resolution, and context management.

Enforces:
- Rule A.2 #4: Tenant isolation enforced twice (Application auth + forced PostgreSQL RLS).
- Invariant 1: Cross-tenant requests return 404 (never 403 or 200).
- Spec function alignment: app.current_tenant() reads 'app.tenant_id' and app.current_user_id() reads 'app.user_id'.
- Client user scoping: client_user role restricted strictly to assigned client_entity_ids.
- Operator access expiry check: operator memberships expire after <= 72h.
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import psycopg


class TenantContextMissingError(RuntimeError):
    """Raised when an application query is attempted without an active tenant context."""


@dataclass(frozen=True)
class UserSession:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    membership_id: uuid.UUID
    role: str
    client_scope_ids: list[uuid.UUID] = field(default_factory=list)
    email: str | None = None
    full_name: str | None = None
    identity_subject: str = ""
    professional_registration_no: str | None = None
    auth_time: int | None = None
    mfa_authenticated: bool = False

    def can_access_client(self, client_id: uuid.UUID) -> bool:
        """Determines if the session has access to a specific client company."""
        if self.role == "client_user":
            return client_id in self.client_scope_ids
        return True


def resolve_user_session(
    conn: psycopg.Connection,
    identity_subject: str,
    requested_tenant_id: uuid.UUID | None = None,
    jwt_claims: dict[str, Any] | None = None,
) -> UserSession | None:
    """Resolves membership for an authenticated OIDC identity subject via app.resolve_membership()."""
    with conn.cursor() as cur:
        # 1. Fetch user record
        cur.execute(
            """
            SELECT id, email, full_name, status
            FROM users
            WHERE identity_subject = %s;
            """,
            (identity_subject,),
        )
        user_row = cur.fetchone()
        if not user_row or user_row[3] != "active":
            return None

        user_id, email, full_name, _status = user_row

        # 2. Call SECURITY DEFINER membership resolver
        cur.execute(
            """
            SELECT tenant_id, membership_id, role, client_scope_ids
            FROM app.resolve_membership(%s);
            """,
            (identity_subject,),
        )
        rows = cur.fetchall()
        if not rows:
            return None

        # Filter by requested tenant if supplied
        selected_row = None
        if requested_tenant_id is not None:
            for r in rows:
                if r[0] == requested_tenant_id:
                    selected_row = r
                    break
        else:
            selected_row = rows[0]

        if not selected_row:
            return None

        tenant_id, membership_id, role, client_scope_ids = selected_row
        scope_uuids = [uuid.UUID(str(c)) for c in client_scope_ids] if client_scope_ids else []

        # 3. Check operator expiry & professional registration details
        cur.execute(
            """
            SELECT professional_registration_no, operator_access_expires_at
            FROM memberships
            WHERE id = %s AND tenant_id = %s AND status = 'active';
            """,
            (membership_id, tenant_id),
        )
        m_row = cur.fetchone()
        if not m_row:
            return None

        prof_reg_no, op_expires_at = m_row

        # Check operator access expiry
        if role == "operator":
            if op_expires_at is None:
                return None
            now_utc = datetime.datetime.now(datetime.UTC)
            if op_expires_at <= now_utc:
                return None

        # Check MFA requirement for professional registration if jwt_claims provided
        has_mfa = False
        auth_time = None
        if jwt_claims is not None:
            acr = str(jwt_claims.get("acr", "")).lower()
            mfa_acrs = {"gold", "2", "mfa", "urn:mfa", "urn:oasis:names:tc:saml:2.0:ac:classes:mobiletwofactorunregistered"}
            if acr in mfa_acrs:
                has_mfa = True
            amr = jwt_claims.get("amr", [])
            if isinstance(amr, list):
                amr_set = {str(a).lower() for a in amr}
                if amr_set.intersection({"mfa", "otp", "totp", "sms", "hwk"}):
                    has_mfa = True
            raw_auth_time = jwt_claims.get("auth_time")
            if raw_auth_time is not None:
                try:
                    auth_time = int(raw_auth_time)
                except (ValueError, TypeError):
                    auth_time = None

        if prof_reg_no is not None and jwt_claims is not None:
            from avenel.tenancy.jwt import verify_mfa_requirement
            verify_mfa_requirement(jwt_claims, prof_reg_no)

        return UserSession(
            user_id=user_id,
            tenant_id=tenant_id,
            membership_id=membership_id,
            role=role,
            client_scope_ids=scope_uuids,
            email=email,
            full_name=full_name,
            identity_subject=identity_subject,
            professional_registration_no=prof_reg_no,
            auth_time=auth_time,
            mfa_authenticated=has_mfa,
        )


def set_rls_context(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    is_local: bool = False,
) -> None:
    """Sets PostgreSQL session variables for Row-Level Security enforcement.
    
    Uses spec session variables:
    - 'app.tenant_id' (read by app.current_tenant())
    - 'app.user_id'   (read by app.current_user_id())
    """
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, %s);", (str(tenant_id), is_local))
        if user_id:
            cur.execute("SELECT set_config('app.user_id', %s, %s);", (str(user_id), is_local))
        else:
            cur.execute("SELECT set_config('app.user_id', '', %s);", (is_local,))


def reset_rls_context(conn: psycopg.Connection) -> None:
    """Resets RLS session variables on the connection."""
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', '', false);")
        cur.execute("SELECT set_config('app.user_id', '', false);")


def require_tenant_context(conn: psycopg.Connection) -> uuid.UUID:
    """Verifies that an active tenant context is established on the connection.
    
    Raises TenantContextMissingError if app.current_tenant() is NULL.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT app.current_tenant();")
        row = cur.fetchone()
        if not row or row[0] is None:
            raise TenantContextMissingError(
                "Opération refusée : aucun contexte d'organisation (app.tenant_id) actif sur cette session de base de données."
            )
        return row[0]


def grant_operator_access(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    granter_user_id: uuid.UUID,
    operator_user_id: uuid.UUID,
    duration_hours: float,
) -> datetime.datetime:
    """Grants temporary operator access (expiry <= 72h) to a user in tenant, granted by owner."""
    if duration_hours <= 0 or duration_hours > 72:
        raise ValueError("La durée d'accès opérateur doit être comprise entre 0 et 72 heures.")

    with conn.cursor() as cur:
        # Granter must be owner
        cur.execute(
            """
            SELECT role FROM memberships
            WHERE tenant_id = %s AND user_id = %s AND status = 'active';
            """,
            (tenant_id, granter_user_id),
        )
        row = cur.fetchone()
        if not row or row[0] != "owner":
            raise PermissionError("Seul un propriétaire (owner) du cabinet peut accorder un accès opérateur.")

        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=duration_hours)
        cur.execute(
            """
            INSERT INTO memberships (
                tenant_id, user_id, role, status, operator_access_expires_at
            )
            VALUES (%s, %s, 'operator', 'active', %s)
            ON CONFLICT (tenant_id, user_id) DO UPDATE
            SET role = 'operator', status = 'active', operator_access_expires_at = EXCLUDED.operator_access_expires_at;
            """,
            (tenant_id, operator_user_id, expires_at),
        )

        # Audit event
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'membership.operator_grant', 'memberships', %s, %s::jsonb);
            """,
            (
                tenant_id,
                str(granter_user_id),
                str(operator_user_id),
                json.dumps({"duration_hours": duration_hours, "expires_at": expires_at.isoformat()}),
            ),
        )
        return expires_at
