"""Service layer for bank reconciliation in Moroccan bookkeeping.

Implements:
- Candidate generation and scoring across bank transactions and journal proposals.
- Detection of TVA retenue à la source (vat_withheld) with check for approved tax mapping.
- Strict double-match prevention: No bank line can belong to two accepted matches.
- Recording of audit events for all decisions.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack
from avenel.reconciliation.matcher import (
    CandidateItem,
    match_grouped_payments,
    match_single_pair,
    match_split_payments,
)


def _record_audit_event(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    data: dict[str, Any],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, %s, %s, %s, %s::jsonb);
            """,
            (tenant_id, actor_id, action, resource_type, str(resource_id), json.dumps(data)),
        )


def check_approved_withholding_mapping(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
) -> uuid.UUID | None:
    """Checks whether an approved tax mapping exists for VAT withholding (direction 'withholding')."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT account_id FROM client_tax_mappings
            WHERE tenant_id = %s AND client_entity_id = %s AND direction = 'withholding' AND approved_by IS NOT NULL
            LIMIT 1;
            """,
            (tenant_id, client_entity_id),
        )
        row = cur.fetchone()
        return uuid.UUID(str(row[0])) if row else None


def generate_reconciliation_matches(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    date_window_days: int | None = None,
) -> list[dict[str, Any]]:
    """Generates candidate reconciliation matches between bank transactions and journal proposals."""
    pack = get_jurisdiction_pack()
    if date_window_days is None:
        window_rule = pack.get_rule("bank.reconciliation.date_window_days")
        date_window_days = int(window_rule["value"]) if window_rule and window_rule.get("value") else 60

    # 1. Fetch bank transactions for this client not already in an accepted match
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bt.id, bt.amount, bt.booking_date, bt.description
            FROM bank_transactions bt
            WHERE bt.tenant_id = %s AND bt.client_entity_id = %s
              AND bt.id NOT IN (
                  SELECT rmi.bank_transaction_id
                  FROM reconciliation_match_items rmi
                  JOIN reconciliation_matches rm ON rm.id = rmi.match_id AND rm.tenant_id = rmi.tenant_id
                  WHERE rmi.tenant_id = %s AND rmi.bank_transaction_id IS NOT NULL AND rm.status = 'accepted'
              )
            ORDER BY bt.booking_date, bt.line_index;
            """,
            (tenant_id, client_entity_id, tenant_id),
        )
        bt_rows = cur.fetchall()

    bank_candidates = [
        CandidateItem(
            kind="bank_tx",
            item_id=str(r[0]),
            amount_mad=float(r[1]),
            date=r[2],
            label=r[3],
        )
        for r in bt_rows
    ]

    # 2. Fetch journal proposals for this work request not in an accepted match
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT jp.id, jp.entry_date, jp.label, jp.journal_code,
                   COALESCE(
                       (SELECT sum(GREATEST(debit_mad, credit_mad)) FROM journal_lines jpl WHERE jpl.journal_proposal_id = jp.id AND (jpl.account_code LIKE '3455%%' OR jpl.account_code LIKE '3456%%' OR jpl.account_code LIKE '445%%')),
                       0
                   ) as vat_mad,
                   COALESCE(
                       (SELECT sum(GREATEST(debit_mad, credit_mad)) FROM journal_lines jpl WHERE jpl.journal_proposal_id = jp.id AND jpl.counterparty_id IS NOT NULL),
                       0
                   ) as total_ttc_mad,
                   COALESCE(
                       (SELECT sum(GREATEST(debit_mad, credit_mad)) FROM journal_lines jpl WHERE jpl.journal_proposal_id = jp.id AND (jpl.account_code LIKE '61%%' OR jpl.account_code LIKE '71%%')),
                       0
                   ) as ht_mad
            FROM journal_proposals jp
            WHERE jp.tenant_id = %s AND jp.client_entity_id = %s AND jp.work_request_id = %s
              AND jp.id NOT IN (
                  SELECT rmi.journal_proposal_id
                  FROM reconciliation_match_items rmi
                  JOIN reconciliation_matches rm ON rm.id = rmi.match_id AND rm.tenant_id = rmi.tenant_id
                  WHERE rmi.tenant_id = %s AND rmi.journal_proposal_id IS NOT NULL AND rm.status = 'accepted'
              );
            """,
            (tenant_id, client_entity_id, work_request_id, tenant_id),
        )
        jp_rows = cur.fetchall()

    prop_candidates = [
        CandidateItem(
            kind="proposal",
            item_id=str(r[0]),
            amount_mad=float(r[5]),
            date=r[1],
            label=r[2],
            vat_mad=float(r[4]),
            ht_mad=float(r[6]),
        )
        for r in jp_rows
    ]

    generated_matches: list[dict[str, Any]] = []
    matched_bank_tx_ids: set[str] = set()

    # 3. Pairwise matching
    for b_item in bank_candidates:
        for p_item in prop_candidates:
            c = match_single_pair(b_item, p_item, date_window_days=date_window_days)
            if c:
                # Check withholding account mapping if vat_withheld
                if c.difference_kind == "vat_withheld":
                    withholding_acc = check_approved_withholding_mapping(conn, tenant_id, client_entity_id)
                    if withholding_acc is None:
                        # Raise ACCOUNT_UNMAPPED blocking issue
                        issue_id = uuid.uuid4()
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO issues (
                                    id, tenant_id, client_entity_id, work_request_id, code, severity, status,
                                    evidence_refs, subject_proposal_id
                                )
                                VALUES (%s, %s, %s, %s, 'ACCOUNT_UNMAPPED', 'blocking', 'open', %s, %s);
                                """,
                                (
                                    issue_id,
                                    tenant_id,
                                    client_entity_id,
                                    work_request_id,
                                    json.dumps([{
                                        "direction": "withholding",
                                        "reason": "Retenue à la source détectée sans compte approuvé dans client_tax_mappings",
                                        "difference_mad": c.difference_mad,
                                    }]),
                                    uuid.UUID(p_item.item_id),
                                ),
                            )

                # Persist proposed match
                match_id = uuid.uuid4()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO reconciliation_matches (
                            id, tenant_id, client_entity_id, work_request_id, status, score,
                            reasons, difference_mad, difference_kind
                        )
                        VALUES (%s, %s, %s, %s, 'proposed', %s, %s, %s, %s);
                        """,
                        (
                            match_id,
                            tenant_id,
                            client_entity_id,
                            work_request_id,
                            c.score,
                            json.dumps(c.reasons),
                            c.difference_mad,
                            c.difference_kind,
                        ),
                    )
                    # Insert bank item
                    cur.execute(
                        """
                        INSERT INTO reconciliation_match_items (
                            id, tenant_id, client_entity_id, match_id, bank_transaction_id, amount_mad
                        )
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (uuid.uuid4(), tenant_id, client_entity_id, match_id, uuid.UUID(b_item.item_id), b_item.amount_mad),
                    )
                    # Insert proposal item
                    cur.execute(
                        """
                        INSERT INTO reconciliation_match_items (
                            id, tenant_id, client_entity_id, match_id, journal_proposal_id, amount_mad
                        )
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (uuid.uuid4(), tenant_id, client_entity_id, match_id, uuid.UUID(p_item.item_id), p_item.amount_mad),
                    )

                matched_bank_tx_ids.add(b_item.item_id)
                generated_matches.append({
                    "id": match_id,
                    "score": c.score,
                    "difference_kind": c.difference_kind,
                    "difference_mad": c.difference_mad,
                    "bank_transaction_id": uuid.UUID(b_item.item_id),
                    "journal_proposal_id": uuid.UUID(p_item.item_id),
                })
                break

    # 4. Check for split payments (1 proposal -> multiple bank lines)
    for p_item in prop_candidates:
        unmatched_bank = [b for b in bank_candidates if b.item_id not in matched_bank_tx_ids]
        split_cand = match_split_payments(unmatched_bank, p_item, date_window_days=date_window_days)
        if split_cand:
            match_id = uuid.uuid4()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reconciliation_matches (
                        id, tenant_id, client_entity_id, work_request_id, status, score,
                        reasons, difference_mad, difference_kind
                    )
                    VALUES (%s, %s, %s, %s, 'proposed', %s, %s, %s, %s);
                    """,
                    (
                        match_id,
                        tenant_id,
                        client_entity_id,
                        work_request_id,
                        split_cand.score,
                        json.dumps(split_cand.reasons),
                        split_cand.difference_mad,
                        split_cand.difference_kind,
                    ),
                )
                for b_it in split_cand.bank_items:
                    cur.execute(
                        """
                        INSERT INTO reconciliation_match_items (
                            id, tenant_id, client_entity_id, match_id, bank_transaction_id, amount_mad
                        )
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (uuid.uuid4(), tenant_id, client_entity_id, match_id, uuid.UUID(b_it.item_id), b_it.amount_mad),
                    )
                    matched_bank_tx_ids.add(b_it.item_id)

                cur.execute(
                    """
                    INSERT INTO reconciliation_match_items (
                        id, tenant_id, client_entity_id, match_id, journal_proposal_id, amount_mad
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (uuid.uuid4(), tenant_id, client_entity_id, match_id, uuid.UUID(p_item.item_id), p_item.amount_mad),
                )
            generated_matches.append({
                "id": match_id,
                "score": split_cand.score,
                "difference_kind": split_cand.difference_kind,
                "difference_mad": split_cand.difference_mad,
            })

    # 5. Check for grouped payments (1 bank line -> multiple proposals)
    unmatched_bank = [b for b in bank_candidates if b.item_id not in matched_bank_tx_ids]
    for b_item in unmatched_bank:
        grouped_cand = match_grouped_payments(b_item, prop_candidates, date_window_days=date_window_days)
        if grouped_cand:
            match_id = uuid.uuid4()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reconciliation_matches (
                        id, tenant_id, client_entity_id, work_request_id, status, score,
                        reasons, difference_mad, difference_kind
                    )
                    VALUES (%s, %s, %s, %s, 'proposed', %s, %s, %s, %s);
                    """,
                    (
                        match_id,
                        tenant_id,
                        client_entity_id,
                        work_request_id,
                        grouped_cand.score,
                        json.dumps(grouped_cand.reasons),
                        grouped_cand.difference_mad,
                        grouped_cand.difference_kind,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO reconciliation_match_items (
                        id, tenant_id, client_entity_id, match_id, bank_transaction_id, amount_mad
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (uuid.uuid4(), tenant_id, client_entity_id, match_id, uuid.UUID(b_item.item_id), b_item.amount_mad),
                )
                matched_bank_tx_ids.add(b_item.item_id)

                for p_it in grouped_cand.proposal_items:
                    cur.execute(
                        """
                        INSERT INTO reconciliation_match_items (
                            id, tenant_id, client_entity_id, match_id, journal_proposal_id, amount_mad
                        )
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (uuid.uuid4(), tenant_id, client_entity_id, match_id, uuid.UUID(p_it.item_id), p_it.amount_mad),
                    )
            generated_matches.append({
                "id": match_id,
                "score": grouped_cand.score,
                "difference_kind": grouped_cand.difference_kind,
                "difference_mad": grouped_cand.difference_mad,
            })

    # 6. Unmatched bank lines raise BANK_LINE_UNMATCHED review issue
    for b_item in bank_candidates:
        if b_item.item_id not in matched_bank_tx_ids:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO issues (
                        id, tenant_id, client_entity_id, work_request_id, code, severity, status,
                        evidence_refs, subject_bank_transaction_id
                    )
                    VALUES (%s, %s, %s, %s, 'BANK_LINE_UNMATCHED', 'review', 'open', %s, %s);
                    """,
                    (
                        uuid.uuid4(),
                        tenant_id,
                        client_entity_id,
                        work_request_id,
                        json.dumps([{"amount": b_item.amount_mad, "label": b_item.label, "date": b_item.date.isoformat()}]),
                        uuid.UUID(b_item.item_id),
                    ),
                )

    return generated_matches


def accept_reconciliation_match(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    match_id: uuid.UUID,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Accepts a reconciliation match.

    MANDATORY INVARIANT: No bank line can belong to two accepted matches.
    Raises ValueError if any bank line in this match is already in another accepted match.
    """
    # 1. Fetch bank transactions in this match
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bank_transaction_id
            FROM reconciliation_match_items
            WHERE tenant_id = %s AND match_id = %s AND bank_transaction_id IS NOT NULL;
            """,
            (tenant_id, match_id),
        )
        bt_rows = cur.fetchall()

    if not bt_rows:
        raise ValueError("Match does not contain any bank transactions")

    bt_ids = [r[0] for r in bt_rows]

    # 2. Check for conflict: are any of these bank transactions already in an accepted match?
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rmi.bank_transaction_id
            FROM reconciliation_match_items rmi
            JOIN reconciliation_matches rm ON rm.id = rmi.match_id AND rm.tenant_id = rmi.tenant_id
            WHERE rmi.tenant_id = %s
              AND rmi.bank_transaction_id = ANY(%s)
              AND rm.status = 'accepted'
              AND rm.id <> %s;
            """,
            (tenant_id, bt_ids, match_id),
        )
        conflict = cur.fetchone()

    if conflict:
        raise ValueError("Impossible d'accepter le rapprochement : une ligne bancaire appartient déjà à un rapprochement accepté.")

    # 3. Update match status to 'accepted'
    decider_uuid = uuid.UUID(actor_id) if actor_id and len(actor_id) == 36 else None
    now = datetime.datetime.now(datetime.UTC)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE reconciliation_matches
            SET status = 'accepted', decided_by = %s, decided_at = %s
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status, score, difference_mad, difference_kind;
            """,
            (decider_uuid, now, tenant_id, match_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Match {match_id} not found")

        # 4. Mark conflicting proposed matches as 'superseded'
        cur.execute(
            """
            UPDATE reconciliation_matches rm
            SET status = 'superseded'
            FROM reconciliation_match_items rmi
            WHERE rm.id = rmi.match_id AND rm.tenant_id = rmi.tenant_id
              AND rm.tenant_id = %s
              AND rmi.bank_transaction_id = ANY(%s)
              AND rm.status = 'proposed'
              AND rm.id <> %s;
            """,
            (tenant_id, bt_ids, match_id),
        )

        cur.execute(
            """
            SELECT client_entity_id, work_request_id
            FROM reconciliation_matches
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, match_id),
        )
        match_meta = cur.fetchone()

    if match_meta:
        from avenel.proposals.bank_proposals import (
            transition_bq_proposals_on_match_accepted,
        )

        transition_bq_proposals_on_match_accepted(
            conn=conn,
            tenant_id=tenant_id,
            client_entity_id=match_meta[0],
            work_request_id=match_meta[1],
            match_id=match_id,
        )

    _record_audit_event(
        conn=conn,
        tenant_id=tenant_id,
        actor_id=actor_id or "system",
        action="reconciliation.match_accepted",
        resource_type="reconciliation_matches",
        resource_id=match_id,
        data={"bank_transactions": [str(b) for b in bt_ids]},
    )

    return {
        "id": row[0],
        "status": row[1],
        "score": float(row[2]) if row[2] is not None else None,
        "difference_mad": float(row[3]),
        "difference_kind": row[4],
    }


def reject_reconciliation_match(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    match_id: uuid.UUID,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Rejects a candidate reconciliation match."""
    decider_uuid = uuid.UUID(actor_id) if actor_id and len(actor_id) == 36 else None
    now = datetime.datetime.now(datetime.UTC)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE reconciliation_matches
            SET status = 'rejected', decided_by = %s, decided_at = %s
            WHERE tenant_id = %s AND id = %s
            RETURNING id, status;
            """,
            (decider_uuid, now, tenant_id, match_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Match {match_id} not found")

        cur.execute(
            """
            SELECT client_entity_id, work_request_id
            FROM reconciliation_matches
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, match_id),
        )
        match_meta = cur.fetchone()

    if match_meta:
        from avenel.proposals.bank_proposals import (
            transition_bq_proposals_on_match_rejected,
        )

        transition_bq_proposals_on_match_rejected(
            conn=conn,
            tenant_id=tenant_id,
            client_entity_id=match_meta[0],
            work_request_id=match_meta[1],
            match_id=match_id,
        )

    _record_audit_event(
        conn=conn,
        tenant_id=tenant_id,
        actor_id=actor_id or "system",
        action="reconciliation.match_rejected",
        resource_type="reconciliation_matches",
        resource_id=match_id,
        data={},
    )

    return {"id": row[0], "status": row[1]}


def list_reconciliation_matches(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Lists all reconciliation matches for a given work request with details."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rm.id, rm.status, rm.score, rm.reasons, rm.difference_mad, rm.difference_kind,
                   rm.decided_by, rm.decided_at
            FROM reconciliation_matches rm
            WHERE rm.tenant_id = %s AND rm.work_request_id = %s
            ORDER BY rm.score DESC NULLS LAST;
            """,
            (tenant_id, work_request_id),
        )
        matches = cur.fetchall()

    results: list[dict[str, Any]] = []
    for m in matches:
        m_id = m[0]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rmi.id, rmi.bank_transaction_id, rmi.journal_proposal_id, rmi.amount_mad,
                       bt.booking_date, bt.description as bt_desc,
                       jp.entry_date, jp.label as jp_label
                FROM reconciliation_match_items rmi
                LEFT JOIN bank_transactions bt ON bt.id = rmi.bank_transaction_id AND bt.tenant_id = rmi.tenant_id
                LEFT JOIN journal_proposals jp ON jp.id = rmi.journal_proposal_id AND jp.tenant_id = rmi.tenant_id
                WHERE rmi.tenant_id = %s AND rmi.match_id = %s;
                """,
                (tenant_id, m_id),
            )
            items = cur.fetchall()

        results.append({
            "id": m[0],
            "status": m[1],
            "score": float(m[2]) if m[2] is not None else None,
            "reasons": m[3] if isinstance(m[3], list) else json.loads(m[3] or "[]"),
            "difference_mad": float(m[4]),
            "difference_kind": m[5],
            "decided_by": m[6],
            "decided_at": m[7].isoformat() if m[7] else None,
            "items": [
                {
                    "id": it[0],
                    "bank_transaction_id": it[1],
                    "journal_proposal_id": it[2],
                    "amount_mad": float(it[3]),
                    "bank_date": it[4].isoformat() if it[4] else None,
                    "bank_desc": it[5],
                    "proposal_date": it[6].isoformat() if it[6] else None,
                    "proposal_label": it[7],
                }
                for it in items
            ],
        })

    return results
