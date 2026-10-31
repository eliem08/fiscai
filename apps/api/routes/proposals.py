"""Accounting proposal inspection, generation, revision, and approval routes (Phase 3)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.proposals.service import (
    ProposalImmutableError,
    ProposalNotFoundError,
    ProposalUnbalancedError,
    create_proposal_revision,
    generate_and_save_proposal_for_document,
    get_proposal_by_id,
    list_proposals_for_work_request,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Proposals"])


class ProposalLineInput(BaseModel):
    account_id: uuid.UUID
    account_code: str
    counterparty_id: uuid.UUID | None = None
    label: str
    currency: str = "MAD"
    debit_tx: float = 0.0
    credit_tx: float = 0.0
    fx_rate: float = 1.0
    fx_rate_date: str | None = None
    fx_source: str | None = None
    debit_mad: float = 0.0
    credit_mad: float = 0.0
    tax_code: str | None = None
    due_date: str | None = None
    evidence_refs: list[dict[str, Any]] = []


class ProposalUpdateInput(BaseModel):
    lines: list[ProposalLineInput]


def _resolve_work_request_scope(
    conn: psycopg.Connection,
    session: UserSession,
    work_request_id: uuid.UUID,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, client_entity_id, accounting_period_id, status
            FROM work_requests
            WHERE tenant_id = %s AND id = %s
            LIMIT 1;
            """,
            (session.tenant_id, work_request_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Demande de travail introuvable.")

        client_id = uuid.UUID(str(row[1]))
        if session.role == "client_user" and client_id not in session.client_scope_ids:
            raise HTTPException(status_code=404, detail="Demande de travail introuvable.")

        return {
            "id": str(row[0]),
            "client_entity_id": client_id,
            "accounting_period_id": uuid.UUID(str(row[2])),
            "status": str(row[3]),
        }


def _resolve_proposal_scope(
    conn: psycopg.Connection,
    session: UserSession,
    proposal_id: uuid.UUID,
) -> dict[str, Any]:
    try:
        proposal = get_proposal_by_id(conn, session.tenant_id, proposal_id)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=404, detail="Proposition introuvable.") from err

    client_id = uuid.UUID(proposal["client_entity_id"])
    if session.role == "client_user" and client_id not in session.client_scope_ids:
        raise HTTPException(status_code=404, detail="Proposition introuvable.")

    return proposal


@router.get("/work-requests/{id}/proposals")
async def list_proposals(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Lists proposals for a work request."""
    _resolve_work_request_scope(conn, session, id)
    return list_proposals_for_work_request(conn, session.tenant_id, id)


@router.get("/proposals/{id}")
async def get_proposal(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Retrieves a single proposal with its lines."""
    return _resolve_proposal_scope(conn, session, id)


@router.post("/documents/{id}:generate-proposal")
async def generate_proposal_endpoint(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Generates and persists a journal proposal for a processed document."""
    # Check operator role
    if session.role == "operator":
        raise HTTPException(status_code=403, detail="Les opérateurs ne peuvent pas générer d'écritures.")

    # Scope resolution
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, client_entity_id, work_request_id
            FROM documents
            WHERE tenant_id = %s AND id = %s
            LIMIT 1;
            """,
            (session.tenant_id, id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        client_id = uuid.UUID(str(row[1]))
        if session.role == "client_user" and client_id not in session.client_scope_ids:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        work_request_id = uuid.UUID(str(row[2]))

    try:
        proposal = generate_and_save_proposal_for_document(
            conn=conn,
            tenant_id=session.tenant_id,
            client_entity_id=client_id,
            work_request_id=work_request_id,
            document_id=id,
            actor_id=str(session.user_id),
        )
        conn.commit()
        return proposal
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(err)) from err


@router.put("/proposals/{id}")
async def update_proposal_endpoint(
    id: uuid.UUID,
    payload: ProposalUpdateInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Edits a proposal, creating a new revision and superseding the previous one."""
    _resolve_proposal_scope(conn, session, id)

    if session.role not in ("owner", "manager", "accountant"):
        raise HTTPException(
            status_code=403,
            detail="Votre rôle ne permet pas de modifier des écritures comptables (droit 'edit_proposals' requis).",
        )

    try:
        lines_data = [l.model_dump() for l in payload.lines]
        new_rev = create_proposal_revision(
            conn=conn,
            tenant_id=session.tenant_id,
            current_proposal_id=id,
            updated_lines=lines_data,
            actor_id=str(session.user_id),
        )
        conn.commit()
        return new_rev
    except ProposalImmutableError as err:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(err)) from err
    except ProposalUnbalancedError as err:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(err)) from err
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(err)) from err


