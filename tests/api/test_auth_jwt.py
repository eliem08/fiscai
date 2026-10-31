"""Tests for real JWT validation against Keycloak JWKS, MFA enforcement, and Operator access.

Enforces:
- Cryptographic signature check against JWKS
- Claims: iss, aud, exp, nbf (expired/forged/wrong-aud gets 401)
- MFA claim enforcement (acr/amr) for members with professional registration numbers
- Operator temporary access (expiry <= 72h) granted by owner; expired access gets 404
"""

from __future__ import annotations

import datetime
import time
import uuid

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import psycopg
import pytest

from apps.api.main import app
from avenel.tenancy.auth import grant_operator_access
from avenel.tenancy.jwt import get_jwt_verifier
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generates an RSA key pair and matching JWKS for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = "avenel-test-key-1"
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"

    jwks = {"keys": [jwk]}
    get_jwt_verifier().set_jwks(jwks)

    rogue_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    return {
        "private_key": private_key,
        "public_key": public_key,
        "jwks": jwks,
        "kid": "avenel-test-key-1",
        "rogue_private_key": rogue_private_key,
    }


def _make_jwt(
    keypair: dict,
    sub: str,
    iss: str = "http://localhost:8080/realms/avenel",
    aud: str = "avenel-api",
    exp_offset: int = 3600,
    nbf_offset: int = 0,
    acr: str | None = None,
    amr: list[str] | None = None,
    use_rogue_key: bool = False,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": iss,
        "aud": aud,
        "iat": now,
        "exp": now + exp_offset,
        "nbf": now + nbf_offset,
    }
    if acr:
        payload["acr"] = acr
    if amr:
        payload["amr"] = amr

    pk = keypair["rogue_private_key"] if use_rogue_key else keypair["private_key"]
    headers = {"kid": keypair["kid"]}
    return jwt.encode(payload, pk, algorithm="RS256", headers=headers)


def test_jwt_valid_signature_authenticates(db_conn: psycopg.Connection, rsa_keypair: dict):
    """Valid JWT signed with matching JWKS key authenticates successfully."""
    t_id = seed_tenant(db_conn, "Cabinet Test JWT")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="accountant")

    token = _make_jwt(rsa_keypair, sub=sub)
    client = TestClient(app)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == str(u_id)
    assert body["role"] == "accountant"


def test_jwt_expired_token_gets_401(db_conn: psycopg.Connection, rsa_keypair: dict):
    """Expired JWT token returns 401."""
    t_id = seed_tenant(db_conn, "Cabinet Expired")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id)

    # Expired 1 hour ago
    token = _make_jwt(rsa_keypair, sub=sub, exp_offset=-3600)
    client = TestClient(app)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expiré" in response.json()["detail"].lower()


def test_jwt_wrong_audience_gets_401(db_conn: psycopg.Connection, rsa_keypair: dict):
    """JWT with invalid audience returns 401."""
    t_id = seed_tenant(db_conn, "Cabinet Wrong Aud")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id)

    token = _make_jwt(rsa_keypair, sub=sub, aud="different-app")
    client = TestClient(app)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "audience" in response.json()["detail"].lower()


def test_jwt_wrong_issuer_gets_401(db_conn: psycopg.Connection, rsa_keypair: dict):
    """JWT with invalid issuer returns 401."""
    t_id = seed_tenant(db_conn, "Cabinet Wrong Iss")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id)

    token = _make_jwt(rsa_keypair, sub=sub, iss="https://rogue-idp.org/realm")
    client = TestClient(app)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "émetteur" in response.json()["detail"].lower() or "iss" in response.json()["detail"].lower()


def test_jwt_forged_signature_gets_401(db_conn: psycopg.Connection, rsa_keypair: dict):
    """JWT signed by an untrusted rogue key returns 401."""
    t_id = seed_tenant(db_conn, "Cabinet Forged")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id)

    token = _make_jwt(rsa_keypair, sub=sub, use_rogue_key=True)
    client = TestClient(app)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "signature" in response.json()["detail"].lower()


def test_jwt_immature_nbf_gets_401(db_conn: psycopg.Connection, rsa_keypair: dict):
    """JWT with nbf in the future returns 401."""
    t_id = seed_tenant(db_conn, "Cabinet Future NBF")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id)

    # Valid only in 1 hour
    token = _make_jwt(rsa_keypair, sub=sub, nbf_offset=3600)
    client = TestClient(app)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "nbf" in response.json()["detail"].lower() or "pas encore valide" in response.json()["detail"].lower()


