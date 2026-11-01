"""Bank journal proposal generator (BQ proposals) for Moroccan bookkeeping.

Implements ARCHITECTURE.md Part D and Phase 4 requirements:
- Generates a BQ proposal (journal code from bank_accounts.journal_code) for every bank line.
- Attaches source_bank_transaction_id and evidence pointing to the statement line.
- Handles 4 canonical cases:
  1. Supplier payment: Dr counterparty account / Cr bank ledger account.
  2. Customer receipt: Dr bank / Cr counterparty; with vat_withheld:
     Dr bank + Dr withholding receivable (client_tax_mappings 'withholding') / Cr counterparty for full TTC.
  3. Bank fees and commissions: Dr fee account + Dr deductible VAT (if fee shows VAT) / Cr bank,
     accounts via client_tax_mappings (raises AccountUnmappedError if missing).
  4. Unmatched line: proposal with a suspense account from client mapping (needs_expert default),
     plus BANK_LINE_UNMATCHED issue.
- Strict arithmetic balancing on all proposals.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack
from avenel.proposals.entry_builder import validate_line_evidence_refs


class AccountUnmappedError(Exception):
    """Raised when an approved account mapping is missing in client_tax_mappings."""


@dataclass(frozen=True)
class BankLineProposalInput:
    tenant_id: uuid.UUID
    client_entity_id: uuid.UUID
    work_request_id: uuid.UUID
    bank_account_id: uuid.UUID
    bank_transaction_id: uuid.UUID
    bank_statement_id: uuid.UUID | None
    line_index: int
    booking_date: datetime.date
    amount_mad: float
    description: str
    journal_code: str
    bank_ledger_account_id: uuid.UUID
    bank_ledger_account_code: str
    # Pattern classification
    pattern: str  # 'supplier_payment' | 'customer_receipt' | 'bank_fee' | 'unmatched'
    # Counterparty details (for supplier_payment / customer_receipt)
    counterparty_id: uuid.UUID | None = None
    counterparty_account_id: uuid.UUID | None = None
    counterparty_account_code: str | None = None
    # Withholding details (for customer_receipt with withholding)
    withholding_mad: float = 0.0
    withholding_account_id: uuid.UUID | None = None
    withholding_account_code: str | None = None
    # Fee details (for bank_fee)
    fee_account_id: uuid.UUID | None = None
    fee_account_code: str | None = None
    fee_vat_account_id: uuid.UUID | None = None
    fee_vat_account_code: str | None = None
    fee_vat_rate: float = 0.0
    # Suspense details (for unmatched)
    suspense_account_id: uuid.UUID | None = None
    suspense_account_code: str | None = None


@dataclass
class BankProposalLine:
    line_no: int
    account_id: uuid.UUID
    account_code: str
    label: str
    currency: str
    debit_mad: float
    credit_mad: float
    tax_code: str | None = None
    counterparty_id: uuid.UUID | None = None
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BankProposalResult:
    proposal_id: uuid.UUID
    tenant_id: uuid.UUID
    client_entity_id: uuid.UUID
    work_request_id: uuid.UUID
    journal_code: str
    entry_date: datetime.date
    label: str
    source_bank_transaction_id: uuid.UUID
    rule_refs: list[str]
    proposed_by: str
    lines: list[BankProposalLine]
    content_hash: str
    revision: int = 1
    supersedes_id: uuid.UUID | None = None
    issues_to_raise: list[dict[str, Any]] = field(default_factory=list)


def _compute_proposal_hash(lines: list[BankProposalLine]) -> str:
    canonical = [
        {
            "line_no": ln.line_no,
            "account_code": ln.account_code,
            "debit_mad": f"{ln.debit_mad:.2f}",
            "credit_mad": f"{ln.credit_mad:.2f}",
            "currency": ln.currency,
            "label": ln.label,
        }
        for ln in sorted(lines, key=lambda x: x.line_no)
    ]
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_bank_journal_proposal(inp: BankLineProposalInput) -> BankProposalResult:
    """Constructs a deterministic, arithmetically balanced BQ proposal for a bank line."""
    evidence = [
        {
            "bank_transaction_id": str(inp.bank_transaction_id),
            "line_index": inp.line_index,
        }
    ]
    lines: list[BankProposalLine] = []
    rule_refs: list[str] = []
    issues: list[dict[str, Any]] = []
    proposal_id = uuid.uuid4()
    currency = "MAD"

    if inp.pattern == "supplier_payment":
        rule_refs.append("bank.proposal.supplier_payment")
        if not inp.counterparty_account_id or not inp.counterparty_account_code:
            raise AccountUnmappedError("Compte fournisseur manquant pour le règlement bancaire (ACCOUNT_UNMAPPED).")

        amount_abs = round(abs(inp.amount_mad), 2)
        # Line 1: Dr Fournisseur
        lines.append(
            BankProposalLine(
                line_no=1,
                account_id=inp.counterparty_account_id,
                account_code=inp.counterparty_account_code,
                label=f"Règlement fournisseur {inp.description}",
                currency=currency,
                debit_mad=amount_abs,
                credit_mad=0.0,
                counterparty_id=inp.counterparty_id,
                evidence_refs=evidence,
            )
        )
        # Line 2: Cr Banque
        lines.append(
            BankProposalLine(
                line_no=2,
                account_id=inp.bank_ledger_account_id,
                account_code=inp.bank_ledger_account_code,
                label=f"Paiement bancaire {inp.description}",
                currency=currency,
                debit_mad=0.0,
                credit_mad=amount_abs,
                evidence_refs=evidence,
            )
        )

    elif inp.pattern == "customer_receipt":
        rule_refs.append("bank.proposal.customer_receipt")
        if not inp.counterparty_account_id or not inp.counterparty_account_code:
            raise AccountUnmappedError("Compte client manquant pour l'encaissement bancaire (ACCOUNT_UNMAPPED).")

        net_received = round(abs(inp.amount_mad), 2)
        withholding = round(abs(inp.withholding_mad), 2)

        if withholding > 0:
            # Encaissement avec retenue à la source
            rule_refs.append("bank.proposal.customer_receipt_withheld")
            if not inp.withholding_account_id or not inp.withholding_account_code:
                raise AccountUnmappedError(
                    "Compte de retenue à la source manquant dans client_tax_mappings direction 'withholding' (ACCOUNT_UNMAPPED)."
                )

            total_ttc = round(net_received + withholding, 2)
            # Line 1: Dr Banque (net reçu)
            lines.append(
                BankProposalLine(
                    line_no=1,
                    account_id=inp.bank_ledger_account_id,
                    account_code=inp.bank_ledger_account_code,
                    label=f"Encaissement bancaire net {inp.description}",
                    currency=currency,
                    debit_mad=net_received,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            # Line 2: Dr Retenue à la source (créance fiscale)
            lines.append(
                BankProposalLine(
                    line_no=2,
                    account_id=inp.withholding_account_id,
                    account_code=inp.withholding_account_code,
                    label=f"Retenue à la source sur encaissement {inp.description}",
                    currency=currency,
                    debit_mad=withholding,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            # Line 3: Cr Client pour le montant total TTC
            lines.append(
                BankProposalLine(
                    line_no=3,
                    account_id=inp.counterparty_account_id,
                    account_code=inp.counterparty_account_code,
                    label=f"Règlement client TTC {inp.description}",
                    currency=currency,
                    debit_mad=0.0,
                    credit_mad=total_ttc,
                    counterparty_id=inp.counterparty_id,
                    evidence_refs=evidence,
                )
            )
        else:
            # Encaissement simple sans retenue
            # Line 1: Dr Banque
            lines.append(
                BankProposalLine(
                    line_no=1,
                    account_id=inp.bank_ledger_account_id,
                    account_code=inp.bank_ledger_account_code,
                    label=f"Encaissement bancaire {inp.description}",
                    currency=currency,
                    debit_mad=net_received,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            # Line 2: Cr Client
            lines.append(
                BankProposalLine(
                    line_no=2,
                    account_id=inp.counterparty_account_id,
                    account_code=inp.counterparty_account_code,
                    label=f"Règlement client {inp.description}",
                    currency=currency,
                    debit_mad=0.0,
                    credit_mad=net_received,
                    counterparty_id=inp.counterparty_id,
                    evidence_refs=evidence,
                )
            )

    elif inp.pattern == "bank_fee":
        rule_refs.append("bank.proposal.bank_fee")
        if not inp.fee_account_id or not inp.fee_account_code:
            raise AccountUnmappedError(
                "Compte de charges pour frais bancaires non configuré dans client_tax_mappings direction 'bank_fee' (ACCOUNT_UNMAPPED)."
            )

        fee_ttc = round(abs(inp.amount_mad), 2)
        if inp.fee_vat_rate > 0:
            if not inp.fee_vat_account_id or not inp.fee_vat_account_code:
                raise AccountUnmappedError(
                    "Compte de TVA déductible sur frais bancaires non configuré (ACCOUNT_UNMAPPED)."
                )

            # Calcul TVA déductible (ex: 10% sur commissions bancaires)
            fee_vat = round(fee_ttc * (inp.fee_vat_rate / (1.0 + inp.fee_vat_rate)), 2)
            fee_ht = round(fee_ttc - fee_vat, 2)

            # Line 1: Dr Services bancaires (HT)
            lines.append(
                BankProposalLine(
                    line_no=1,
                    account_id=inp.fee_account_id,
                    account_code=inp.fee_account_code,
                    label=f"Frais et commissions bancaires HT {inp.description}",
                    currency=currency,
                    debit_mad=fee_ht,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            # Line 2: Dr TVA déductible sur commissions
            lines.append(
                BankProposalLine(
                    line_no=2,
                    account_id=inp.fee_vat_account_id,
                    account_code=inp.fee_vat_account_code,
                    label=f"TVA déductible sur frais bancaires {inp.description}",
                    currency=currency,
                    debit_mad=fee_vat,
                    credit_mad=0.0,
                    tax_code="VAT_10",
                    evidence_refs=evidence,
                )
            )
            # Line 3: Cr Banque (TTC)
            lines.append(
                BankProposalLine(
                    line_no=3,
                    account_id=inp.bank_ledger_account_id,
                    account_code=inp.bank_ledger_account_code,
                    label=f"Prélèvement frais bancaires {inp.description}",
                    currency=currency,
                    debit_mad=0.0,
                    credit_mad=fee_ttc,
                    evidence_refs=evidence,
                )
            )
        else:
            # Frais sans TVA
            lines.append(
                BankProposalLine(
                    line_no=1,
                    account_id=inp.fee_account_id,
                    account_code=inp.fee_account_code,
                    label=f"Frais bancaires {inp.description}",
                    currency=currency,
                    debit_mad=fee_ttc,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            lines.append(
                BankProposalLine(
                    line_no=2,
                    account_id=inp.bank_ledger_account_id,
                    account_code=inp.bank_ledger_account_code,
                    label=f"Prélèvement bancaire {inp.description}",
                    currency=currency,
                    debit_mad=0.0,
                    credit_mad=fee_ttc,
                    evidence_refs=evidence,
                )
            )

    else:
        # Pattern unmatched : ligne non rapprochée vers compte d'attente + anomalie BANK_LINE_UNMATCHED
        rule_refs.append("bank.proposal.unmatched")
        amount_abs = round(abs(inp.amount_mad), 2)

        # Compte d'attente : client mapping 'suspense' ou suggestion pack 'accounting.suspense.default_account'
        pack = get_jurisdiction_pack()
        default_suspense_rule = pack.get_rule("accounting.suspense.default_account")
        suspense_code = inp.suspense_account_code or (
            str(default_suspense_rule["value"]) if default_suspense_rule and default_suspense_rule.get("value") else "4711"
        )
        suspense_id = inp.suspense_account_id or uuid.uuid5(inp.tenant_id, f"suspense-{suspense_code}")

        if inp.amount_mad < 0:
            # Débit compte d'attente / Crédit Banque
            lines.append(
                BankProposalLine(
                    line_no=1,
                    account_id=suspense_id,
                    account_code=suspense_code,
                    label=f"Opération bancaire en attente {inp.description}",
                    currency=currency,
                    debit_mad=amount_abs,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            lines.append(
                BankProposalLine(
                    line_no=2,
                    account_id=inp.bank_ledger_account_id,
                    account_code=inp.bank_ledger_account_code,
                    label=f"Sortie bancaire {inp.description}",
                    currency=currency,
                    debit_mad=0.0,
                    credit_mad=amount_abs,
                    evidence_refs=evidence,
                )
            )
        else:
            # Débit Banque / Crédit compte d'attente
            lines.append(
                BankProposalLine(
                    line_no=1,
                    account_id=inp.bank_ledger_account_id,
                    account_code=inp.bank_ledger_account_code,
                    label=f"Entrée bancaire {inp.description}",
                    currency=currency,
                    debit_mad=amount_abs,
                    credit_mad=0.0,
                    evidence_refs=evidence,
                )
            )
            lines.append(
                BankProposalLine(
                    line_no=2,
                    account_id=suspense_id,
                    account_code=suspense_code,
                    label=f"Recette en attente {inp.description}",
                    currency=currency,
                    debit_mad=0.0,
                    credit_mad=amount_abs,
                    evidence_refs=evidence,
                )
            )

        issues.append({
            "code": "BANK_LINE_UNMATCHED",
            "severity": "review",
            "message": f"Ligne bancaire non rapprochée : {inp.description} ({inp.amount_mad:.2f} MAD)",
            "subject_bank_transaction_id": inp.bank_transaction_id,
        })

    # Validate arithmetic balance
    tot_debit = round(sum(ln.debit_mad for ln in lines), 2)
    tot_credit = round(sum(ln.credit_mad for ln in lines), 2)
    if tot_debit != tot_credit:
        raise ValueError(f"Proposition bancaire non équilibrée : Débit={tot_debit:.2f}, Crédit={tot_credit:.2f}")

    # Validate evidence references on all lines
    for ln in lines:
        validate_line_evidence_refs(ln.evidence_refs)

    content_hash = _compute_proposal_hash(lines)

    return BankProposalResult(
        proposal_id=proposal_id,
        tenant_id=inp.tenant_id,
        client_entity_id=inp.client_entity_id,
        work_request_id=inp.work_request_id,
        journal_code=inp.journal_code,
        entry_date=inp.booking_date,
        label=f"BQ: {inp.description[:80]}",
        source_bank_transaction_id=inp.bank_transaction_id,
        rule_refs=rule_refs,
        proposed_by="rules",
        lines=lines,
        content_hash=content_hash,
        issues_to_raise=issues,
    )


def save_bank_journal_proposal(
    conn: psycopg.Connection,
    res: BankProposalResult,
) -> uuid.UUID:
    """Inserts a generated bank proposal and its lines atomically into PostgreSQL.

    Enforces invariant: exactly one active proposal per source_bank_transaction_id.
    If supersedes_id is provided or an active proposal exists for source_bank_transaction_id,
    the previous proposal is updated to status = 'superseded' in the same transaction.
    """
    with conn.cursor() as cur:
        # Supersede any active proposal for this bank transaction
        if res.source_bank_transaction_id:
            cur.execute(
                """
                UPDATE journal_proposals
                SET status = 'superseded'
                WHERE tenant_id = %s
                  AND source_bank_transaction_id = %s
                  AND status IN ('proposed', 'edited', 'approved')
                  AND id <> %s;
                """,
                (res.tenant_id, res.source_bank_transaction_id, res.proposal_id),
            )

        cur.execute(
            """
            INSERT INTO journal_proposals (
                id, tenant_id, client_entity_id, work_request_id, revision,
                journal_code, entry_date, label, source_bank_transaction_id,
                status, supersedes_id, rule_refs, proposed_by, content_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'proposed', %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                res.proposal_id,
                res.tenant_id,
                res.client_entity_id,
                res.work_request_id,
                res.revision,
                res.journal_code,
                res.entry_date,
                res.label,
                res.source_bank_transaction_id,
                res.supersedes_id,
                res.rule_refs,
                res.proposed_by,
                res.content_hash,
            ),
        )

        for ln in res.lines:
            line_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO journal_lines (
                    id, tenant_id, client_entity_id, journal_proposal_id, line_no,
                    account_id, account_code, counterparty_id, label,
                    currency, debit_tx, credit_tx, fx_rate, fx_rate_date, fx_source,
                    debit_mad, credit_mad, tax_code, evidence_refs
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, 1.0, %s, 'bank_statement',
                    %s, %s, %s, %s::jsonb
                );
                """,
                (
                    line_id,
                    res.tenant_id,
                    res.client_entity_id,
                    res.proposal_id,
                    ln.line_no,
                    ln.account_id,
                    ln.account_code,
                    ln.counterparty_id,
                    ln.label,
                    ln.currency,
                    ln.debit_mad,
                    ln.credit_mad,
                    res.entry_date,
                    ln.debit_mad,
                    ln.credit_mad,
                    ln.tax_code,
                    json.dumps(ln.evidence_refs),
                ),
            )

        for iss in res.issues_to_raise:
            cur.execute(
                """
                INSERT INTO issues (
                    id, tenant_id, client_entity_id, work_request_id, code, severity, status,
                    evidence_refs, subject_bank_transaction_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'open', %s::jsonb, %s);
                """,
                (
                    uuid.uuid4(),
                    res.tenant_id,
                    res.client_entity_id,
                    res.work_request_id,
                    iss["code"],
                    iss["severity"],
                    json.dumps([{"proposal_id": str(res.proposal_id), "description": iss["message"]}]),
                    iss["subject_bank_transaction_id"],
                ),
            )

    return res.proposal_id


def create_initial_suspense_proposal_for_bank_tx(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    bank_transaction_id: uuid.UUID,
    supersedes_id: uuid.UUID | None = None,
    revision: int = 1,
) -> uuid.UUID:
    """Generates and saves the initial suspense proposal for an unmatched bank transaction."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bt.amount, bt.booking_date, bt.description, bt.line_index,
                   ba.id as bank_acc_id, ba.journal_code, ba.ledger_account_id,
                   ca.account_code as bank_account_code
            FROM bank_transactions bt
            JOIN bank_accounts ba ON ba.id = bt.bank_account_id AND ba.tenant_id = bt.tenant_id
            JOIN chart_accounts ca ON ca.id = ba.ledger_account_id AND ca.tenant_id = ba.tenant_id
            WHERE bt.tenant_id = %s AND bt.id = %s;
            """,
            (tenant_id, bank_transaction_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Transaction bancaire {bank_transaction_id} introuvable")

        amount, booking_date, desc, line_idx, bank_acc_id, journal_code, ledger_acc_id, bank_acc_code = row

        # Fetch suspense account mapping
        cur.execute(
            """
            SELECT ca.id, ca.account_code
            FROM client_tax_mappings ctm
            JOIN chart_accounts ca ON ca.id = ctm.account_id AND ca.tenant_id = ctm.tenant_id
            WHERE ctm.tenant_id = %s AND ctm.client_entity_id = %s AND ctm.direction = 'suspense'
            LIMIT 1;
            """,
            (tenant_id, client_entity_id),
        )
        susp_row = cur.fetchone()
        susp_id = susp_row[0] if susp_row else None
        susp_code = susp_row[1] if susp_row else None

        if not susp_id:
            pack = get_jurisdiction_pack()
            default_suspense_rule = pack.get_rule("accounting.suspense.default_account")
            susp_code = (
                str(default_suspense_rule["value"])
                if default_suspense_rule and default_suspense_rule.get("value")
                else "4711"
            )
            cur.execute(
                """
                SELECT id FROM chart_accounts
                WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, susp_code),
            )
            c_row = cur.fetchone()
            if c_row:
                susp_id = c_row[0]
            else:
                susp_id = uuid.uuid4()
                cur.execute(
                    """
                    INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
                    VALUES (%s, %s, %s, %s, %s, 'cgnc_seed')
                    RETURNING id;
                    """,
                    (susp_id, tenant_id, client_entity_id, susp_code, "Compte d'attente (opérations à régulariser)"),
                )

    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        work_request_id=work_request_id,
        bank_account_id=bank_acc_id,
        bank_transaction_id=bank_transaction_id,
        bank_statement_id=None,
        line_index=line_idx or 1,
        booking_date=booking_date,
        amount_mad=float(amount),
        description=desc,
        journal_code=journal_code or "BQ",
        bank_ledger_account_id=ledger_acc_id,
        bank_ledger_account_code=bank_acc_code,
        pattern="unmatched",
        suspense_account_id=susp_id,
        suspense_account_code=susp_code,
    )

    res = build_bank_journal_proposal(inp)
    res.revision = revision
    res.supersedes_id = supersedes_id
    return save_bank_journal_proposal(conn, res)


