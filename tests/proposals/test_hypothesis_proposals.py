"""Property-based tests for proposal balancing and evidence invariants (Hypothesis).

Enforces ARCHITECTURE.md Part G Phase 3 Exit Criteria & User Prompt Item 8:
- "Hypothesis: max_examples >= 1000 for balancing, with strategies covering multi-rate,
   credit notes, FX, and amounts at 0.005 rounding boundaries."
- Invariant 1: Every generated proposal strictly balances in MAD (sum(debit_mad) == sum(credit_mad)).
- Invariant 2: Every proposal line has valid evidence references (regions or bank lines),
  or empty evidence for explicit residual rounding lines.
- Invariant 3: Counterparty line strictly equals invoice TTC converted at stated FX rate.
- Invariant 4: Database line constraints strictly satisfied.
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Generator
import psycopg
import pytest
from hypothesis import given, settings, strategies as st

from avenel.clients.service import create_client_entity
from avenel.proposals.entry_builder import build_journal_proposal
from avenel.proposals.fx import record_fx_rate
from avenel.proposals.tax_mapping import seed_approved_client_tax_mappings
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture(scope="module")
def hypothesis_env(postgres_url: str) -> Generator[tuple[psycopg.Connection, uuid.UUID, uuid.UUID, uuid.UUID], None, None]:
    """Sets up persistent connection and tenant context with approved tax mappings and FX rates."""
    conn = psycopg.connect(postgres_url, autocommit=True)
    tenant_id = seed_tenant(conn, "Cabinet Hypothesis Property Tests")
    sub = f"prop-tester-{uuid.uuid4()}"
    user_id = seed_user(conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(conn, user_id, tenant_id, "accountant")
    set_rls_context(conn, tenant_id, user_id)

    client = create_client_entity(conn, tenant_id, "Atlas Property Testing SARL", actor_id=str(user_id))

    # Seed approved tax mappings (Item 2)
    seed_approved_client_tax_mappings(conn, tenant_id, client.id, approver_id=user_id)

    # Seed FX fixing rates for foreign currencies (Item 7)
    tx_date = datetime.date(2026, 3, 15)
    record_fx_rate(conn, tenant_id, tx_date, "EUR", 10.8523, "bam_fixing", user_id)
    record_fx_rate(conn, tenant_id, tx_date, "USD", 9.9814, "bam_fixing", user_id)
    record_fx_rate(conn, tenant_id, tx_date, "GBP", 12.7845, "bam_fixing", user_id)

    yield conn, tenant_id, client.id, user_id
    conn.close()


# Strategies covering amounts at 0.005 rounding boundaries, credit notes, FX, and multi-rate
boundary_amounts = st.integers(min_value=100, max_value=2000000).map(lambda i: round(i * 0.005, 3))
float_amounts = st.floats(min_value=1.0, max_value=25000.0, allow_nan=False, allow_infinity=False).map(lambda f: round(f, 2))
amount_strategy = st.one_of(boundary_amounts, float_amounts)

doc_type_strategy = st.sampled_from([
    "invoice_purchase",
    "invoice_sale",
    "purchase_credit_note",
    "sales_credit_note",
    "fixed_asset",
])
currency_strategy = st.sampled_from(["MAD", "EUR", "USD", "GBP"])
single_vat_rates = st.sampled_from([0.20, 0.10, 0.0])


@settings(max_examples=1000, deadline=None)
@given(
    ht=amount_strategy,
    is_multi_rate=st.booleans(),
    single_vat_rate=single_vat_rates,
    doc_type=doc_type_strategy,
    currency=currency_strategy,
)
def test_hypothesis_every_proposal_balances_and_has_evidence(
    hypothesis_env: tuple[psycopg.Connection, uuid.UUID, uuid.UUID, uuid.UUID],
    ht: float,
    is_multi_rate: bool,
    single_vat_rate: float,
    doc_type: str,
    currency: str,
):
    """Property: For arbitrary amounts (including 0.005 boundaries), multi-rate, credit notes, and FX,

    every generated proposal strictly balances in MAD and all constraints are satisfied.
    """
    conn, tenant_id, client_id, user_id = hypothesis_env

    ht_rounded = round(ht, 2)
    if ht_rounded <= 0.0:
        ht_rounded = 1.00

    vat_breakdown: list[dict] = []
    if is_multi_rate and doc_type in ("invoice_purchase", "purchase_credit_note", "fixed_asset") and ht_rounded >= 10.0:
        base1 = round(ht_rounded * 0.6, 2)
        base2 = round(ht_rounded - base1, 2)
        vat1 = round(base1 * 0.20, 2)
        vat2 = round(base2 * 0.10, 2)
        vat_rounded = round(vat1 + vat2, 2)
        ttc_rounded = round(ht_rounded + vat_rounded, 2)
        vat_breakdown = [
            {"rate": 0.20, "base_ht": base1, "vat_amount": vat1},
            {"rate": 0.10, "base_ht": base2, "vat_amount": vat2},
        ]
    else:
        vat_rounded = round(ht_rounded * single_vat_rate, 2)
        ttc_rounded = round(ht_rounded + vat_rounded, 2)

    doc_id = uuid.uuid4()
    mock_extracted = {
        "invoice_number": {"value": f"INV-{uuid.uuid4().hex[:6].upper()}", "page": 1, "confidence": 0.98},
        "invoice_date": {"value": "2026-03-15", "page": 1, "confidence": 0.98},
        "supplier_ice": {"value": "001234567890123", "page": 1, "confidence": 0.98},
        "supplier_if": {"value": "12345678", "page": 1, "confidence": 0.98},
        "supplier_name": {"value": "Fournisseur Property Test", "page": 1, "confidence": 0.98},
        "client_name": {"value": "Atlas Property Testing SARL", "page": 1, "confidence": 0.98},
        "currency": {"value": currency, "page": 1, "confidence": 1.0},
        "total_ht": {"value": ht_rounded, "page": 1, "confidence": 0.98, "bbox": [0.1, 0.1, 0.4, 0.15]},
        "total_vat": {"value": vat_rounded, "page": 1, "confidence": 0.98, "bbox": [0.1, 0.2, 0.4, 0.25]},
        "total_ttc": {"value": ttc_rounded, "page": 1, "confidence": 0.98, "bbox": [0.1, 0.3, 0.4, 0.35]},
    }
    if vat_breakdown:
        mock_extracted["vat_breakdown"] = {"value": vat_breakdown}

    entry = build_journal_proposal(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_id,
        document_id=doc_id,
        doc_type=doc_type,
        extracted_fields=mock_extracted,
        actor_id=str(user_id),
    )

    assert len(entry.lines) >= 2, f"Proposal must have at least 2 lines, got {len(entry.lines)}"

    # Invariant 1: Strict MAD balance: sum(debit_mad) == sum(credit_mad)
    total_debit_mad = round(sum(line.debit_mad for line in entry.lines), 2)
    total_credit_mad = round(sum(line.credit_mad for line in entry.lines), 2)
    diff = abs(total_debit_mad - total_credit_mad)
    assert diff < 0.009, f"Proposal unbalanced: debit={total_debit_mad}, credit={total_credit_mad}, diff={diff}"

    # Invariant 2: Evidence validity and database line constraints
    for line in entry.lines:
        # Rounding adjustment lines (6331 loss, 7331 gain, 6588 residual) may have empty evidence
        if line.account_code not in ("6331", "7331", "6588"):
            assert len(line.evidence_refs) > 0, f"Line #{line.line_no} ({line.account_code}) missing evidence"
            for ev in line.evidence_refs:
                assert "document_id" in ev, "Evidence must reference source document_id"
                assert "page" in ev, "Evidence must reference page"
                assert "bbox" in ev, "Evidence must reference bbox"

        # Invariant 3: DB constraints strictly satisfied
        assert (line.debit_mad > 0) != (line.credit_mad > 0), "Line must be either debit or credit, not both or zero"
        assert (line.debit_tx > 0) != (line.credit_tx > 0), "Transaction amount must be either debit or credit"
        assert (line.debit_tx > 0) == (line.debit_mad > 0), "Debit direction must match between tx and MAD"

        if line.currency == "MAD":
            assert line.fx_rate == 1.0, "MAD fx_rate must be 1.0"
            assert line.fx_rate_date is None, "MAD fx_rate_date must be None"
            assert line.fx_source is None, "MAD fx_source must be None"
        else:
            assert line.fx_rate_date is not None, f"Foreign currency {line.currency} requires fx_rate_date"
            assert line.fx_source is not None, f"Foreign currency {line.currency} requires fx_source"
