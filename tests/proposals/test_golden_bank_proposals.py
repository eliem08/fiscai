"""Golden tests for Bank Journal Proposals (BQ Proposals) per Phase 4 requirements.

Covers:
1. Supplier payment: Dr counterparty account / Cr bank ledger account.
2. Customer receipt: Dr bank / Cr counterparty; with vat_withheld,
   Dr bank + Dr withholding receivable (client_tax_mappings 'withholding') / Cr counterparty for full TTC.
3. Bank fees and commissions: Dr fee account + Dr deductible VAT (if fee shows VAT) / Cr bank,
   accounts via client_tax_mappings, ACCOUNT_UNMAPPED if missing.
4. Unmatched line: proposal with a suspense account from client mapping (needs_expert default),
   plus BANK_LINE_UNMATCHED issue.
"""

from __future__ import annotations

import datetime
import uuid
import pytest

from avenel.proposals.bank_proposals import (
    AccountUnmappedError,
    BankLineProposalInput,
    build_bank_journal_proposal,
)


def test_golden_bank_proposal_supplier_payment():
    """Supplier payment: Dr counterparty account (4411) / Cr bank ledger account (5141)."""
    tenant_id = uuid.uuid4()
    client_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    supplier_acc_id = uuid.uuid4()
    bank_acc_id = uuid.uuid4()
    counterparty_id = uuid.uuid4()

    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=tx_id,
        bank_statement_id=uuid.uuid4(),
        line_index=3,
        booking_date=datetime.date(2026, 3, 20),
        amount_mad=-4800.00,  # disbursement
        description="VIR FOURNISSEUR STE CASABLANCAISE SARL",
        journal_code="BQ01",
        bank_ledger_account_id=bank_acc_id,
        bank_ledger_account_code="5141001",
        pattern="supplier_payment",
        counterparty_id=counterparty_id,
        counterparty_account_id=supplier_acc_id,
        counterparty_account_code="4411000",
    )

    res = build_bank_journal_proposal(inp)

    assert res.journal_code == "BQ01"
    assert res.source_bank_transaction_id == tx_id
    assert "bank.proposal.supplier_payment" in res.rule_refs
    assert len(res.lines) == 2

    # Line 1: Dr Fournisseur
    l1 = res.lines[0]
    assert l1.account_code == "4411000"
    assert l1.debit_mad == 4800.00
    assert l1.credit_mad == 0.0
    assert l1.counterparty_id == counterparty_id
    assert l1.evidence_refs == [{"bank_transaction_id": str(tx_id), "line_index": 3}]

    # Line 2: Cr Banque
    l2 = res.lines[1]
    assert l2.account_code == "5141001"
    assert l2.debit_mad == 0.0
    assert l2.credit_mad == 4800.00
    assert l2.evidence_refs == [{"bank_transaction_id": str(tx_id), "line_index": 3}]


def test_golden_bank_proposal_customer_receipt_with_vat_withheld():
    """Customer receipt with vat_withheld:

    Dr bank (net received) + Dr withholding receivable / Cr counterparty for full TTC.
    """
    tenant_id = uuid.uuid4()
    client_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    customer_acc_id = uuid.uuid4()
    bank_acc_id = uuid.uuid4()
    withholding_acc_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    # Invoice TTC is 12,000 MAD (HT: 10,000, TVA 20%: 2,000).
    # 75% withheld = 1,500 MAD.
    # Customer paid net in bank = 10,500 MAD.
    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=tx_id,
        bank_statement_id=uuid.uuid4(),
        line_index=7,
        booking_date=datetime.date(2026, 3, 22),
        amount_mad=10500.00,  # receipt
        description="VIR ENCAISSEMENT CLIENT ATLAS DISTRIB FACT 2026-089",
        journal_code="BQ",
        bank_ledger_account_id=bank_acc_id,
        bank_ledger_account_code="5141",
        pattern="customer_receipt",
        counterparty_id=customer_id,
        counterparty_account_id=customer_acc_id,
        counterparty_account_code="3421",
        withholding_mad=1500.00,
        withholding_account_id=withholding_acc_id,
        withholding_account_code="3456",
    )

    res = build_bank_journal_proposal(inp)

    assert len(res.lines) == 3
    assert "bank.proposal.customer_receipt_withheld" in res.rule_refs

    # Line 1: Dr Banque 10,500 MAD
    assert res.lines[0].account_code == "5141"
    assert res.lines[0].debit_mad == 10500.00
    assert res.lines[0].credit_mad == 0.0

    # Line 2: Dr Retenue à la source 1,500 MAD
    assert res.lines[1].account_code == "3456"
    assert res.lines[1].debit_mad == 1500.00
    assert res.lines[1].credit_mad == 0.0

    # Line 3: Cr Client pour le plein TTC 12,000 MAD
    assert res.lines[2].account_code == "3421"
    assert res.lines[2].debit_mad == 0.0
    assert res.lines[2].credit_mad == 12000.00
    assert res.lines[2].counterparty_id == customer_id

    # Arithmetic balance verified
    tot_dr = sum(l.debit_mad for l in res.lines)
    tot_cr = sum(l.credit_mad for l in res.lines)
    assert tot_dr == tot_cr == 12000.00


