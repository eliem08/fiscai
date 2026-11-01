"""Issue workflow and portal client requests service per ARCHITECTURE.md Phase 5 and Part D2.

Manages:
- Issue lifecycle: open -> assigned -> waiting_client -> resolved / waived
- Sending issues to client in portal
- Client portal request answers and document attachments
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

import psycopg

from avenel.tenancy.auth import require_tenant_context


class IssueError(Exception):
    """Base exception for issue workflow errors."""


def list_work_request_issues(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Lists issues for a work request, optionally filtered by status."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        query = """
            SELECT id, code, severity, status, resolution, resolution_note,
                   evidence_refs, subject_document_id, subject_proposal_id,
                   subject_bank_transaction_id, assigned_to, resolved_by,
                   resolved_at, created_at
            FROM issues
            WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
        """
        params: list[Any] = [tenant_id, client_entity_id, work_request_id]

        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY CASE severity WHEN 'blocking' THEN 1 WHEN 'review' THEN 2 ELSE 3 END, created_at ASC;"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        return [
            {
                "id": str(r[0]),
                "code": r[1],
                "severity": r[2],
                "status": r[3],
                "resolution": r[4],
                "resolution_note": r[5],
                "evidence_refs": r[6] if isinstance(r[6], list) else json.loads(r[6] or "[]"),
                "subject_document_id": str(r[7]) if r[7] else None,
                "subject_proposal_id": str(r[8]) if r[8] else None,
                "subject_bank_transaction_id": str(r[9]) if r[9] else None,
                "assigned_to": str(r[10]) if r[10] else None,
                "resolved_by": str(r[11]) if r[11] else None,
                "resolved_at": r[12].isoformat() if hasattr(r[12], "isoformat") else str(r[12]) if r[12] else None,
                "created_at": r[13].isoformat() if hasattr(r[13], "isoformat") else str(r[13]),
            }
            for r in rows
        ]


def assign_issue(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    issue_id: uuid.UUID,
    assigned_to: uuid.UUID,
) -> dict[str, Any]:
    """Assigns an issue to a cabinet user."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE issues
            SET assigned_to = %s, status = 'assigned'
            WHERE tenant_id = %s AND id = %s AND status IN ('open', 'assigned')
            RETURNING id, status, assigned_to;
            """,
            (assigned_to, tenant_id, issue_id),
        )
        row = cur.fetchone()
        if not row:
            raise IssueError("Anomalie introuvable ou non assignable.")

        return {"id": str(row[0]), "status": row[1], "assigned_to": str(row[2])}


def resolve_issue(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    issue_id: uuid.UUID,
    resolved_by: uuid.UUID,
    resolution: str = "fixed",
    resolution_note: str | None = None,
) -> dict[str, Any]:
    """Resolves or waives an issue."""
    require_tenant_context(conn)

    if resolution not in ("fixed", "accepted_as_is", "waived"):
        raise ValueError(f"Mode de résolution invalide : {resolution}")

    status = "waived" if resolution == "waived" else "resolved"

    with conn.cursor() as cur:
        # Check blocking constraint: blocking issues cannot be accepted_as_is
        cur.execute("SELECT severity FROM issues WHERE tenant_id = %s AND id = %s;", (tenant_id, issue_id))
        r = cur.fetchone()
        if not r:
            raise IssueError("Anomalie introuvable.")
        if r[0] == "blocking" and resolution == "accepted_as_is":
            raise IssueError("Une anomalie bloquante ne peut pas être acceptée en l'état.")

        cur.execute(
            """
            UPDATE issues
            SET status = %s,
                resolution = %s,
                resolution_note = %s,
                resolved_by = %s,
                resolved_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status, resolution, resolved_at;
            """,
            (status, resolution, resolution_note, resolved_by, tenant_id, issue_id),
        )
        row = cur.fetchone()
        assert row is not None
        return {
            "id": str(row[0]),
            "status": row[1],
            "resolution": row[2],
            "resolved_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }


def acknowledge_review_issue(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    issue_id: uuid.UUID,
    acknowledged_by: uuid.UUID,
    note: str,
) -> dict[str, Any]:
    """Acknowledges a review-severity issue with a mandatory non-empty justification note."""
    require_tenant_context(conn)

    if not note or not note.strip():
        raise ValueError("Le motif d'acquittement est obligatoire.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT severity, status
            FROM issues
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, issue_id),
        )
        row = cur.fetchone()
        if not row:
            raise IssueError("Anomalie introuvable.")

        severity, _current_status = row
        if severity == "blocking":
            raise IssueError("Une anomalie bloquante ne peut pas être acquittée en l'état.")

        cur.execute(
            """
            UPDATE issues
            SET status = 'resolved',
                resolution = 'accepted_as_is',
                resolution_note = %s,
                resolved_by = %s,
                resolved_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status, resolution, resolution_note, resolved_at;
            """,
            (note.strip(), acknowledged_by, tenant_id, issue_id),
        )
        updated = cur.fetchone()
        assert updated is not None
        return {
            "id": str(updated[0]),
            "status": updated[1],
            "resolution": updated[2],
            "resolution_note": updated[3],
            "resolved_at": updated[4].isoformat() if hasattr(updated[4], "isoformat") else str(updated[4]),
        }


def send_issue_to_client(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    issue_id: uuid.UUID,
    actor_id: str,
    client_prompt: str,
) -> dict[str, Any]:
    """Sends an issue request to the client portal, transitioning status to waiting_client."""
    require_tenant_context(conn)

    if not client_prompt or not client_prompt.strip():
        raise ValueError("Le message adressé au client est obligatoire.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, evidence_refs
            FROM issues
            WHERE tenant_id = %s AND id = %s AND status NOT IN ('resolved', 'waived');
            """,
            (tenant_id, issue_id),
        )
        row = cur.fetchone()
        if not row:
            raise IssueError("Anomalie introuvable ou déjà résolue.")

        evidence = row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]")
        entry = {
            "type": "client_request",
            "sent_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "sent_by": actor_id,
            "prompt": client_prompt.strip(),
        }
        evidence.append(entry)

        cur.execute(
            """
            UPDATE issues
            SET status = 'waiting_client',
                resolution = 'sent_to_client',
                evidence_refs = %s::jsonb
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status, resolution;
            """,
            (json.dumps(evidence), tenant_id, issue_id),
        )
        updated = cur.fetchone()
        assert updated is not None
        return {"id": str(updated[0]), "status": updated[1], "resolution": updated[2]}


