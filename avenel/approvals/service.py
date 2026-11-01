"""Work request approval service per ARCHITECTURE.md Phase 5 and D.4.

Enforces:
- Rule A.3: Humans approve.
- Invariant #7: Export refused when proposal hash changed between approval and export.
- Invariant #8: Approver cannot be preparer unless single_person_policy is true; approver must have registration.
- Quality gate: All blocking issues must be resolved before requesting approval.
- Empreinte numérique (subject_hash) calculated over deterministic proposals and matches.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg

from avenel.approvals.hashing import compute_proposal_set_hash
from avenel.tenancy.auth import require_tenant_context


class ApprovalError(Exception):
    """Base exception for approval domain errors."""


class BlockingIssuesExistError(ApprovalError):
    """Raised when open blocking issues prevent submitting or approving a work request."""


class UnacknowledgedReviewIssuesError(ApprovalError):
    """Raised when unacknowledged review issues prevent submitting or approving a work request."""


class UnbalancedProposalError(ApprovalError):
    """Raised when active proposals in the work request do not balance."""


class NoProposalsError(ApprovalError):
    """Raised when attempting to approve a work request with zero active proposals."""


class ApprovalStateError(ApprovalError):
    """Raised when an approval is not in pending state for a decision."""


class ApprovalStaleError(ApprovalError):
    """Raised when proposals mutated between approval request and decision (409 Conflict)."""


class ApprovalHashMismatchError(ApprovalError):
    """Raised when provided expected subject_hash does not match the approval record (409 Conflict)."""


class SegregationOfDutiesError(ApprovalError):
    """Raised when preparer attempts to approve without single_person_policy."""


class MissingRegistrationNumberError(ApprovalError):
    """Raised when the approver lacks a professional registration number."""


def get_work_request_canonical_proposals_and_matches(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetches active proposals and accepted reconciliation matches for hash computation."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        # 1. Fetch active proposals (proposed, edited, approved)
        cur.execute(
            """
            SELECT id, revision, journal_code, entry_date, label,
                   source_document_id, source_bank_transaction_id
            FROM journal_proposals
            WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
              AND status IN ('proposed', 'edited', 'approved')
            ORDER BY journal_code, entry_date, id;
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        prop_rows = cur.fetchall()

        proposals_data: list[dict[str, Any]] = []
        for p in prop_rows:
            p_id, rev, j_code, e_date, lbl, doc_id, bt_id = p
            cur.execute(
                """
                SELECT line_no, account_code, label, currency, debit_mad, credit_mad, counterparty_id
                FROM journal_lines
                WHERE tenant_id = %s AND journal_proposal_id = %s
                ORDER BY line_no ASC;
                """,
                (tenant_id, p_id),
            )
            line_rows = cur.fetchall()
            lines = [
                {
                    "line_no": int(lr[0]),
                    "account_code": str(lr[1]),
                    "label": str(lr[2] or ""),
                    "currency": str(lr[3] or "MAD"),
                    "debit_mad": f"{float(lr[4] or 0.0):.2f}",
                    "credit_mad": f"{float(lr[5] or 0.0):.2f}",
                    "counterparty_id": str(lr[6]) if lr[6] else None,
                }
                for lr in line_rows
            ]

            proposals_data.append(
                {
                    "id": str(p_id),
                    "revision": int(rev),
                    "journal_code": str(j_code),
                    "entry_date": e_date.isoformat() if hasattr(e_date, "isoformat") else str(e_date),
                    "label": str(lbl or ""),
                    "source_document_id": str(doc_id) if doc_id else None,
                    "source_bank_transaction_id": str(bt_id) if bt_id else None,
                    "lines": lines,
                }
            )

        # 2. Fetch accepted reconciliation matches
        cur.execute(
            """
            SELECT rm.id, rm.difference_kind, rm.difference_mad
            FROM reconciliation_matches rm
            WHERE rm.tenant_id = %s AND rm.client_entity_id = %s AND rm.work_request_id = %s
              AND rm.status = 'accepted'
            ORDER BY rm.id;
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        match_rows = cur.fetchall()

        matches_data: list[dict[str, Any]] = []
        for m in match_rows:
            m_id, d_kind, d_mad = m
            cur.execute(
                """
                SELECT bank_transaction_id, journal_proposal_id, amount_mad
                FROM reconciliation_match_items
                WHERE tenant_id = %s AND match_id = %s
                ORDER BY bank_transaction_id NULLS LAST, journal_proposal_id NULLS LAST;
                """,
                (tenant_id, m_id),
            )
            item_rows = cur.fetchall()
            items = [
                {
                    "bank_transaction_id": str(ir[0]) if ir[0] else None,
                    "journal_proposal_id": str(ir[1]) if ir[1] else None,
                    "amount_mad": f"{float(ir[2]):.2f}",
                }
                for ir in item_rows
            ]
            matches_data.append(
                {
                    "id": str(m_id),
                    "difference_kind": str(d_kind or "none"),
                    "difference_mad": f"{float(d_mad or 0.0):.2f}",
                    "items": items,
                }
            )

    return proposals_data, matches_data


def compute_work_request_subject_hash(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
) -> str:
    """Computes the deterministic SHA-256 subject_hash for a work request."""
    proposals, matches = get_work_request_canonical_proposals_and_matches(
        conn, tenant_id, client_entity_id, work_request_id
    )
    return compute_proposal_set_hash(proposals, matches)


def check_work_request_quality_gate(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
) -> None:
    """Verifies that no blocking issues exist and all proposals are balanced."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        # Check blocking issues
        cur.execute(
            """
            SELECT code, severity, status
            FROM issues
            WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
              AND severity = 'blocking' AND status NOT IN ('resolved', 'waived');
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        blocking_issues = cur.fetchall()
        if blocking_issues:
            codes = [b[0] for b in blocking_issues]
            raise BlockingIssuesExistError(
                f"Validation refusée : des anomalies bloquantes non résolues subsistent ({', '.join(codes)})."
            )

        # Check review issues: must all be acknowledged (fixed, or accepted_as_is with note)
        cur.execute(
            """
            SELECT code, status, resolution, resolution_note
            FROM issues
            WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
              AND severity = 'review'
              AND (
                status NOT IN ('resolved', 'waived')
                OR (resolution = 'accepted_as_is' AND (resolution_note IS NULL OR trim(resolution_note) = ''))
              );
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        unack_review_issues = cur.fetchall()
        if unack_review_issues:
            codes = [u[0] for u in unack_review_issues]
            raise UnacknowledgedReviewIssuesError(
                f"Validation refusée : des anomalies de niveau revue non acquittées subsistent ({', '.join(codes)})."
            )

        # Check balance of active proposals
        cur.execute(
            """
            SELECT jp.id, jp.journal_code,
                   COALESCE(SUM(jl.debit_mad), 0.0) as total_debit,
                   COALESCE(SUM(jl.credit_mad), 0.0) as total_credit
            FROM journal_proposals jp
            JOIN journal_lines jl ON jl.journal_proposal_id = jp.id AND jl.tenant_id = jp.tenant_id
            WHERE jp.tenant_id = %s AND jp.client_entity_id = %s AND jp.work_request_id = %s
              AND jp.status IN ('proposed', 'edited', 'approved')
            GROUP BY jp.id, jp.journal_code;
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        p_rows = cur.fetchall()
        for p_id, j_code, tot_dr, tot_cr in p_rows:
            diff = round(abs(float(tot_dr) - float(tot_cr)), 2)
            if diff > 0.001:
                raise UnbalancedProposalError(
                    f"Proposition {p_id} ({j_code}) déséquilibrée : Débit {tot_dr:.2f} != Crédit {tot_cr:.2f}."
                )


def request_work_request_approval(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    prepared_by: uuid.UUID,
    single_person_policy: bool | None = None,
) -> dict[str, Any]:
    """Submits a work request for formal approval, creating a pending approval with subject_hash."""
    require_tenant_context(conn)

    # 1. Quality gate
    check_work_request_quality_gate(conn, tenant_id, client_entity_id, work_request_id)

    # 2. Check that at least one proposal exists
    proposals, _ = get_work_request_canonical_proposals_and_matches(
        conn, tenant_id, client_entity_id, work_request_id
    )
    if not proposals:
        raise NoProposalsError("Aucune écriture comptable active trouvée pour ce dossier.")

    # 3. Compute subject_hash
    subject_hash = compute_work_request_subject_hash(
        conn, tenant_id, client_entity_id, work_request_id
    )

    # 4. Resolve single_person_policy from client_entities if not explicitly specified
    with conn.cursor() as cur:
        if single_person_policy is None:
            cur.execute(
                "SELECT single_person_policy FROM client_entities WHERE tenant_id = %s AND id = %s;",
                (tenant_id, client_entity_id),
            )
            ce_row = cur.fetchone()
            single_person_policy = bool(ce_row[0]) if ce_row else False

        # Cancel any previous pending approvals for this work request
        cur.execute(
            """
            UPDATE approvals
            SET status = 'cancelled'
            WHERE tenant_id = %s AND work_request_id = %s AND status = 'pending';
            """,
            (tenant_id, work_request_id),
        )

        # Determine revision number
        cur.execute(
            """
            SELECT COALESCE(MAX(revision), 0) + 1
            FROM approvals
            WHERE tenant_id = %s AND work_request_id = %s;
            """,
            (tenant_id, work_request_id),
        )
        rev_row = cur.fetchone()
        assert rev_row is not None
        next_rev = rev_row[0]

        approval_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO approvals (
                id, tenant_id, client_entity_id, work_request_id, revision,
                subject_hash, status, prepared_by, single_person_policy
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
            RETURNING id, revision, subject_hash, status, created_at;
            """,
            (
                approval_id,
                tenant_id,
                client_entity_id,
                work_request_id,
                next_rev,
                subject_hash,
                prepared_by,
                single_person_policy,
            ),
        )
        app_row = cur.fetchone()

        # Update work request status
        cur.execute(
            """
            UPDATE work_requests
            SET status = 'awaiting_approval', updated_at = now()
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, work_request_id),
        )

    assert app_row is not None
    return {
        "id": str(app_row[0]),
        "revision": app_row[1],
        "subject_hash": app_row[2],
        "status": app_row[3],
        "created_at": app_row[4].isoformat() if hasattr(app_row[4], "isoformat") else str(app_row[4]),
    }


def decide_work_request_approval(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    approval_id: uuid.UUID,
    decider_id: uuid.UUID,
    decision: str,
    reason: str,
    expected_subject_hash: str | None = None,
) -> dict[str, Any]:
    """Decides (approves, rejects, cancels) a pending approval."""
    require_tenant_context(conn)

    if decision not in ("approved", "rejected", "cancelled"):
        raise ValueError(f"Décision invalide : {decision}")

    if not reason or not reason.strip():
        raise ValueError("Le motif de la décision est obligatoire.")

    with conn.cursor() as cur:
        # Fetch approval record
        cur.execute(
            """
            SELECT id, client_entity_id, work_request_id, revision, subject_hash,
                   status, prepared_by, single_person_policy
            FROM approvals
            WHERE tenant_id = %s AND id = %s
            FOR UPDATE;
            """,
            (tenant_id, approval_id),
        )
        row = cur.fetchone()
        if not row:
            raise ApprovalError("Demande de validation introuvable.")

        (
            _app_id,
            client_id,
            wr_id,
            _rev,
            stored_hash,
            cur_status,
            prepared_by,
            single_person,
        ) = row

        if cur_status != "pending":
            raise ApprovalStateError("Cette demande de validation n'est plus en attente.")

        # Check expected subject_hash if caller supplied one
        if expected_subject_hash and expected_subject_hash.strip() != stored_hash.strip():
            raise ApprovalHashMismatchError(
                "L'empreinte du dossier ne correspond pas à l'empreinte soumise."
            )

        # Invariant check: recompute subject_hash from live proposals
        current_hash = compute_work_request_subject_hash(conn, tenant_id, client_id, wr_id)
        if current_hash != stored_hash:
            raise ApprovalStaleError(
                "Le dossier a été modifié depuis la demande de validation. Une nouvelle validation est requise."
            )

        decider_reg_no = None
        decider_title = None

        if decision == "approved":
            # Segregation of duties: preparer cannot approve unless single_person_policy is true
            if not single_person and prepared_by and str(prepared_by) == str(decider_id):
                raise SegregationOfDutiesError(
                    "Le préparateur ne peut pas valider son propre dossier sans politique dérogatoire."
                )

            # Professional registration requirement
            cur.execute(
                """
                SELECT professional_title, professional_registration_no
                FROM memberships
                WHERE tenant_id = %s AND user_id = %s;
                """,
                (tenant_id, decider_id),
            )
            m_row = cur.fetchone()
            if not m_row or not m_row[1]:
                raise MissingRegistrationNumberError(
                    "L'approbateur doit posséder un numéro d'inscription professionnelle (OEC / Comptable Agréé)."
                )
            decider_title, decider_reg_no = m_row[0], m_row[1]

            # Quality gate re-check
            check_work_request_quality_gate(conn, tenant_id, client_id, wr_id)

        # Update approval row
        cur.execute(
            """
            UPDATE approvals
            SET status = %s,
                decided_by = %s,
                decided_at = now(),
                reason = %s,
                decider_registration_no = %s,
                decider_professional_title = %s
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status, decided_at;
            """,
            (
                decision,
                decider_id,
                reason,
                decider_reg_no,
                decider_title,
                tenant_id,
                approval_id,
            ),
        )
        updated = cur.fetchone()

        if decision == "approved":
            # Atomically mark all active proposals in this work request as approved
            cur.execute(
                """
                UPDATE journal_proposals
                SET status = 'approved'
                WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
                  AND status IN ('proposed', 'edited');
                """,
                (tenant_id, client_id, wr_id),
            )

            # Update work request status
            cur.execute(
                """
                UPDATE work_requests
                SET status = 'completed', updated_at = now()
                WHERE tenant_id = %s AND id = %s;
                """,
                (tenant_id, wr_id),
            )
        elif decision == "rejected":
            cur.execute(
                """
                UPDATE work_requests
                SET status = 'needs_attention', updated_at = now()
                WHERE tenant_id = %s AND id = %s;
                """,
                (tenant_id, wr_id),
            )

    assert updated is not None
    return {
        "id": str(updated[0]),
        "status": updated[1],
        "decided_at": updated[2].isoformat() if hasattr(updated[2], "isoformat") else str(updated[2]),
        "decision": decision,
        "subject_hash": stored_hash,
    }


def get_pending_approvals(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lists pending approvals in the tenant."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.client_entity_id, ce.legal_name, a.work_request_id,
                   a.revision, a.subject_hash, a.created_at, u.full_name as preparer_name
            FROM approvals a
            JOIN client_entities ce ON ce.id = a.client_entity_id AND ce.tenant_id = a.tenant_id
            LEFT JOIN users u ON u.id = a.prepared_by
            WHERE a.tenant_id = %s AND a.status = 'pending'
            ORDER BY a.created_at DESC
            LIMIT %s;
            """,
            (tenant_id, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "client_entity_id": str(r[1]),
                "client_name": str(r[2]),
                "work_request_id": str(r[3]),
                "revision": r[4],
                "subject_hash": r[5],
                "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                "preparer_name": str(r[7] or ""),
            }
            for r in rows
        ]
