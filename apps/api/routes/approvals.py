"""Work Request Approvals routes per ARCHITECTURE.md Phase 5 and D.4."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.approvals.service import (
    ApprovalError,
    ApprovalHashMismatchError,
    ApprovalStaleError,
    ApprovalStateError,
    BlockingIssuesExistError,
    MissingRegistrationNumberError,
    NoProposalsError,
    SegregationOfDutiesError,
    UnacknowledgedReviewIssuesError,
    UnbalancedProposalError,
    decide_work_request_approval,
    get_pending_approvals,
    request_work_request_approval,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Approvals"])


class DecideApprovalInput(BaseModel):
    decision: str = Field(description="approved, rejected, or cancelled")
    reason: str = Field(min_length=1, description="Motif de la décision")
    subject_hash: str = Field(min_length=64, max_length=64, description="Empreinte SHA-256 attendue du dossier")


@router.get("/approvals", response_model=list[dict[str, Any]], operation_id="listPendingApprovals")
def list_approvals(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    status_filter: Annotated[str, Query(alias="status")] = "pending",
    limit: Annotated[int, Query(le=100)] = 50,
) -> list[dict[str, Any]]:
    """Lists pending approvals in the tenant."""
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Opération non autorisée pour le rôle client_user.")

    return get_pending_approvals(conn, session.tenant_id, limit=limit)


@router.post("/work-requests/{work_request_id}/approvals", status_code=status.HTTP_201_CREATED, operation_id="requestWorkRequestApproval")
def request_approval(
    work_request_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Submits a monthly bookkeeping work request for formal approval, computing subject_hash."""
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

    try:
        app_res = request_work_request_approval(
            conn=conn,
            tenant_id=session.tenant_id,
            client_entity_id=client_entity_id,
            work_request_id=work_request_id,
            prepared_by=session.user_id,
        )
        conn.commit()
        return app_res
    except (BlockingIssuesExistError, UnacknowledgedReviewIssuesError) as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except (UnbalancedProposalError, NoProposalsError) as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except ApprovalError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approvals/{approval_id}:decide", operation_id="decideApproval")
def decide_approval_endpoint(
    approval_id: uuid.UUID,
    payload: DecideApprovalInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Decides a pending approval (approved, rejected, cancelled)."""
    if session.role in ("client_user", "staff"):
        raise HTTPException(status_code=403, detail="Opération réservée aux experts-comptables et managers.")

    # Re-authentication MFA check: must have authenticated with MFA within the last 5 minutes (300 seconds)
    import time
    now_ts = int(time.time())
    if (
        not session.mfa_authenticated
        or session.auth_time is None
        or (now_ts - session.auth_time > 300)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ré-authentification MFA requise (moins de 5 minutes).",
            headers={"WWW-Authenticate": 'Bearer error="insufficient_user_authentication"'},
        )

    try:
        dec_res = decide_work_request_approval(
            conn=conn,
            tenant_id=session.tenant_id,
            approval_id=approval_id,
            decider_id=session.user_id,
            decision=payload.decision,
            reason=payload.reason,
            expected_subject_hash=payload.subject_hash,
        )
        conn.commit()
        return dec_res
    except (ApprovalStaleError, ApprovalHashMismatchError, BlockingIssuesExistError, UnacknowledgedReviewIssuesError) as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except SegregationOfDutiesError as e:
        conn.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except MissingRegistrationNumberError as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except (ApprovalStateError, ValueError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ApprovalError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e))
