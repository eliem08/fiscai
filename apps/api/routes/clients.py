"""Client company endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.clients.service import (
    ClientArchivedError,
    archive_client_entity,
    create_client_entity,
    get_client_entity,
    list_client_entities,
    update_client_entity,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Clients"])


class CreateClientRequest(BaseModel):
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


class UpdateClientRequest(BaseModel):
    legal_name: str | None = None
    display_name: str | None = None
    ice: str | None = None
    if_number: str | None = None
    rc_number: str | None = None
    rc_city: str | None = None
    tp_number: str | None = None
    legal_form: str | None = None
    vat_regime: str | None = None
    vat_filing_frequency: str | None = None
    vat_prorata: float | None = None
    status: str | None = None


@router.get("/client-entities", summary="List client companies in tenant")
async def list_clients(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Lists client companies for current tenant.
    
    Scoped to assigned client IDs for client_user role.
    """
    scopes = session.client_scope_ids if session.role == "client_user" else None
    clients = list_client_entities(
        conn=conn,
        tenant_id=session.tenant_id,
        client_scope_ids=scopes,
        limit=limit,
    )
    return {
        "items": [c.to_dict() for c in clients],
        "total": len(clients),
    }


@router.post("/client-entities", status_code=201, summary="Create a client company")
async def create_client(
    body: CreateClientRequest,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    """Creates a new client company in current tenant.
    
    Refused for client_user, staff, and operator roles (403).
    """
    if session.role in ("client_user", "staff", "operator"):
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    try:
        client = create_client_entity(
            conn=conn,
            tenant_id=session.tenant_id,
            legal_name=body.legal_name,
            actor_id=str(session.user_id),
            display_name=body.display_name,
            ice=body.ice,
            if_number=body.if_number,
            rc_number=body.rc_number,
            rc_city=body.rc_city,
            tp_number=body.tp_number,
            legal_form=body.legal_form,
            vat_regime=body.vat_regime,
            vat_filing_frequency=body.vat_filing_frequency,
            vat_prorata=body.vat_prorata,
            is_auto_entrepreneur=body.is_auto_entrepreneur,
        )
        conn.commit()
        return client.to_dict()
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/client-entities/{id}", summary="Get client company by ID")
async def get_client(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Fetches single client company. Cross-tenant or out-of-scope returns 404."""
    scopes = session.client_scope_ids if session.role == "client_user" else None
    client = get_client_entity(
        conn=conn,
        tenant_id=session.tenant_id,
        client_id=id,
        client_scope_ids=scopes,
    )
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
    return client.to_dict()


@router.put("/client-entities/{id}", summary="Update client company")
@router.patch("/client-entities/{id}", summary="Patch client company")
async def update_client(
    id: uuid.UUID,
    body: UpdateClientRequest,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    """Updates client company details. Cross-tenant or out-of-scope returns 404. In-scope forbidden returns 403."""
    # 1. Scope & existence check first: cross-tenant or out-of-scope returns 404
    scope = session.client_scope_ids if session.role == "client_user" else None
    existing = get_client_entity(conn, session.tenant_id, id, client_scope_ids=scope)
    if not existing:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    # 2. Action permission check: in-scope but unauthorized role returns 403
    if session.role in ("operator", "staff", "client_user"):
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        client = update_client_entity(
            conn=conn,
            tenant_id=session.tenant_id,
            client_id=id,
            actor_id=str(session.user_id),
            updates=updates,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
        conn.commit()
        return client.to_dict()
    except ClientArchivedError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/client-entities/{id}/archive", summary="Archive client company")
async def archive_client(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    """Archives client company. Reserved for owner and manager. Cross-tenant/out-of-scope returns 404."""
    # 1. Scope & existence check first: cross-tenant or out-of-scope returns 404
    scope = session.client_scope_ids if session.role == "client_user" else None
    existing = get_client_entity(conn, session.tenant_id, id, client_scope_ids=scope)
    if not existing:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    # 2. In-scope action check: only owner and manager can archive client entities
    if session.role in ("accountant", "staff", "client_user", "operator"):
        raise HTTPException(status_code=403, detail="Action réservée aux gestionnaires et propriétaires du cabinet.")

    success = archive_client_entity(
        conn=conn,
        tenant_id=session.tenant_id,
        client_id=id,
        actor_id=str(session.user_id),
    )
    if not success:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
    conn.commit()
    return {"status": "archived", "id": str(id)}
