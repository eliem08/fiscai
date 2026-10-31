"""Tests for Data Residency Router (C.6).

Exit criteria:
- Residency router refuses disallowed calls.
- No provider call in tests (zero external network requests).
"""

from __future__ import annotations

import os
import uuid
import psycopg
import pytest

from avenel.extraction.router import (
    ProviderCallRequest,
    ProviderRouter,
    is_region_allowed,
    sanitize_pii_for_external_call,
)
from tests.helpers import seed_tenant


def test_residency_policy_region_allowlist():
    """MA_ONLY permits only local/Moroccan regions; EU_ALLOWED permits EU; GLOBAL_ALLOWED permits any."""
    assert is_region_allowed("MA_ONLY", "local") is True
    assert is_region_allowed("MA_ONLY", "ma") is True
    assert is_region_allowed("MA_ONLY", "eu-west-1") is False
    assert is_region_allowed("MA_ONLY", "us-east-1") is False

    assert is_region_allowed("EU_ALLOWED", "local") is True
    assert is_region_allowed("EU_ALLOWED", "eu-west-1") is True
    assert is_region_allowed("EU_ALLOWED", "us-east-1") is False

    assert is_region_allowed("GLOBAL_ALLOWED", "us-east-1") is True


def test_residency_router_refuses_disallowed_external_calls(db_conn: psycopg.Connection):
    """Under MA_ONLY, router refuses external provider calls and logs refused_by_policy."""
    tenant_id = seed_tenant(db_conn, "Cabinet Fiscalité Casa", residency_policy="MA_ONLY")

    router = ProviderRouter(db_conn=db_conn)

    req = ProviderCallRequest(
        provider="openai",
        region="us-east-1",
        model="gpt-4o",
        purpose="document_extraction",
        payload={"prompt": "Extract invoice data"},
    )

    resp = router.execute_call(tenant_id=tenant_id, policy="MA_ONLY", request=req)
    assert resp.status == "refused_by_policy"
    assert resp.result is None

    # Verify provider_calls record
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT provider, region, status, usage
            FROM provider_calls
            WHERE id = %s AND tenant_id = %s;
            """,
            (resp.provider_call_id, tenant_id),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "openai"
        assert row[1] == "us-east-1"
        assert row[2] == "refused_by_policy"


def test_zero_provider_calls_in_tests():
    """In test environment, external network provider calls are refused regardless of policy."""
    os.environ["AVENEL_TEST_MODE"] = "1"
    router = ProviderRouter()

    req = ProviderCallRequest(
        provider="anthropic",
        region="eu-west-1",
        model="claude-3-opus",
        purpose="test_call",
        payload={"data": "test"},
    )

    resp = router.execute_call(tenant_id=uuid.uuid4(), policy="GLOBAL_ALLOWED", request=req)
    assert resp.status == "refused_by_policy"
    assert "forbidden in tests" in str(resp.usage)


def test_pii_sanitization_for_external_calls():
    """Sanitizes ICE, RIB, and IF numbers before prompt dispatch."""
    raw_prompt = "Facture fournisseur avec ICE 001234567890123 et RIB 123456789012345678901234 et IF : 12345678."
    sanitized = sanitize_pii_for_external_call(raw_prompt)

    assert "001234567890123" not in sanitized
    assert "[MASQUÉ_ICE_15D]" in sanitized
    assert "123456789012345678901234" not in sanitized
    assert "[MASQUÉ_RIB_24D]" in sanitized
    assert "[MASQUÉ_IF]" in sanitized
