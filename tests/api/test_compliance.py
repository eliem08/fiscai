"""Tests for compliance document generators (DPA and CNDP).

Enforces:
- Title is strictly 'Projet — à valider par un juriste'
- Includes needs_expert keys they depend on
- Word 'conforme' is NEVER used
"""

from __future__ import annotations

import json
import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_compliance_dpa_and_cndp_generation(
    postgres_url: str,
    db_conn: psycopg.Connection,
):
    """Verifies DPA and CNDP dossier generation for an authenticated firm."""
    client = TestClient(app)

    tenant_id = seed_tenant(db_conn, "Cabinet Fiduciaire Casablanca")
    user_id = seed_user(db_conn, "sub-compliance-user", "compliance@fiduciaire.ma", "Meftah Mohamed")
    seed_membership(db_conn, user_id, tenant_id, role="owner")

    headers = {"X-Identity-Subject": "sub-compliance-user"}

    # 1. DPA Generation
    res_dpa = client.get("/v1/compliance/dpa", headers=headers)
    assert res_dpa.status_code == 200
    dpa = res_dpa.json()
    assert dpa["title"] == "Projet — à valider par un juriste"
    assert "needs_expert_dependencies" in dpa
    assert "compliance.cndp.dpa_wording" in dpa["needs_expert_dependencies"]
    assert "compliance.cybersecurity.loi_05_20" in dpa["needs_expert_dependencies"]
    assert "compliance.oec.professional_secrecy" in dpa["needs_expert_dependencies"]
    assert dpa["governing_law"] == "Loi n° 09-08"
    assert dpa["controller"]["legal_name"] == "Cabinet Fiduciaire Casablanca"
    assert len(dpa["clauses"]) >= 5

    # Check that 'conforme' is never used anywhere in DPA
    dpa_str = json.dumps(dpa, ensure_ascii=False).lower()
    assert "conforme" not in dpa_str, f"Found forbidden word 'conforme' in DPA output: {dpa_str}"

    # 2. CNDP Dossier Generation
    res_cndp = client.get("/v1/compliance/cndp-dossier", headers=headers)
    assert res_cndp.status_code == 200
    cndp = res_cndp.json()
    assert cndp["title"] == "Projet — à valider par un juriste"
    assert "needs_expert_dependencies" in cndp
    assert "compliance.cndp.provider_routes" in cndp["needs_expert_dependencies"]
    assert "compliance.cndp.dpa_wording" in cndp["needs_expert_dependencies"]
    assert "compliance.cybersecurity.loi_05_20" in cndp["needs_expert_dependencies"]
    assert "compliance.oec.ai_assisted_preparation" in cndp["needs_expert_dependencies"]
    assert "compliance.oec.professional_secrecy" in cndp["needs_expert_dependencies"]
    assert cndp["responsible_entity"]["legal_name"] == "Cabinet Fiduciaire Casablanca"
    assert cndp["purpose_of_processing"]["exempt_from_transfer_abroad"] is True
    assert "Loi marocaine n° 09-08" in cndp["governing_statute"]

    # Check that 'conforme' is never used anywhere in CNDP dossier
    cndp_str = json.dumps(cndp, ensure_ascii=False).lower()
    assert "conforme" not in cndp_str, f"Found forbidden word 'conforme' in CNDP output: {cndp_str}"
