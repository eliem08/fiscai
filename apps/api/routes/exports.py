"""Export routes for Sage 100, Odoo, and Evidence Packs per ARCHITECTURE.md Phase 5 and D2."""

from __future__ import annotations

import datetime
import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.exports.service import (
    ExportApprovalRequiredError,
    ExportError,
    ExportHashMismatchError,
    create_export,
    create_or_get_default_export_profile,
    generate_signed_download_urls,
    get_evidence_pack_file,
    get_export_file,
    record_export_round_trip,
    verify_export_download_token,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Exports"])


class CreateExportInput(BaseModel):
    approval_id: uuid.UUID
    target: str = Field(default="sage100_csv", description="sage100_csv, sage100_pnm, odoo_csv")
    export_profile_id: uuid.UUID | None = None


class RecordRoundTripInput(BaseModel):
    software: str = Field(min_length=1, description="Nom du logiciel (ex: Sage 100, Odoo)")
    version: str = Field(min_length=1, description="Version du logiciel (ex: v10.2, v17)")
    imported_at: datetime.datetime = Field(description="Horodatage de l'importation réelle")
    result: str = Field(description="Résultat de l'importation: 'ok' ou 'failed'")
    notes: str | None = Field(default=None, description="Observations ou détails sur l'import")
    screenshot_document_id: uuid.UUID | None = Field(default=None, description="Document de capture d'écran justificative")


@router.post("/export-profiles/{profile_id}:record-round-trip", operation_id="recordExportRoundTrip")
def record_round_trip_endpoint(
    profile_id: uuid.UUID,
    payload: RecordRoundTripInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Records manual round trip verification on third-party software (owner/manager only, requiring MFA)."""
    if session.role not in ("owner", "manager"):
        raise HTTPException(status_code=403, detail="Opération réservée aux propriétaires et managers.")

    if not session.mfa_authenticated:
        raise HTTPException(
            status_code=401,
            detail="Authentification MFA obligatoire pour enregistrer une validation de round-trip.",
            headers={"WWW-Authenticate": 'Bearer error="insufficient_user_authentication"'},
        )

    try:
        res = record_export_round_trip(
            conn=conn,
            tenant_id=session.tenant_id,
            export_profile_id=profile_id,
            software=payload.software,
            version=payload.version,
            imported_at=payload.imported_at,
            result=payload.result,
            recorded_by=session.user_id,
            notes=payload.notes,
            screenshot_document_id=payload.screenshot_document_id,
        )
        conn.commit()
        return res
    except (ExportError, ValueError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/work-requests/{work_request_id}/exports", status_code=status.HTTP_201_CREATED, operation_id="createExport")
def create_export_endpoint(
    work_request_id: uuid.UUID,
    payload: CreateExportInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Generates an accounting export and cryptographic evidence pack for an approved work request."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT client_entity_id FROM work_requests WHERE tenant_id = %s AND id = %s;",
            (session.tenant_id, work_request_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dossier de travail introuvable.")
        client_entity_id = row[0]

    # Resolve or create export profile
    if payload.export_profile_id:
        profile_id = payload.export_profile_id
    else:
        prof = create_or_get_default_export_profile(conn, session.tenant_id, payload.target)
        profile_id = prof["id"]

    try:
        exp_res = create_export(
            conn=conn,
            tenant_id=session.tenant_id,
            client_entity_id=client_entity_id,
            work_request_id=work_request_id,
            approval_id=payload.approval_id,
            export_profile_id=profile_id,
            actor_id=str(session.user_id),
        )
        conn.commit()
        return exp_res
    except ExportHashMismatchError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ExportApprovalRequiredError as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except ExportError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exports/{export_id}", operation_id="getExport")
def get_export_endpoint(
    export_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Retrieves export metadata."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, e.work_request_id, e.client_entity_id, e.status,
                   e.file_sha256, ep.target, ep.encoding, e.created_at
            FROM exports e
            JOIN export_profiles ep ON ep.id = e.export_profile_id AND ep.tenant_id = e.tenant_id
            WHERE e.tenant_id = %s AND e.id = %s;
            """,
            (session.tenant_id, export_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Exportation introuvable.")

        download_urls = generate_signed_download_urls(export_id, expires_in_seconds=900)
        return {
            "id": str(row[0]),
            "work_request_id": str(row[1]),
            "client_entity_id": str(row[2]),
            "status": row[3],
            "file_sha256": row[4],
            "target": row[5],
            "encoding": row[6],
            "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
            "file_download_url": download_urls["file_download_url"],
            "evidence_pack_download_url": download_urls["evidence_pack_download_url"],
        }


@router.get("/exports/{export_id}/file", operation_id="downloadExportFile")
def download_export_file(
    export_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    token: Annotated[str | None, Query()] = None,
) -> Response:
    """Downloads the generated accounting export file (Sage 100 CSV/PNM or Odoo CSV)."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    if token is not None and not verify_export_download_token(token, export_id, "file"):
        raise HTTPException(status_code=401, detail="Lien de téléchargement expiré ou invalide (délai 15 minutes).")

    try:
        content, filename, mime = get_export_file(conn, session.tenant_id, export_id, actor_id=str(session.user_id))
        conn.commit()
        return Response(
            content=content,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ExportError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/exports/{export_id}/evidence-pack", operation_id="downloadEvidencePack")
def download_evidence_pack(
    export_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    token: Annotated[str | None, Query()] = None,
) -> Response:
    """Downloads the cryptographic Evidence Pack ZIP archive."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    if token is not None and not verify_export_download_token(token, export_id, "evidence_pack"):
        raise HTTPException(status_code=401, detail="Lien de téléchargement expiré ou invalide (délai 15 minutes).")

    try:
        content, filename, mime = get_evidence_pack_file(conn, session.tenant_id, export_id, actor_id=str(session.user_id))
        conn.commit()
        return Response(
            content=content,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ExportError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e))