def test_golden_bank_proposal_bank_fees_and_commissions():
    """Bank fees and commissions: Dr fee account (6147) + Dr deductible VAT (34552) / Cr bank."""
    tenant_id = uuid.uuid4()
    client_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    fee_acc_id = uuid.uuid4()
    vat_acc_id = uuid.uuid4()
    bank_acc_id = uuid.uuid4()

    # Fee total: 110.00 MAD TTC (100.00 MAD HT + 10.00 MAD TVA 10%)
    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=tx_id,
        bank_statement_id=uuid.uuid4(),
        line_index=12,
        booking_date=datetime.date(2026, 3, 31),
        amount_mad=-110.00,  # fee disbursement
        description="FRAIS DE TENUE DE COMPTE ET COMMISSIONS",
        journal_code="BQ",
        bank_ledger_account_id=bank_acc_id,
        bank_ledger_account_code="5141",
        pattern="bank_fee",
        fee_account_id=fee_acc_id,
        fee_account_code="6147",
        fee_vat_account_id=vat_acc_id,
        fee_vat_account_code="34552",
        fee_vat_rate=0.10,
    )

    res = build_bank_journal_proposal(inp)

    assert len(res.lines) == 3
    assert "bank.proposal.bank_fee" in res.rule_refs

    # Line 1: Dr Services bancaires HT 100.00 MAD
    assert res.lines[0].account_code == "6147"
    assert res.lines[0].debit_mad == 100.00
    assert res.lines[0].credit_mad == 0.0

    # Line 2: Dr TVA déductible sur charges 10.00 MAD
    assert res.lines[1].account_code == "34552"
    assert res.lines[1].debit_mad == 10.00
    assert res.lines[1].credit_mad == 0.0
    assert res.lines[1].tax_code == "VAT_10"

    # Line 3: Cr Banque 110.00 MAD
    assert res.lines[2].account_code == "5141"
    assert res.lines[2].debit_mad == 0.0
    assert res.lines[2].credit_mad == 110.00

    tot_dr = sum(l.debit_mad for l in res.lines)
    tot_cr = sum(l.credit_mad for l in res.lines)
    assert tot_dr == tot_cr == 110.00


def test_bank_fees_missing_mapping_raises_account_unmapped():
    """Missing fee or VAT mapping raises AccountUnmappedError."""
    inp = BankLineProposalInput(
        tenant_id=uuid.uuid4(),
        client_entity_id=uuid.uuid4(),
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=uuid.uuid4(),
        bank_statement_id=uuid.uuid4(),
        line_index=1,
        booking_date=datetime.date(2026, 3, 31),
        amount_mad=-55.00,
        description="COMMISSION VIREMENT",
        journal_code="BQ",
        bank_ledger_account_id=uuid.uuid4(),
        bank_ledger_account_code="5141",
        pattern="bank_fee",
        fee_account_id=None,  # Missing!
        fee_account_code=None,
    )

    with pytest.raises(AccountUnmappedError) as exc_info:
        build_bank_journal_proposal(inp)
    assert "ACCOUNT_UNMAPPED" in str(exc_info.value)


def test_golden_bank_proposal_unmatched_line_with_suspense_account():
    """Unmatched bank line posts to suspense account (4711) and raises BANK_LINE_UNMATCHED."""
    tenant_id = uuid.uuid4()
    client_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    bank_acc_id = uuid.uuid4()

    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=tx_id,
        bank_statement_id=uuid.uuid4(),
        line_index=15,
        booking_date=datetime.date(2026, 3, 28),
        amount_mad=-1250.00,  # unknown disbursement
        description="PRELEVEMENT DIVERS NON IDENTIFIE",
        journal_code="BQ",
        bank_ledger_account_id=bank_acc_id,
        bank_ledger_account_code="5141",
        pattern="unmatched",
    )

    res = build_bank_journal_proposal(inp)

    assert len(res.lines) == 2
    assert "bank.proposal.unmatched" in res.rule_refs

    # Line 1: Dr Compte d'attente 4711
    assert res.lines[0].account_code == "4711"
    assert res.lines[0].debit_mad == 1250.00
    assert res.lines[0].credit_mad == 0.0

    # Line 2: Cr Banque 5141
    assert res.lines[1].account_code == "5141"
    assert res.lines[1].debit_mad == 0.0
    assert res.lines[1].credit_mad == 1250.00

    # Issue BANK_LINE_UNMATCHED raised
    assert len(res.issues_to_raise) == 1
    assert res.issues_to_raise[0]["code"] == "BANK_LINE_UNMATCHED"
    assert res.issues_to_raise[0]["severity"] == "review"
    assert res.issues_to_raise[0]["subject_bank_transaction_id"] == tx_id