def transition_bq_proposals_on_match_accepted(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    match_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Transitions BQ proposals when a match is accepted.

    Within the same database transaction:
    - Suspense proposal is superseded.
    - Counterparty BQ proposal is inserted with status='proposed', revision=old_rev+1, supersedes_id=old_id.
    - BANK_LINE_UNMATCHED issue for the bank transaction is resolved.
    """
    created_proposal_ids: list[uuid.UUID] = []
    with conn.cursor() as cur:
        # Fetch match items
        cur.execute(
            """
            SELECT rm.difference_mad, rm.difference_kind,
                   rmi.bank_transaction_id, rmi.journal_proposal_id
            FROM reconciliation_matches rm
            JOIN reconciliation_match_items rmi ON rmi.match_id = rm.id AND rmi.tenant_id = rm.tenant_id
            WHERE rm.tenant_id = %s AND rm.id = %s;
            """,
            (tenant_id, match_id),
        )
        rows = cur.fetchall()

    if not rows:
        return created_proposal_ids

    diff_mad = float(rows[0][0])
    diff_kind = rows[0][1]

    # Bank transactions and invoice proposals in this match
    bank_tx_ids = [r[2] for r in rows if r[2] is not None]
    invoice_prop_ids = [r[3] for r in rows if r[3] is not None]

    for bt_id in bank_tx_ids:
        with conn.cursor() as cur:
            # Bank transaction info
            cur.execute(
                """
                SELECT bt.amount, bt.booking_date, bt.description, bt.line_index,
                       ba.id as bank_acc_id, ba.journal_code, ba.ledger_account_id,
                       ca.account_code as bank_account_code
                FROM bank_transactions bt
                JOIN bank_accounts ba ON ba.id = bt.bank_account_id AND ba.tenant_id = bt.tenant_id
                JOIN chart_accounts ca ON ca.id = ba.ledger_account_id AND ca.tenant_id = ba.tenant_id
                WHERE bt.tenant_id = %s AND bt.id = %s;
                """,
                (tenant_id, bt_id),
            )
            bt_row = cur.fetchone()
            if not bt_row:
                continue
            bt_amount, bt_date, bt_desc, bt_line_idx, bank_acc_id, journal_code, ledger_acc_id, bank_acc_code = bt_row

            # Active proposal for this bank transaction
            cur.execute(
                """
                SELECT id, revision
                FROM journal_proposals
                WHERE tenant_id = %s AND source_bank_transaction_id = %s
                  AND status IN ('proposed', 'edited', 'approved')
                ORDER BY revision DESC LIMIT 1;
                """,
                (tenant_id, bt_id),
            )
            active_prop = cur.fetchone()
            old_prop_id = active_prop[0] if active_prop else None
            old_rev = active_prop[1] if active_prop else 0

            # Matched invoice counterparty details
            cp_id = None
            cp_acc_id = None
            cp_acc_code = None
            if invoice_prop_ids:
                cur.execute(
                    """
                    SELECT jl.counterparty_id, jl.account_id, jl.account_code
                    FROM journal_lines jl
                    WHERE jl.tenant_id = %s AND jl.journal_proposal_id = %s
                      AND jl.counterparty_id IS NOT NULL
                    LIMIT 1;
                    """,
                    (tenant_id, invoice_prop_ids[0]),
                )
                cp_row = cur.fetchone()
                if cp_row:
                    cp_id, cp_acc_id, cp_acc_code = cp_row

            # Withholding mapping if needed
            wh_acc_id = None
            wh_acc_code = None
            wh_amount = 0.0
            if diff_kind in ("vat_withheld", "withholding_other") and diff_mad > 0:
                wh_amount = diff_mad
                cur.execute(
                    """
                    SELECT ca.id, ca.account_code
                    FROM client_tax_mappings ctm
                    JOIN chart_accounts ca ON ca.id = ctm.account_id AND ca.tenant_id = ctm.tenant_id
                    WHERE ctm.tenant_id = %s AND ctm.client_entity_id = %s AND ctm.direction = 'withholding'
                    LIMIT 1;
                    """,
                    (tenant_id, client_entity_id),
                )
                wh_row = cur.fetchone()
                if wh_row:
                    wh_acc_id, wh_acc_code = wh_row

        pattern = "customer_receipt" if float(bt_amount) > 0 else "supplier_payment"
        inp = BankLineProposalInput(
            tenant_id=tenant_id,
            client_entity_id=client_entity_id,
            work_request_id=work_request_id,
            bank_account_id=bank_acc_id,
            bank_transaction_id=bt_id,
            bank_statement_id=None,
            line_index=bt_line_idx or 1,
            booking_date=bt_date,
            amount_mad=float(bt_amount),
            description=bt_desc,
            journal_code=journal_code or "BQ",
            bank_ledger_account_id=ledger_acc_id,
            bank_ledger_account_code=bank_acc_code,
            pattern=pattern,
            counterparty_id=cp_id,
            counterparty_account_id=cp_acc_id,
            counterparty_account_code=cp_acc_code,
            withholding_mad=wh_amount,
            withholding_account_id=wh_acc_id,
            withholding_account_code=wh_acc_code,
        )

        res = build_bank_journal_proposal(inp)
        res.revision = old_rev + 1
        res.supersedes_id = old_prop_id
        prop_id = save_bank_journal_proposal(conn, res)
        created_proposal_ids.append(prop_id)

        # Resolve open BANK_LINE_UNMATCHED issue
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE issues
                SET status = 'resolved', resolved_at = now(), resolution = 'fixed'
                WHERE tenant_id = %s AND subject_bank_transaction_id = %s
                  AND code = 'BANK_LINE_UNMATCHED' AND status = 'open';
                """,
                (tenant_id, bt_id),
            )

    return created_proposal_ids


