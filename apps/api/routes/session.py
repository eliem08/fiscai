"""Session endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apps.api.deps import get_current_session
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Session"])


@router.get("/me", summary="Get current authenticated user session")
async def get_me(session: Annotated[UserSession, Depends(get_current_session)]) -> dict[str, Any]:
    """Returns active session, tenant, role, and client scoping for authenticated user."""
    return {
        "user_id": str(session.user_id),
        "tenant_id": str(session.tenant_id),
        "membership_id": str(session.membership_id),
        "role": session.role,
        "email": session.email,
        "full_name": session.full_name,
        "client_scope_ids": [str(c) for c in session.client_scope_ids],
    }