def test_golden_bank_proposal_customer_receipt_is_only_withholding():
    """Customer receipt with IS 5% withholding only (LF 2026):

    HT = 10,000 MAD, TVA = 2,000 MAD, TTC = 12,000 MAD.
    IS 5% on HT = 500 MAD.
    Net bank receipt = 11,500 MAD.
    Journal proposal:
      Dr Bank: 11,500 MAD
      Dr Withholding receivable: 500 MAD
      Cr Customer: 12,000 MAD (Full TTC)
    """
    tenant_id = uuid.uuid4()
    client_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    customer_acc_id = uuid.uuid4()
    bank_acc_id = uuid.uuid4()
    withholding_acc_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=tx_id,
        bank_statement_id=uuid.uuid4(),
        line_index=8,
        booking_date=datetime.date(2026, 3, 24),
        amount_mad=11500.00,  # net receipt
        description="VIR ENCAISSEMENT CLIENT PRESTATION RETENUE IS 5%",
        journal_code="BQ",
        bank_ledger_account_id=bank_acc_id,
        bank_ledger_account_code="5141",
        pattern="customer_receipt",
        counterparty_id=customer_id,
        counterparty_account_id=customer_acc_id,
        counterparty_account_code="3421",
        withholding_mad=500.00,  # 5% on HT
        withholding_account_id=withholding_acc_id,
        withholding_account_code="3456",
    )

    res = build_bank_journal_proposal(inp)

    assert len(res.lines) == 3
    assert res.lines[0].debit_mad == 11500.00
    assert res.lines[1].debit_mad == 500.00
    assert res.lines[2].credit_mad == 12000.00

    tot_dr = sum(l.debit_mad for l in res.lines)
    tot_cr = sum(l.credit_mad for l in res.lines)
    assert tot_dr == tot_cr == 12000.00


def test_golden_bank_proposal_customer_receipt_combined_withholding():
    """Customer receipt with Combined Withholding (75% TVA + 5% IS on HT):

    HT = 10,000 MAD, TVA = 2,000 MAD, TTC = 12,000 MAD.
    TVA 75% withheld = 1,500 MAD.
    IS 5% on HT withheld = 500 MAD.
    Total withheld = 2,000 MAD.
    Net bank receipt = 10,000 MAD.
    Journal proposal:
      Dr Bank: 10,000 MAD
      Dr Withholding receivable: 2,000 MAD
      Cr Customer: 12,000 MAD (Full TTC)
    """
    tenant_id = uuid.uuid4()
    client_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    customer_acc_id = uuid.uuid4()
    bank_acc_id = uuid.uuid4()
    withholding_acc_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    inp = BankLineProposalInput(
        tenant_id=tenant_id,
        client_entity_id=client_id,
        work_request_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        bank_transaction_id=tx_id,
        bank_statement_id=uuid.uuid4(),
        line_index=9,
        booking_date=datetime.date(2026, 3, 25),
        amount_mad=10000.00,  # net receipt
        description="VIR ENCAISSEMENT CLIENT RETENUES COMBINEES TVA ET IS",
        journal_code="BQ",
        bank_ledger_account_id=bank_acc_id,
        bank_ledger_account_code="5141",
        pattern="customer_receipt",
        counterparty_id=customer_id,
        counterparty_account_id=customer_acc_id,
        counterparty_account_code="3421",
        withholding_mad=2000.00,  # 1500 TVA + 500 IS
        withholding_account_id=withholding_acc_id,
        withholding_account_code="3456",
    )

    res = build_bank_journal_proposal(inp)

    assert len(res.lines) == 3
    assert res.lines[0].debit_mad == 10000.00
    assert res.lines[1].debit_mad == 2000.00
    assert res.lines[2].credit_mad == 12000.00

    tot_dr = sum(l.debit_mad for l in res.lines)
    tot_cr = sum(l.credit_mad for l in res.lines)
    assert tot_dr == tot_cr == 12000.00

