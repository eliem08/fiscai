"""Journal proposal management service for Moroccan bookkeeping (Phase 3).

Enforces:
- Rule A.4: Double tenant isolation (application authorization + PostgreSQL RLS).
- Rule A.5: Posted, approved, and audited data is immutable.
- Atomic insertion of balanced lines.
- Proposal revision management (superseding immutable older revisions).
- No per-entry approval endpoint (approval occurs only at monthly-file level, Phase 5).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import psycopg

from avenel.proposals.duplicates import (
    detect_probable_duplicates,
    record_duplicate_issues_if_any,
)
from avenel.proposals.entry_builder import (
    ProposalGenerationBlockedError,
    ProposedEntry,
    build_journal_proposal,
    validate_line_evidence_refs,
)
from avenel.tenancy.auth import require_tenant_context


class ProposalNotFoundError(Exception):
    pass


class ProposalImmutableError(Exception):
    pass


class ProposalUnbalancedError(Exception):
    pass


def _compute_proposal_content_hash(lines: list[dict[str, Any]]) -> str:
    """Computes a deterministic SHA-256 hash across proposal lines."""
    canonical_items = []
    for l in sorted(lines, key=lambda x: int(x.get("line_no", 0))):
        canonical_items.append({
            "line_no": l.get("line_no"),
            "account_code": l.get("account_code"),
            "debit_mad": f"{float(l.get('debit_mad', 0.0)):.2f}",
            "credit_mad": f"{float(l.get('credit_mad', 0.0)):.2f}",
            "currency": l.get("currency", "MAD"),
            "label": l.get("label", ""),
        })
    raw_str = json.dumps(canonical_items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def generate_and_save_proposal_for_document(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    document_id: uuid.UUID,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Extracts fields from document and generates + persists a balanced proposal in journal_proposals.

    If generation is blocked (e.g. ACCOUNT_UNMAPPED or FX_RATE_MISSING):
    records a blocking issue in issues table, creates NO proposal lines, and returns blocked status.
    """
    require_tenant_context(conn)

    # 1. Fetch document and extraction details
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.doc_type, e.fields
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            JOIN extractions e ON e.document_version_id = dv.id AND e.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s AND d.client_entity_id = %s AND d.id = %s
            ORDER BY dv.version_number DESC, e.created_at DESC
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, document_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Aucune extraction valide trouvée pour le document {document_id}")

        doc_type = str(row[0]) if row[0] else "invoice_purchase"
        extracted_fields = row[1] if isinstance(row[1], dict) else json.loads(row[1])

    # 2. Check for probable duplicates
    inv_no = extracted_fields.get("invoice_number", {}).get("value")
    inv_date = extracted_fields.get("invoice_date", {}).get("value")
    supplier_ice = extracted_fields.get("supplier_ice", {}).get("value")
    supplier_name = extracted_fields.get("supplier_name", {}).get("value")
    tot_ttc = float(extracted_fields.get("total_ttc", {}).get("value") or 0.0)

    matches = detect_probable_duplicates(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        current_document_id=document_id,
        supplier_ice=supplier_ice,
        supplier_name=supplier_name,
        invoice_number=inv_no,
        total_ttc=tot_ttc,
        invoice_date=inv_date,
    )
    record_duplicate_issues_if_any(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        work_request_id=work_request_id,
        document_id=document_id,
        matches=matches,
    )

    # 3. Build proposed entry (or catch blocking errors)
    try:
        entry: ProposedEntry = build_journal_proposal(
            conn=conn,
            tenant_id=tenant_id,
            client_entity_id=client_entity_id,
            document_id=document_id,
            doc_type=doc_type,
            extracted_fields=extracted_fields,
            actor_id=actor_id,
        )
    except ProposalGenerationBlockedError as blocked_err:
        # Record blocking issue in issues table
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO issues (
                    tenant_id, client_entity_id, work_request_id, subject_document_id,
                    code, severity, status, evidence_refs
                ) VALUES (%s, %s, %s, %s, %s, 'blocking', 'open', %s::jsonb);
                """,
                (
                    tenant_id,
                    client_entity_id,
                    work_request_id,
                    document_id,
                    blocked_err.code,
                    json.dumps([{"detail": blocked_err.detail, "rule_key": blocked_err.rule_key}]),
                ),
            )
        # Create NO proposal lines in journal_proposals or journal_lines
        return {
            "status": "blocked",
            "issue_code": blocked_err.code,
            "detail": blocked_err.detail,
            "proposal_id": None,
            "lines": [],
        }

    # 4. Record any non-blocking detected issues (review severity)
    if entry.detected_issues:
        with conn.cursor() as cur:
            for issue in entry.detected_issues:
                cur.execute(
                    """
                    INSERT INTO issues (
                        tenant_id, client_entity_id, work_request_id, subject_document_id,
                        code, severity, status, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'open', %s::jsonb);
                    """,
                    (
                        tenant_id,
                        client_entity_id,
                        work_request_id,
                        document_id,
                        issue["code"],
                        issue.get("severity", "review"),
                        json.dumps([{"reason": issue.get("reason", "")}]),
                    ),
                )

    # 5. Insert into journal_proposals and journal_lines atomically
    proposal_id = uuid.uuid4()
    lines_dicts = [
        {
            "line_no": l.line_no,
            "account_id": l.account_id,
            "account_code": l.account_code,
            "counterparty_id": l.counterparty_id,
            "label": l.label,
            "currency": l.currency,
            "debit_tx": l.debit_tx,
            "credit_tx": l.credit_tx,
            "fx_rate": l.fx_rate,
            "fx_rate_date": l.fx_rate_date,
            "fx_source": l.fx_source,
            "debit_mad": l.debit_mad,
            "credit_mad": l.credit_mad,
            "tax_code": l.tax_code,
            "due_date": l.due_date,
            "evidence_refs": l.evidence_refs,
        }
        for l in entry.lines
    ]

    content_hash = _compute_proposal_content_hash(lines_dicts)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (
                id, tenant_id, client_entity_id, work_request_id, revision,
                journal_code, entry_date, label, source_document_id,
                status, rule_refs, proposed_by, content_hash
            ) VALUES (
                %s, %s, %s, %s, 1,
                %s, %s, %s, %s,
                'proposed', %s, %s, %s
            ) RETURNING id;
            """,
            (
                proposal_id,
                tenant_id,
                client_entity_id,
                work_request_id,
                entry.journal_code,
                entry.entry_date,
                entry.label,
                document_id,
                entry.rule_refs,
                entry.proposed_by,
                content_hash,
            ),
        )

        for l in lines_dicts:
            line_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO journal_lines (
                    id, tenant_id, client_entity_id, journal_proposal_id, line_no,
                    account_id, account_code, counterparty_id, label,
                    currency, debit_tx, credit_tx, fx_rate, fx_rate_date, fx_source,
                    debit_mad, credit_mad, tax_code, due_date, evidence_refs
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::jsonb
                );
                """,
                (
                    line_id,
                    tenant_id,
                    client_entity_id,
                    proposal_id,
                    l["line_no"],
                    l["account_id"],
                    l["account_code"],
                    l["counterparty_id"],
                    l["label"],
                    l["currency"],
                    l["debit_tx"],
                    l["credit_tx"],
                    l["fx_rate"],
                    l["fx_rate_date"],
                    l["fx_source"],
                    l["debit_mad"],
                    l["credit_mad"],
                    l["tax_code"],
                    l["due_date"],
                    json.dumps(l["evidence_refs"]),
                ),
            )

    return get_proposal_by_id(conn, tenant_id, proposal_id)


def get_proposal_by_id(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    proposal_id: uuid.UUID,
) -> dict[str, Any]:
    """Retrieves proposal and its lines."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, client_entity_id, work_request_id, revision,
                   journal_code, entry_date, label, source_document_id,
                   status, supersedes_id, rule_refs, proposed_by, content_hash, created_at
            FROM journal_proposals
            WHERE tenant_id = %s AND id = %s
            LIMIT 1;
            """,
            (tenant_id, proposal_id),
        )
        row = cur.fetchone()
        if not row:
            raise ProposalNotFoundError(f"Proposition {proposal_id} introuvable.")

        prop_dict = {
            "id": str(row[0]),
            "client_entity_id": str(row[1]),
            "work_request_id": str(row[2]),
            "revision": row[3],
            "journal_code": row[4],
            "entry_date": row[5].isoformat() if row[5] else None,
            "label": row[6],
            "source_document_id": str(row[7]) if row[7] else None,
            "status": row[8],
            "supersedes_id": str(row[9]) if row[9] else None,
            "rule_refs": row[10],
            "proposed_by": row[11],
            "content_hash": row[12],
            "created_at": row[13].isoformat() if row[13] else None,
            "lines": [],
        }

        cur.execute(
            """
            SELECT id, line_no, account_id, account_code, counterparty_id, label,
                   currency, debit_tx, credit_tx, fx_rate, fx_rate_date, fx_source,
                   debit_mad, credit_mad, tax_code, due_date, evidence_refs
            FROM journal_lines
            WHERE tenant_id = %s AND journal_proposal_id = %s
            ORDER BY line_no ASC;
            """,
            (tenant_id, proposal_id),
        )
        lines_rows = cur.fetchall()
        for lr in lines_rows:
            (
                _l_id, l_no, acc_id, acc_code, cp_id, lbl,
                curr, d_tx, c_tx, fx_r, fx_d, fx_s,
                d_mad, c_mad, t_code, due_d, ev_raw,
            ) = lr
            ev = ev_raw if isinstance(ev_raw, list) else json.loads(ev_raw)
            prop_dict["lines"].append({
                "id": str(_l_id),
                "line_no": l_no,
                "account_id": str(acc_id),
                "account_code": acc_code,
                "counterparty_id": str(cp_id) if cp_id else None,
                "label": lbl,
                "currency": curr,
                "debit_tx": float(d_tx),
                "credit_tx": float(c_tx),
                "fx_rate": float(fx_r),
                "fx_rate_date": fx_d.isoformat() if fx_d else None,
                "fx_source": fx_s,
                "debit_mad": float(d_mad),
                "credit_mad": float(c_mad),
                "tax_code": t_code,
                "due_date": due_d.isoformat() if due_d else None,
                "evidence_refs": ev,
            })

    return prop_dict


def list_proposals_for_work_request(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    """Lists proposals for a work request, filtering out superseded ones by default."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        query = """
            SELECT id FROM journal_proposals
            WHERE tenant_id = %s AND work_request_id = %s
        """
        params: list[Any] = [tenant_id, work_request_id]
        if not include_superseded:
            query += " AND status <> 'superseded'"
        query += " ORDER BY created_at DESC;"

        cur.execute(query, tuple(params))
        ids = [uuid.UUID(str(r[0])) for r in cur.fetchall()]

    return [get_proposal_by_id(conn, tenant_id, pid) for pid in ids]


def create_proposal_revision(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    current_proposal_id: uuid.UUID,
    updated_lines: list[dict[str, Any]],
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Creates a new proposal revision (N+1) and marks previous revision as superseded (Rule A.5)."""
    require_tenant_context(conn)
    current = get_proposal_by_id(conn, tenant_id, current_proposal_id)

    if current["status"] in ("approved", "exported"):
        raise ProposalImmutableError(
            f"La proposition {current_proposal_id} est déjà validée ({current['status']}) et immuable."
        )

    # Verify arithmetic balance on new lines
    total_debit = round(sum(float(l.get("debit_mad", 0.0)) for l in updated_lines), 2)
    total_credit = round(sum(float(l.get("credit_mad", 0.0)) for l in updated_lines), 2)
    if total_debit != total_credit or len(updated_lines) < 2:
        raise ProposalUnbalancedError(
            f"Les écritures ne sont pas équilibrées : débit={total_debit:.2f}, crédit={total_credit:.2f}"
        )

    # Validate evidence refs on updated lines
    for l in updated_lines:
        evs = l.get("evidence_refs", [])
        validate_line_evidence_refs(evs)

    new_proposal_id = uuid.uuid4()
    new_revision = int(current["revision"]) + 1
    new_hash = _compute_proposal_content_hash(updated_lines)

    with conn.cursor() as cur:
        # 1. Mark existing proposal as superseded
        cur.execute(
            """
            UPDATE journal_proposals
            SET status = 'superseded'
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, current_proposal_id),
        )

        # 2. Insert new revision
        user_uuid = uuid.UUID(actor_id) if actor_id and len(actor_id) == 36 else None
        cur.execute(
            """
            INSERT INTO journal_proposals (
                id, tenant_id, client_entity_id, work_request_id, revision,
                journal_code, entry_date, label, source_document_id,
                status, supersedes_id, rule_refs, proposed_by, last_edited_by, content_hash
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                'edited', %s, %s, 'human', %s, %s
            );
            """,
            (
                new_proposal_id,
                tenant_id,
                uuid.UUID(current["client_entity_id"]),
                uuid.UUID(current["work_request_id"]),
                new_revision,
                current["journal_code"],
                current["entry_date"],
                current["label"],
                uuid.UUID(current["source_document_id"]) if current["source_document_id"] else None,
                current_proposal_id,
                current["rule_refs"],
                user_uuid,
                new_hash,
            ),
        )

        # 3. Insert new lines
        for idx, l in enumerate(updated_lines, start=1):
            line_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO journal_lines (
                    id, tenant_id, client_entity_id, journal_proposal_id, line_no,
                    account_id, account_code, counterparty_id, label,
                    currency, debit_tx, credit_tx, fx_rate, fx_rate_date, fx_source,
                    debit_mad, credit_mad, tax_code, due_date, evidence_refs
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::jsonb
                );
                """,
                (
                    line_id,
                    tenant_id,
                    uuid.UUID(current["client_entity_id"]),
                    new_proposal_id,
                    idx,
                    uuid.UUID(str(l["account_id"])),
                    str(l["account_code"]),
                    uuid.UUID(str(l["counterparty_id"])) if l.get("counterparty_id") else None,
                    str(l["label"]),
                    str(l.get("currency", "MAD")),
                    float(l.get("debit_tx", l.get("debit_mad", 0.0))),
                    float(l.get("credit_tx", l.get("credit_mad", 0.0))),
                    float(l.get("fx_rate", 1.0)),
                    l.get("fx_rate_date"),
                    l.get("fx_source"),
                    float(l["debit_mad"]),
                    float(l["credit_mad"]),
                    l.get("tax_code"),
                    l.get("due_date"),
                    json.dumps(l.get("evidence_refs", [])),
                ),
            )

    return get_proposal_by_id(conn, tenant_id, new_proposal_id)
