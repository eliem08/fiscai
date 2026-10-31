"""Negative tests proving each quality guard fails on a planted violation.

Per Checklist Item 3:
1. Tax-literal linter: fails when 0.20 is planted in application code.
2. Spectral OpenAPI linter: fails when `nullable: true` is planted in a schema.
3. rls_check: fails when a table has tenant_id and no RLS policy.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import psycopg

from scripts.check_no_tax_literals import scan_file
from scripts.rls_check import _run_query_on_url


def test_tax_literal_linter_fails_on_planted_rate():
    """Prove check_no_tax_literals flags numeric tax literals (0.20) in code."""
    planted_code = "vat_rate = 0.20\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(planted_code)
        temp_path = Path(f.name)

    try:
        violations = scan_file(temp_path)
        assert len(violations) > 0, "Linter must report a violation for hardcoded 0.20 in tax context"
        reasons_flagged = [v[1] for v in violations]
        assert any("0.20" in r for r in reasons_flagged), f"Expected '0.20' in violations, got {reasons_flagged}"
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_linter_fails_on_planted_identifier_regex():
    """Prove check_no_tax_literals flags hardcoded identifier regexes outside /jurisdiction/."""
    planted_code = 'ICE_REGEX = "^[0-9]{15}$"\n'
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(planted_code)
        temp_path = Path(f.name)

    try:
        violations = scan_file(temp_path)
        assert len(violations) > 0, "Linter must report a violation for hardcoded ICE regex"
        assert any("ICE 15-digit regex" in v[1] for v in violations)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_linter_fails_on_planted_account_seed():
    """Prove check_no_tax_literals flags hardcoded accounting account seeds outside /jurisdiction/."""
    planted_code = 'MY_ACCOUNTS = [{"code": "3421", "label": "Clients"}]\n'
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(planted_code)
        temp_path = Path(f.name)

    try:
        violations = scan_file(temp_path)
        assert len(violations) > 0, "Linter must report a violation for hardcoded account seed"
        assert any("account seed" in v[1] for v in violations)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_spectral_fails_on_planted_nullable_true():
    """Prove Spectral fails when nullable: true is planted in an OpenAPI 3.1 contract."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    ruleset_path = repo_root / ".spectral.yaml"

    planted_openapi = """
openapi: 3.1.0
info:
  title: Planted Test API
  version: 1.0.0
paths:
  /planted:
    get:
      operationId: getPlanted
      tags:
        - test
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema:
                type: string
                nullable: true
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(planted_openapi)
        temp_path = Path(f.name)

    try:
        cmd = [
            "npx.cmd" if os.name == "nt" else "npx",
            "@stoplight/spectral-cli",
            "lint",
            str(temp_path),
            "--ruleset",
            str(ruleset_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        # Spectral must fail with exit code != 0
        assert result.returncode != 0, f"Spectral should have failed on nullable: true, but passed: {result.stdout}"
        combined_output = (result.stdout + result.stderr).lower()
        assert "no-nullable" in combined_output or "nullable" in combined_output, (
            f"Expected no-nullable rule failure in spectral output: {result.stdout}"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_rls_check_fails_on_planted_unprotected_table(postgres_url: str, db_conn: psycopg.Connection):
    """Prove rls_check fails when a table has tenant_id but lacks forced RLS or a policy."""
    with db_conn.cursor() as cur:
        # Create an unprotected table with tenant_id
        cur.execute("CREATE TABLE planted_unprotected_table (id uuid PRIMARY KEY, tenant_id uuid NOT NULL);")
    db_conn.commit()

    try:
        # rls_check must return False because planted_unprotected_table has no RLS policy
        passed = _run_query_on_url(postgres_url)
        assert passed is False, "rls_check MUST fail when a table with tenant_id has no policy"
    finally:
        # Clean up planted table
        with db_conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS planted_unprotected_table;")
        db_conn.commit()

    # Verify rls_check passes cleanly after table is removed
    assert _run_query_on_url(postgres_url) is True
