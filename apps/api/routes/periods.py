"""Accounting periods endpoints."""

from __future__ import annotations

import datetime
import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.clients.service import (
    ClientArchivedError,
    ClientNotFoundError,
    get_client_entity,
)
from avenel.periods.service import (
    PeriodAlreadyExistsError,
    PeriodOverlapError,
    list_accounting_periods,
    open_accounting_period,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Periods"])


class CreatePeriodRequest(BaseModel):
    period_code: str
    starts_on: datetime.date
    ends_on: datetime.date
    fiscal_year_end: datetime.date


@router.get("/client-entities/{id}/periods", summary="List accounting periods for client company")
async def list_periods(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Lists accounting periods. Cross-tenant or out-of-scope returns 404."""
    scope = session.client_scope_ids if session.role == "client_user" else None
    client = get_client_entity(conn, session.tenant_id, id, client_scope_ids=scope)
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    try:
        items = list_accounting_periods(conn, session.tenant_id, id)
        return {"items": items}
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/client-entities/{id}/periods", status_code=201, summary="Open accounting period for client company")
async def create_period(
    id: uuid.UUID,
    body: CreatePeriodRequest,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    """Opens a new accounting period. Cross-tenant or out-of-scope returns 404. In-scope forbidden returns 403."""
    # Scope check first: out-of-scope returns 404
    if session.role == "client_user" and id not in session.client_scope_ids:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    client = get_client_entity(conn, session.tenant_id, id)
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    # Action permission check: in-scope but unauthorized role returns 403
    if session.role in ("staff", "client_user", "operator"):
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    try:
        period = open_accounting_period(
            conn=conn,
            tenant_id=session.tenant_id,
            client_id=id,
            actor_id=str(session.user_id),
            period_code=body.period_code,
            starts_on=body.starts_on,
            ends_on=body.ends_on,
            fiscal_year_end=body.fiscal_year_end,
        )
        conn.commit()
        return period
    except (PeriodOverlapError, PeriodAlreadyExistsError) as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ClientArchivedError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ClientNotFoundError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
