"""Work requests and monthly bookkeeping files routes."""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.documents.service import (
    DuplicateDocumentError,
    InvalidDocumentPayloadError,
    init_document_upload,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Work"])


class CreateWorkRequestInput(BaseModel):
    client_entity_id: uuid.UUID
    accounting_period_id: uuid.UUID


class UploadInitInput(BaseModel):
    original_filename: str = Field(min_length=1)
    byte_size: int = Field(gt=0, le=52428800)
    mime_type: str
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


def _resolve_work_request_scope(
    conn: psycopg.Connection,
    session: UserSession,
    work_request_id: uuid.UUID,
) -> dict[str, Any]:
    """Scope-first resolution: returns work request row or raises 404."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT wr.id, wr.tenant_id, wr.client_entity_id, wr.accounting_period_id, wr.status, wr.current_revision
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

        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "client_entity_id": str(row[2]),
            "accounting_period_id": str(row[3]),
            "status": row[4],
            "current_revision": row[5],
        }


@router.get("/work-requests")
async def list_work_requests(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    period: str | None = Query(default=None),
) -> dict[str, Any]:
    with conn.cursor() as cur:
        query = """
            SELECT wr.id, wr.tenant_id, wr.client_entity_id, wr.accounting_period_id, wr.status, wr.current_revision
            FROM work_requests wr
            WHERE wr.tenant_id = %s
        """
        params: list[Any] = [session.tenant_id]

        if session.role == "client_user":
            if not session.client_scope_ids:
                return {"items": []}
            query += " AND wr.client_entity_id = ANY(%s)"
            params.append(session.client_scope_ids)

        if period:
            query += " AND wr.accounting_period_id = %s"
            params.append(uuid.UUID(period))

        query += " ORDER BY wr.created_at DESC;"
        cur.execute(query, tuple(params))
        items = []
        for r in cur.fetchall():
            items.append({
                "id": str(r[0]),
                "tenant_id": str(r[1]),
                "client_entity_id": str(r[2]),
                "accounting_period_id": str(r[3]),
                "status": r[4],
                "current_revision": r[5],
            })
        return {"items": items}


@router.post("/work-requests", status_code=status.HTTP_201_CREATED)
async def create_work_request(
    body: CreateWorkRequestInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    # Scope check
    if session.role == "client_user":
        if body.client_entity_id not in session.client_scope_ids:
            raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    if session.role == "operator":
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM client_entities WHERE tenant_id = %s AND id = %s;",
            (session.tenant_id, body.client_entity_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

        cur.execute(
            "SELECT id FROM accounting_periods WHERE tenant_id = %s AND id = %s AND client_entity_id = %s;",
            (session.tenant_id, body.accounting_period_id, body.client_entity_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Période comptable introuvable.")

        cur.execute(
            "SELECT id FROM work_requests WHERE tenant_id = %s AND client_entity_id = %s AND accounting_period_id = %s;",
            (session.tenant_id, body.client_entity_id, body.accounting_period_id),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Un dossier existe déjà pour cette période.")

        wr_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status, current_revision)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'draft', 1)
            RETURNING id, current_revision;
            """,
            (wr_id, session.tenant_id, body.client_entity_id, body.accounting_period_id),
        )
        row = cur.fetchone()
        assert row is not None
        conn.commit()

        return {
            "id": str(row[0]),
            "tenant_id": str(session.tenant_id),
            "client_entity_id": str(body.client_entity_id),
            "accounting_period_id": str(body.accounting_period_id),
            "status": "draft",
            "current_revision": row[1],
        }


@router.get("/work-requests/{id}")
async def get_work_request(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    return _resolve_work_request_scope(conn, session, id)


@router.post("/work-requests/{id}/uploads", status_code=status.HTTP_201_CREATED)
async def init_upload_for_work_request(
    id: uuid.UUID,
    body: UploadInitInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    # 1. Scope-first check: returns 404 if work request is out of scope
    _resolve_work_request_scope(conn, session, id)

    # 2. Role permission check: operator cannot upload documents
    if session.role == "operator":
        raise HTTPException(status_code=403, detail="Les opérateurs ne peuvent pas téléverser de documents.")

    try:
        res = init_document_upload(
            conn=conn,
            tenant_id=session.tenant_id,
            work_request_id=id,
            original_filename=body.original_filename,
            byte_size=body.byte_size,
            mime_type=body.mime_type,
            sha256=body.sha256,
            uploaded_by=session.user_id,
            source_channel="portal" if session.role == "client_user" else "console",
        )
        conn.commit()
        return {
            "document_id": str(res.document_id),
            "document_version_id": str(res.document_version_id),
            "object_key": res.object_key,
            "presigned_upload": res.presigned_upload,
        }
    except DuplicateDocumentError as err:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(err)) from err
    except InvalidDocumentPayloadError as err:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(err)) from err


@router.get("/work-requests/{id}/documents")
async def list_documents(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _resolve_work_request_scope(conn, session, id)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.client_entity_id, d.work_request_id, d.original_filename,
                   d.status, d.doc_type, dv.page_count, d.received_at
            FROM documents d
            LEFT JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s AND d.work_request_id = %s
            ORDER BY d.received_at DESC;
            """,
            (session.tenant_id, id),
        )
        items = []
        for r in cur.fetchall():
            items.append({
                "id": str(r[0]),
                "client_entity_id": str(r[1]),
                "work_request_id": str(r[2]),
                "original_filename": r[3],
                "status": r[4],
                "doc_type": r[5],
                "page_count": r[6],
                "received_at": r[7].isoformat() if r[7] else None,
            })
        return {"items": items}


@router.get("/work-requests/{id}/issues")
async def list_issues(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _resolve_work_request_scope(conn, session, id)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, subject_document_id, code, severity, status, evidence_refs
            FROM issues
            WHERE tenant_id = %s AND work_request_id = %s
            ORDER BY created_at DESC;
            """,
            (session.tenant_id, id),
        )
        items = []
        for r in cur.fetchall():
            refs = r[5] if isinstance(r[5], (list, dict)) else json.loads(r[5]) if r[5] else []
            details_dict = refs[0] if isinstance(refs, list) and refs and isinstance(refs[0], dict) else (refs if isinstance(refs, dict) else {})
            items.append({
                "id": str(r[0]),
                "document_id": str(r[1]) if r[1] else None,
                "code": r[2],
                "severity": r[3],
                "status": r[4],
                "details": details_dict,
            })
        return {"items": items}
