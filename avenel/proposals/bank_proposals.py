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
    """Inserts a generated bank proposal and its lines atomically into PostgreSQL."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (
                id, tenant_id, client_entity_id, work_request_id, revision,
                journal_code, entry_date, label, source_bank_transaction_id,
                status, rule_refs, proposed_by, content_hash
            )
            VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, 'proposed', %s, %s, %s)
            RETURNING id;
            """,
            (
                res.proposal_id,
                res.tenant_id,
                res.client_entity_id,
                res.work_request_id,
                res.journal_code,
                res.entry_date,
                res.label,
                res.source_bank_transaction_id,
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
