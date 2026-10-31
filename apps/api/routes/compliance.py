"""Compliance endpoints for Moroccan Law 09-08 (DPA & CNDP)."""

from __future__ import annotations

from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from apps.api.deps import get_current_session, get_db
from avenel.compliance.cndp import generate_cndp_dossier
from avenel.compliance.dpa import generate_dpa_document
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Compliance"])


@router.get("/compliance/dpa", summary="Generate Data Processing Agreement")
async def get_dpa(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Generates a project DPA for the active tenant under Loi 09-08."""
    if session.role == "client_user":
        raise HTTPException(status_code=404, detail="Document introuvable.")

    with conn.cursor() as cur:
        cur.execute("SELECT legal_name FROM tenants WHERE id = %s;", (session.tenant_id,))
        tenant_row = cur.fetchone()
        firm_name = tenant_row[0] if tenant_row else "Cabinet Comptable"

    return generate_dpa_document(
        tenant_id=session.tenant_id,
        firm_legal_name=firm_name,
        representative_name=session.full_name or "Représentant Légal",
    )


@router.get("/compliance/cndp-dossier", summary="Generate CNDP declaration dossier")
async def get_cndp(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Generates the CNDP declaration dossier project for personal data processing."""
    if session.role == "client_user":
        raise HTTPException(status_code=404, detail="Document introuvable.")

    with conn.cursor() as cur:
        cur.execute("SELECT legal_name FROM tenants WHERE id = %s;", (session.tenant_id,))
        tenant_row = cur.fetchone()
        firm_name = tenant_row[0] if tenant_row else "Cabinet Comptable"

    return generate_cndp_dossier(
        tenant_id=session.tenant_id,
        firm_legal_name=firm_name,
        representative_name=session.full_name or "Représentant Légal",
        firm_email=session.email,
    )
