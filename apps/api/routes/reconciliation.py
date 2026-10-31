"""Bank reconciliation API routes (Phase 4)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.reconciliation.service import (
    accept_reconciliation_match,
    generate_reconciliation_matches,
    list_reconciliation_matches,
    reject_reconciliation_match,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1/reconciliation", tags=["Reconciliation"])


class GenerateMatchesInput(BaseModel):
    client_entity_id: uuid.UUID
    work_request_id: uuid.UUID
    date_window_days: int | None = None


def _check_client_scope(session: UserSession, client_id: uuid.UUID) -> None:
    if session.role == "client_user" and client_id not in session.client_scope_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")


def _resolve_work_request(
    conn: psycopg.Connection,
    session: UserSession,
    work_request_id: uuid.UUID,
) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT client_entity_id FROM work_requests
            WHERE tenant_id = %s AND id = %s
            LIMIT 1;
            """,
            (session.tenant_id, work_request_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande de travail introuvable.")
        client_id = uuid.UUID(str(row[0]))
        _check_client_scope(session, client_id)
        return client_id


@router.get("/matches")
def list_matches_endpoint(
    work_request_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Lists reconciliation candidates and accepted matches for a work request."""
    _resolve_work_request(conn, session, work_request_id)
    return list_reconciliation_matches(conn, session.tenant_id, work_request_id)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_matches_endpoint(
    payload: GenerateMatchesInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Triggers candidate generation for bank reconciliation."""
    _check_client_scope(session, payload.client_entity_id)

    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    return generate_reconciliation_matches(
        conn=conn,
        tenant_id=session.tenant_id,
        client_entity_id=payload.client_entity_id,
        work_request_id=payload.work_request_id,
        date_window_days=payload.date_window_days,
    )


@router.post("/matches/{match_id}/accept")
def accept_match_endpoint(
    match_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Accepts a reconciliation match. Enforces double-match prevention."""
    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    try:
        return accept_reconciliation_match(
            conn=conn,
            tenant_id=session.tenant_id,
            match_id=match_id,
            actor_id=str(session.user_id),
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err


@router.post("/matches/{match_id}/reject")
def reject_match_endpoint(
    match_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Rejects a reconciliation match candidate."""
    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    try:
        return reject_reconciliation_match(
            conn=conn,
            tenant_id=session.tenant_id,
            match_id=match_id,
            actor_id=str(session.user_id),
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
