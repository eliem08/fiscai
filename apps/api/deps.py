"""FastAPI dependency injection for database connection and authenticated session."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Annotated, Any

import psycopg
from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from avenel.tenancy.auth import UserSession, resolve_user_session, set_rls_context
from avenel.tenancy.jwt import AuthenticationError, MfaRequiredError, get_jwt_verifier


def problem_response(status: int, title: str, detail: str, type_uri: str = "about:blank") -> JSONResponse:
    """Returns an RFC 9457 compliant Problem Details response."""
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": type_uri,
            "title": title,
            "status": status,
            "detail": detail,
        },
    )


def get_db_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel")


def get_db() -> Generator[psycopg.Connection, None, None]:
    """Provides a database connection with auto-rollback on exception."""
    db_url = get_db_url()
    with psycopg.connect(db_url, autocommit=False) as conn:
        yield conn


def get_current_session(
    request: Request,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_identity_subject: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> UserSession:
    """Resolves authenticated session and sets RLS session variables on the connection."""
    jwt_claims: dict[str, Any] | None = None
    subject: str | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        verifier = get_jwt_verifier()
        # If JWKS is configured or token looks like a real JWT (has 3 parts)
        if len(token.split(".")) == 3:
            try:
                jwt_claims = verifier.verify_token(token)
                subject = str(jwt_claims.get("sub", ""))
            except AuthenticationError as e:
                raise HTTPException(
                    status_code=401,
                    detail=f"Échec de l'authentification JWT: {e}",
                ) from e
        else:
            # Fallback for plain subject test tokens
            subject = token

    if not subject and x_identity_subject:
        subject = x_identity_subject

    if not subject:
        raise HTTPException(
            status_code=401,
            detail="Jeton d'authentification ou identité utilisateur manquant.",
        )

    requested_tenant = None
    if x_tenant_id:
        try:
            requested_tenant = uuid.UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Organisation introuvable.",
            )

    try:
        session = resolve_user_session(conn, subject, requested_tenant, jwt_claims=jwt_claims)
    except MfaRequiredError:
        raise
    except AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e

    if not session:
        # If accessing a specific tenant where user is not an active member (or operator expired) -> 404
        if requested_tenant is not None:
            raise HTTPException(
                status_code=404,
                detail="Organisation introuvable ou accès non autorisé.",
            )
        raise HTTPException(
            status_code=401,
            detail="Session invalide ou appartenance active introuvable pour cet utilisateur.",
        )

    # Enforce PostgreSQL Row-Level Security with spec parameters 'app.tenant_id' and 'app.user_id'
    set_rls_context(conn, session.tenant_id, session.user_id)
    return session