def list_portal_requests(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Lists requests awaiting client response in the portal."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        query = """
            SELECT i.id, i.client_entity_id, ce.legal_name, i.work_request_id,
                   i.code, i.severity, i.evidence_refs, i.created_at
            FROM issues i
            JOIN client_entities ce ON ce.id = i.client_entity_id AND ce.tenant_id = i.tenant_id
            WHERE i.tenant_id = %s AND i.status = 'waiting_client'
        """
        params: list[Any] = [tenant_id]
        if client_entity_id:
            query += " AND i.client_entity_id = %s"
            params.append(client_entity_id)

        query += " ORDER BY i.created_at DESC;"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        requests_list = []
        for r in rows:
            evidence = r[6] if isinstance(r[6], list) else json.loads(r[6] or "[]")
            last_prompt = ""
            for item in reversed(evidence):
                if item.get("type") == "client_request":
                    last_prompt = item.get("prompt", "")
                    break

            requests_list.append(
                {
                    "id": str(r[0]),
                    "client_entity_id": str(r[1]),
                    "client_name": r[2],
                    "work_request_id": str(r[3]),
                    "code": r[4],
                    "severity": r[5],
                    "prompt": last_prompt,
                    "created_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
                }
            )
        return requests_list


def answer_portal_request(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    issue_id: uuid.UUID,
    client_user_id: uuid.UUID,
    answer_text: str,
    attached_document_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Client user provides explanation and optional replacement document in the portal."""
    require_tenant_context(conn)

    if not answer_text and not attached_document_id:
        raise ValueError("Une explication ou un document justificatif est requis.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, evidence_refs, client_entity_id, work_request_id
            FROM issues
            WHERE tenant_id = %s AND id = %s AND status = 'waiting_client';
            """,
            (tenant_id, issue_id),
        )
        row = cur.fetchone()
        if not row:
            raise IssueError("Demande portail introuvable ou déjà traitée.")

        evidence = row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]")
        entry = {
            "type": "client_response",
            "answered_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "answered_by": str(client_user_id),
            "response": answer_text.strip(),
            "attached_document_id": str(attached_document_id) if attached_document_id else None,
        }
        evidence.append(entry)

        # Transition issue back to 'open' for cabinet review
        cur.execute(
            """
            UPDATE issues
            SET status = 'open',
                resolution = NULL,
                evidence_refs = %s::jsonb
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status;
            """,
            (json.dumps(evidence), tenant_id, issue_id),
        )
        updated = cur.fetchone()
        assert updated is not None
        return {"id": str(updated[0]), "status": updated[1], "answered": True}
