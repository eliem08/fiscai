"""Probable duplicate invoice detection for Moroccan bookkeeping proposals.

Enforces ARCHITECTURE.md Part D.2 / Part G Phase 3:
- Same counterparty AND (same invoice number OR (same TTC AND |date delta| <= window from pack)).
- Window lives in the pack (`invoice.duplicate_window_days`).
- Issue code: `DUPLICATE_PROBABLE` from `issues.yaml`.
- Gate: Probable duplicate recall >= 99% on fixtures (ARCHITECTURE.md Part H).
"""

from __future__ import annotations

import datetime
import json
import re
import uuid
from dataclasses import dataclass

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack


@dataclass(frozen=True)
class ProbableDuplicateMatch:
    conflicting_document_id: uuid.UUID
    conflicting_proposal_id: uuid.UUID | None
    conflicting_invoice_number: str | None
    conflicting_total_ttc: float
    conflicting_invoice_date: str | None
    match_kind: str  # 'exact_number' or 'amount_and_date_window'
    confidence: float
    reason: str


def get_duplicate_window_days() -> int:
    """Reads duplicate date window from Moroccan jurisdiction pack."""
    pack = get_jurisdiction_pack()
    rule = pack.get_rule("invoice.duplicate_window_days")
    if rule and rule.get("value") is not None:
        try:
            return int(rule["value"])
        except (ValueError, TypeError):
            pass
    return 20


def _normalize_invoice_number(num: str | None) -> str:
    if not num:
        return ""
    return re.sub(r"[\s\-_/\\.]+", "", str(num)).upper()


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", str(name).strip().lower())


def detect_probable_duplicates(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    current_document_id: uuid.UUID,
    supplier_ice: str | None,
    supplier_name: str | None,
    invoice_number: str | None,
    total_ttc: float,
    invoice_date: datetime.date | str | None,
    date_window_days: int | None = None,
) -> list[ProbableDuplicateMatch]:
    """Detects probable duplicate invoices in the database for the same client entity.

    Rule:
    same counterparty AND (same invoice number OR (same TTC AND |date delta| <= window from pack)).
    """
    effective_window = date_window_days if date_window_days is not None else get_duplicate_window_days()
    norm_no = _normalize_invoice_number(invoice_number)
    norm_name = _normalize_name(supplier_name)
    norm_ice = str(supplier_ice).strip() if supplier_ice else None

    date_obj: datetime.date | None = None
    if isinstance(invoice_date, str) and invoice_date.strip():
        try:
            date_obj = datetime.date.fromisoformat(invoice_date.strip())
        except ValueError:
            date_obj = None
    elif isinstance(invoice_date, datetime.date):
        date_obj = invoice_date

    matches: list[ProbableDuplicateMatch] = []

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, e.fields, jp.id
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            JOIN extractions e ON e.document_version_id = dv.id AND e.tenant_id = d.tenant_id
            LEFT JOIN journal_proposals jp ON jp.source_document_id = d.id AND jp.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s
              AND d.client_entity_id = %s
              AND d.id <> %s
              AND d.status NOT IN ('quarantined', 'rejected');
            """,
            (tenant_id, client_entity_id, current_document_id),
        )
        rows = cur.fetchall()

        for row in rows:
            other_doc_id = uuid.UUID(str(row[0]))
            fields_val = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            proposal_id = uuid.UUID(str(row[2])) if row[2] else None

            other_ice_val = fields_val.get("supplier_ice", {}).get("value")
            other_ice = str(other_ice_val).strip() if other_ice_val else None
            other_name = fields_val.get("supplier_name", {}).get("value")
            other_no = fields_val.get("invoice_number", {}).get("value")
            other_ttc = fields_val.get("total_ttc", {}).get("value")
            other_date_str = fields_val.get("invoice_date", {}).get("value")

            # 1. Counterparty check: SAME COUNTERPARTY IS STRICTLY REQUIRED
            supplier_matched = False
            if norm_ice and other_ice and norm_ice == other_ice or norm_name and other_name and norm_name == _normalize_name(other_name):
                supplier_matched = True

            # If counterparty does NOT match, NEVER flagged
            if not supplier_matched:
                continue

            # 2. Branch A: Same invoice number
            other_norm_no = _normalize_invoice_number(other_no)
            if norm_no and other_norm_no and norm_no == other_norm_no:
                matches.append(
                    ProbableDuplicateMatch(
                        conflicting_document_id=other_doc_id,
                        conflicting_proposal_id=proposal_id,
                        conflicting_invoice_number=other_no,
                        conflicting_total_ttc=float(other_ttc) if other_ttc is not None else 0.0,
                        conflicting_invoice_date=other_date_str,
                        match_kind="exact_number",
                        confidence=0.99,
                        reason=f"Même numéro de facture '{invoice_number}' détecté pour le même fournisseur.",
                    )
                )
                continue

            # 3. Branch B: Same TTC AND |date delta| <= window from pack
            if other_ttc is not None:
                try:
                    amount_diff = abs(float(total_ttc) - float(other_ttc))
                except (ValueError, TypeError):
                    amount_diff = 999.0

                if amount_diff <= 0.01:
                    date_in_window = False
                    if date_obj and other_date_str:
                        try:
                            other_d = datetime.date.fromisoformat(other_date_str.strip())
                            delta_days = abs((date_obj - other_d).days)
                            if delta_days <= effective_window:
                                date_in_window = True
                        except ValueError:
                            date_in_window = False

                    if date_in_window:
                        matches.append(
                            ProbableDuplicateMatch(
                                conflicting_document_id=other_doc_id,
                                conflicting_proposal_id=proposal_id,
                                conflicting_invoice_number=other_no,
                                conflicting_total_ttc=float(other_ttc),
                                conflicting_invoice_date=other_date_str,
                                match_kind="amount_and_date_window",
                                confidence=0.92,
                                reason=(
                                    f"Même montant TTC ({total_ttc:.2f} MAD) et date dans la fenêtre "
                                    f"(≤ {effective_window} jours) pour le même fournisseur."
                                ),
                            )
                        )

    return matches


def record_duplicate_issues_if_any(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    document_id: uuid.UUID,
    matches: list[ProbableDuplicateMatch],
) -> None:
    """Inserts review issues into the issues table using code DUPLICATE_PROBABLE from issues.yaml."""
    if not matches:
        return

    with conn.cursor() as cur:
        for match in matches:
            evidence = {
                "conflicting_document_id": str(match.conflicting_document_id),
                "conflicting_proposal_id": str(match.conflicting_proposal_id) if match.conflicting_proposal_id else None,
                "invoice_number": match.conflicting_invoice_number,
                "total_ttc": match.conflicting_total_ttc,
                "invoice_date": match.conflicting_invoice_date,
                "match_kind": match.match_kind,
                "reason": match.reason,
            }
            cur.execute(
                """
                INSERT INTO issues (
                    tenant_id, client_entity_id, work_request_id, subject_document_id,
                    code, severity, status, evidence_refs
                ) VALUES (%s, %s, %s, %s, 'DUPLICATE_PROBABLE', 'review', 'open', %s::jsonb);
                """,
                (tenant_id, client_entity_id, work_request_id, document_id, json.dumps([evidence])),
            )
