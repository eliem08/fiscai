"""Internal operational metrics routes for review effort and costs per file (Phase 5b Item 1)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.telemetry.review_effort import (
    get_internal_metrics_summary,
    record_review_effort,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Metrics"])


class RecordReviewEffortInput(BaseModel):
    active_review_seconds: int = Field(ge=0, default=0)
    fields_corrected: int = Field(ge=0, default=0)
    entries_edited: int = Field(ge=0, default=0)
    issues_resolved: int = Field(ge=0, default=0)


def _resolve_work_request_scope(
    conn: psycopg.Connection,
    session: UserSession,
    work_request_id: uuid.UUID,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT wr.id, wr.tenant_id, wr.client_entity_id
            FROM work_requests wr
            WHERE wr.tenant_id = %s AND wr.id = %s;
            """,
            (session.tenant_id, work_request_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dossier de travail introuvable.")

        client_entity_id = uuid.UUID(str(row[2]))
        if session.role == "client_user" and client_entity_id not in session.client_scope_ids:
            raise HTTPException(status_code=404, detail="Dossier de travail introuvable.")

        return {"id": str(row[0]), "tenant_id": str(row[1])}


@router.post(
    "/work-requests/{work_request_id}/review-effort",
    status_code=status.HTTP_200_OK,
    summary="Enregistrer l'effort de révision active pour un utilisateur",
)
def submit_review_effort(
    work_request_id: uuid.UUID,
    payload: RecordReviewEffortInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Enregistre le temps passé, les champs corrigés, écritures modifiées et anomalies résolues."""
    # Scope check
    _resolve_work_request_scope(conn, session, work_request_id)

    # In-scope role check: staff, accountant, manager, owner can review; client_user & operator cannot mutate review effort
    if session.role in ("client_user", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre rôle ne permet pas d'enregistrer l'effort de révision.",
        )

    result = record_review_effort(
        conn=conn,
        tenant_id=session.tenant_id,
        work_request_id=work_request_id,
        user_id=session.user_id,
        active_review_seconds=payload.active_review_seconds,
        fields_corrected=payload.fields_corrected,
        entries_edited=payload.entries_edited,
        issues_resolved=payload.issues_resolved,
    )
    conn.commit()
    return result


@router.get(
    "/metrics/internal",
    status_code=status.HTTP_200_OK,
    summary="Indicateurs internes d'effort de révision et coût de traitement",
)
def get_internal_metrics(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Accessible exclusivement aux rôles 'owner' et 'operator'."""
    if session.role not in ("owner", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé exclusivement aux propriétaires du cabinet et aux opérateurs.",
        )

    return get_internal_metrics_summary(conn=conn, tenant_id=session.tenant_id)
