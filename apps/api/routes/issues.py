"""Issue workflow and client portal routes per ARCHITECTURE.md Phase 5 and D2."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.issues.service import (
    IssueError,
    acknowledge_review_issue,
    answer_portal_request,
    assign_issue,
    list_portal_requests,
    resolve_issue,
    send_issue_to_client,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Issues"])


class AssignIssueInput(BaseModel):
    assigned_to: uuid.UUID


class ResolveIssueInput(BaseModel):
    resolution: str = Field(default="fixed", description="fixed, accepted_as_is, or waived")
    resolution_note: str | None = None


class AcknowledgeIssueInput(BaseModel):
    resolution_note: str = Field(min_length=1, description="Motif de l'acquittement en l'état")


class SendToClientInput(BaseModel):
    prompt: str = Field(min_length=1, description="Message adressé au client")


class AnswerPortalRequestInput(BaseModel):
    response: str = Field(description="Explication ou réponse du client")
    attached_document_id: uuid.UUID | None = None


@router.post("/issues/{issue_id}:assign", operation_id="assignIssue")
def assign_issue_endpoint(
    issue_id: uuid.UUID,
    payload: AssignIssueInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Assigns an open issue to a cabinet user."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    try:
        res = assign_issue(conn, session.tenant_id, issue_id, payload.assigned_to)
        conn.commit()
        return res
    except IssueError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/issues/{issue_id}:resolve", operation_id="resolveIssue")
def resolve_issue_endpoint(
    issue_id: uuid.UUID,
    payload: ResolveIssueInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Resolves or waives an issue."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    try:
        res = resolve_issue(
            conn=conn,
            tenant_id=session.tenant_id,
            issue_id=issue_id,
            resolved_by=session.user_id,
            resolution=payload.resolution,
            resolution_note=payload.resolution_note,
        )
        conn.commit()
        return res
    except (IssueError, ValueError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/issues/{issue_id}:acknowledge", operation_id="acknowledgeIssue")
def acknowledge_issue_endpoint(
    issue_id: uuid.UUID,
    payload: AcknowledgeIssueInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Acknowledges a review-severity issue as accepted_as_is with a non-empty note."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    try:
        res = acknowledge_review_issue(
            conn=conn,
            tenant_id=session.tenant_id,
            issue_id=issue_id,
            acknowledged_by=session.user_id,
            note=payload.resolution_note,
        )
        conn.commit()
        return res
    except (IssueError, ValueError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/issues/{issue_id}:send-to-client", operation_id="sendIssueToClient")
def send_issue_to_client_endpoint(
    issue_id: uuid.UUID,
    payload: SendToClientInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Sends an issue request to the client portal."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    try:
        res = send_issue_to_client(
            conn=conn,
            tenant_id=session.tenant_id,
            issue_id=issue_id,
            actor_id=str(session.user_id),
            client_prompt=payload.prompt,
        )
        conn.commit()
        return res
    except IssueError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/portal/requests", operation_id="listPortalRequests")
def list_portal_requests_endpoint(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    client_entity_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[dict[str, Any]]:
    """Lists requests waiting for client action in the portal."""
    scope_client = client_entity_id
    if session.role == "client_user":
        if scope_client and scope_client not in session.client_scope_ids:
            raise HTTPException(status_code=404, detail="Client introuvable.")
        if not scope_client and session.client_scope_ids:
            scope_client = session.client_scope_ids[0]

    return list_portal_requests(conn, session.tenant_id, scope_client)


@router.post("/portal/requests/{request_id}:answer", operation_id="answerPortalRequest")
def answer_portal_request_endpoint(
    request_id: uuid.UUID,
    payload: AnswerPortalRequestInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Client user answers a request in the portal."""
    try:
        res = answer_portal_request(
            conn=conn,
            tenant_id=session.tenant_id,
            issue_id=request_id,
            client_user_id=session.user_id,
            answer_text=payload.response,
            attached_document_id=payload.attached_document_id,
        )
        conn.commit()
        return res
    except IssueError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e))
