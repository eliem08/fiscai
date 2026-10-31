"""Property-based tests for proposal balancing and evidence invariants (Hypothesis).

Enforces ARCHITECTURE.md Part G Phase 3 Exit Criteria:
- "property tests (Hypothesis) show every generated proposal balances;"
- "every line has evidence."
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
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture(scope="module")
def hypothesis_env(postgres_url: str) -> Generator[tuple[psycopg.Connection, uuid.UUID, uuid.UUID, uuid.UUID], None, None]:
    """Sets up persistent connection and tenant context for Hypothesis runs."""
    conn = psycopg.connect(postgres_url, autocommit=True)
    tenant_id = seed_tenant(conn, "Cabinet Hypothesis Property Tests")
    sub = f"prop-tester-{uuid.uuid4()}"
    user_id = seed_user(conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(conn, user_id, tenant_id, "accountant")
    set_rls_context(conn, tenant_id, user_id)

    client = create_client_entity(conn, tenant_id, "Atlas Property Testing SARL", actor_id=str(user_id))
    yield conn, tenant_id, client.id, user_id
    conn.close()


# Strategies for arbitrary invoice extraction inputs
amount_strategy = st.floats(min_value=0.50, max_value=500000.0, allow_nan=False, allow_infinity=False)
doc_type_strategy = st.sampled_from(["invoice_purchase", "invoice_sale", "purchase_credit_note", "sales_credit_note", "fixed_asset"])
currency_strategy = st.sampled_from(["MAD", "EUR", "USD"])


@settings(max_examples=50, deadline=None)
@given(
    ht=amount_strategy,
    vat_rate=st.sampled_from([0.20, 0.10, 0.0]),
    doc_type=doc_type_strategy,
    currency=currency_strategy,
)
def test_hypothesis_every_proposal_balances_and_has_evidence(
    hypothesis_env: tuple[psycopg.Connection, uuid.UUID, uuid.UUID, uuid.UUID],
    ht: float,
    vat_rate: float,
    doc_type: str,
    currency: str,
):
    """Property: For arbitrary amounts, VAT rates, document types, and currencies,

    every generated proposal balances (sum(debit_mad) == sum(credit_mad)) and every line has evidence.
    """
    conn, tenant_id, client_id, user_id = hypothesis_env

    ht_rounded = round(ht, 2)
    vat_rounded = round(ht_rounded * vat_rate, 2)
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

    # Invariant 1: Proposal strictly balances in MAD
    total_debit_mad = round(sum(line.debit_mad for line in entry.lines), 2)
    total_credit_mad = round(sum(line.credit_mad for line in entry.lines), 2)
    diff = abs(total_debit_mad - total_credit_mad)
    assert diff < 0.009, f"Proposal unbalanced: debit={total_debit_mad}, credit={total_credit_mad}, diff={diff}"

    # Invariant 2: Every line has evidence
    for line in entry.lines:
        assert len(line.evidence_refs) > 0, f"Line #{line.line_no} ({line.account_code}) has no evidence refs"
        for ev in line.evidence_refs:
            assert "field" in ev or "rule_ref" in ev, "Evidence must link to field or rule_ref"
            assert "document_id" in ev, "Evidence must reference source document_id"

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