def transition_bq_proposals_on_match_rejected(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    match_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Transitions BQ proposals when a match is rejected.

    Within the same database transaction:
    - The counterparty BQ proposal is superseded.
    - A new suspense proposal revision is restored.
    - A BANK_LINE_UNMATCHED issue is opened/restored.
    """
    restored_proposal_ids: list[uuid.UUID] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rmi.bank_transaction_id
            FROM reconciliation_match_items rmi
            WHERE rmi.tenant_id = %s AND rmi.match_id = %s AND rmi.bank_transaction_id IS NOT NULL;
            """,
            (tenant_id, match_id),
        )
        bt_rows = cur.fetchall()

    for r in bt_rows:
        bt_id = r[0]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, revision
                FROM journal_proposals
                WHERE tenant_id = %s AND source_bank_transaction_id = %s
                  AND status IN ('proposed', 'edited', 'approved')
                ORDER BY revision DESC LIMIT 1;
                """,
                (tenant_id, bt_id),
            )
            row = cur.fetchone()
            old_id = row[0] if row else None
            old_rev = row[1] if row else 0

        new_rev = old_rev + 1
        suspense_id = create_initial_suspense_proposal_for_bank_tx(
            conn=conn,
            tenant_id=tenant_id,
            client_entity_id=client_entity_id,
            work_request_id=work_request_id,
            bank_transaction_id=bt_id,
            supersedes_id=old_id,
            revision=new_rev,
        )
        restored_proposal_ids.append(suspense_id)

    return restored_proposal_ids