def test_mfa_enforced_for_professional_registration(db_conn: psycopg.Connection, rsa_keypair: dict):
    """Members with professional registration numbers must have MFA (acr/amr) in token."""
    t_id = seed_tenant(db_conn, "Cabinet OEC MFA")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    # Set professional registration on membership
    with db_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE memberships
            SET professional_title = 'expert_comptable', professional_registration_no = 'OEC-MA-2026-999'
            WHERE tenant_id = %s AND user_id = %s;
            """,
            (t_id, u_id),
        )
    db_conn.commit()

    client = TestClient(app)

    # 1. Token without MFA claim fails with 401, RFC 9470 WWW-Authenticate and avenel/mfa-required problem type
    no_mfa_token = _make_jwt(rsa_keypair, sub=sub)
    res1 = client.get("/v1/me", headers={"Authorization": f"Bearer {no_mfa_token}"})
    assert res1.status_code == 401
    assert res1.headers.get("www-authenticate") == 'Bearer error="insufficient_user_authentication"'
    res_json = res1.json()
    assert res_json.get("type") == "avenel/mfa-required"
    assert "mfa" in res_json["detail"].lower()

    # 2. Token with acr: 'mfa' succeeds
    mfa_acr_token = _make_jwt(rsa_keypair, sub=sub, acr="mfa")
    res2 = client.get("/v1/me", headers={"Authorization": f"Bearer {mfa_acr_token}"})
    assert res2.status_code == 200

    # 3. Token with amr: ['otp'] succeeds
    mfa_amr_token = _make_jwt(rsa_keypair, sub=sub, amr=["pwd", "otp"])
    res3 = client.get("/v1/me", headers={"Authorization": f"Bearer {mfa_amr_token}"})
    assert res3.status_code == 200


def test_operator_access_lifecycle_and_expiry(db_conn: psycopg.Connection, rsa_keypair: dict):
    """Owner can grant operator access <= 72h; expired access gets 404."""
    t_id = seed_tenant(db_conn, "Cabinet Operator Test")
    owner_sub = f"owner-{uuid.uuid4()}"
    owner_id = seed_user(db_conn, identity_subject=owner_sub, email=f"{owner_sub}@example.com")
    seed_membership(db_conn, owner_id, t_id, role="owner")

    operator_sub = f"op-{uuid.uuid4()}"
    operator_id = seed_user(db_conn, identity_subject=operator_sub, email=f"{operator_sub}@example.com")
    seed_membership(db_conn, operator_id, t_id, role="staff")

    # 1. Owner grants 48 hours of operator access
    expires_at = grant_operator_access(
        conn=db_conn,
        tenant_id=t_id,
        granter_user_id=owner_id,
        operator_user_id=operator_id,
        duration_hours=48.0,
    )
    db_conn.commit()
    assert expires_at > datetime.datetime.now(datetime.timezone.utc)

    # Operator accesses tenant while grant is active -> 200
    token = _make_jwt(rsa_keypair, sub=operator_sub)
    client = TestClient(app)
    res_active = client.get(
        "/v1/client-entities",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(t_id)},
    )
    assert res_active.status_code == 200

    # 2. Expire operator access manually in DB
    with db_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE memberships
            SET operator_access_expires_at = now() - interval '1 hour'
            WHERE tenant_id = %s AND user_id = %s;
            """,
            (t_id, operator_id),
        )
    db_conn.commit()

    # Expired operator access returns 404 for tenant isolation
    res_expired = client.get(
        "/v1/client-entities",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(t_id)},
    )
    assert res_expired.status_code == 404

    # 3. Grant exceeding 72h is refused with ValueError
    with pytest.raises(ValueError, match="0 et 72 heures"):
        grant_operator_access(
            conn=db_conn,
            tenant_id=t_id,
            granter_user_id=owner_id,
            operator_user_id=operator_id,
            duration_hours=75.0,
        )

    # 4. Non-owner cannot grant operator access
    staff_sub = f"staff-{uuid.uuid4()}"
    staff_id = seed_user(db_conn, identity_subject=staff_sub, email=f"{staff_sub}@example.com")
    seed_membership(db_conn, staff_id, t_id, role="staff")
    db_conn.commit()
    with pytest.raises(PermissionError, match="propriétaire"):
        grant_operator_access(
            conn=db_conn,
            tenant_id=t_id,
            granter_user_id=staff_id,
            operator_user_id=operator_id,
            duration_hours=24.0,
        )
