"""Security verification test: Keycloak production realm export contains zero static secrets or test credentials.

Enforces Phase 5b review requirement:
- Test TOTP secrets (e.g. JBSWY3DPEHPK3PXP) exist only in CI/test realm config.
- Production realm export contains NO static TOTP secret, credentials, or development passwords.
"""

from __future__ import annotations

import json
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROD_REALM_PATH = os.path.join(REPO_ROOT, "docker", "keycloak", "realm-export-prod.json")
TEST_REALM_PATH = os.path.join(REPO_ROOT, "docker", "keycloak", "realm-export-test.json")
KNOWN_CI_TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def test_production_realm_export_exists():
    """Production realm export must exist in docker/keycloak."""
    assert os.path.isfile(PROD_REALM_PATH), f"Missing production realm export at {PROD_REALM_PATH}"


def test_production_realm_contains_no_static_totp_secret_or_credentials():
    """Production Keycloak export must contain zero pre-configured users or static credentials."""
    with open(PROD_REALM_PATH, "r", encoding="utf-8") as f:
        prod_data = json.load(f)

    # 1. Users list must be empty in production realm export (users register via OIDC or admin console)
    users = prod_data.get("users", [])
    assert users == [], f"Production realm export must have empty users list, found {len(users)} users"

    # 2. Raw content search: ensure no secretData, totpSecret, or static credential fields appear
    with open(PROD_REALM_PATH, "r", encoding="utf-8") as f:
        raw_content = f.read()

    assert "secretData" not in raw_content
    assert "credentialData" not in raw_content
    assert "totpSecret" not in raw_content
    assert not re.search(r'"password"\s*:\s*"[^"]+"', raw_content, re.IGNORECASE)

    # 3. Specifically verify KNOWN_CI_TOTP_SECRET is absent from production configuration
    assert KNOWN_CI_TOTP_SECRET not in raw_content


def test_production_realm_enforces_secure_otp_policy():
    """Production OTP policy must mandate 6 digits, 30s period, and HmacSHA256 algorithm."""
    with open(PROD_REALM_PATH, "r", encoding="utf-8") as f:
        prod_data = json.load(f)

    assert prod_data.get("otpPolicyType") == "totp"
    assert prod_data.get("otpPolicyDigits") == 6
    assert prod_data.get("otpPolicyPeriod") == 30
    assert prod_data.get("otpPolicyAlgorithm") == "HmacSHA256"
    assert prod_data.get("registrationAllowed") is False
    assert prod_data.get("bruteForceProtected") is True


def test_test_totp_secret_confined_to_ci_test_realm_and_fixtures():
    """Confirms that KNOWN_CI_TOTP_SECRET exists only in test configurations and never in production files."""
    assert os.path.isfile(TEST_REALM_PATH)
    with open(TEST_REALM_PATH, "r", encoding="utf-8") as f:
        test_content = f.read()

    # The test realm explicitly contains the test fixture secret
    assert KNOWN_CI_TOTP_SECRET in test_content
