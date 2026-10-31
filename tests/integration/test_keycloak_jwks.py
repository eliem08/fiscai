"""Integration test for Keycloak OIDC: real token issuance, JWKS fetch, key caching, and key rotation.

Tests:
1. Real token issuance (RS256 JWT with iss, aud, exp, kid, sub).
2. JWKS fetch from Keycloak / OIDC endpoint.
3. Key caching: repeated verifications hit the cache without re-fetching JWKS.
4. Key rotation:
   - New key (kid_2) introduced: automatically fetched on demand and accepted.
   - Removed key (kid_1) revoked from JWKS: subsequent tokens signed with removed kid are rejected.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from jwt.algorithms import RSAAlgorithm
import pytest

from avenel.tenancy.jwt import AuthenticationError, JwtVerifier


def _generate_rsa_key_pair(kid: str) -> dict[str, Any]:
    """Generates an RSA-2048 key pair and returns private PEM + public JWK dictionary."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    public_jwk["kid"] = kid
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"

    return {
        "kid": kid,
        "private_pem": private_pem,
        "public_jwk": public_jwk,
    }


class MockKeycloakServer:
    """Threaded HTTP server serving dynamic Keycloak JWKS and OIDC endpoints."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.active_keys: dict[str, dict[str, Any]] = {}
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.endswith("/protocol/openid-connect/certs"):
                    jwks = {"keys": [k["public_jwk"] for k in parent.active_keys.values()]}
                    body = json.dumps(jwks).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path.endswith("/health"):
                    self.send_response(200)
                    self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                # Silence standard HTTP logs
                pass

        self.server = HTTPServer((host, port), Handler)
        self.actual_port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @property
    def jwks_url(self) -> str:
        return f"http://127.0.0.1:{self.actual_port}/realms/avenel/protocol/openid-connect/certs"

    @property
    def issuer(self) -> str:
        return f"http://127.0.0.1:{self.actual_port}/realms/avenel"


@pytest.fixture(scope="module")
def keycloak_service():
    """Starts a dynamic Keycloak-compliant OIDC server for the test session."""
    server = MockKeycloakServer()
    server.start()
    yield server
    server.stop()


def test_keycloak_real_token_issuance_caching_and_rotation(keycloak_service: MockKeycloakServer):
    """End-to-end integration test: issuance, initial fetch, caching, new kid acceptance, removed kid rejection."""
    # 1. Generate Key 1 (kid_1) and publish to Keycloak JWKS
    key1 = _generate_rsa_key_pair("keycloak-kid-1")
    keycloak_service.active_keys[key1["kid"]] = key1

    verifier = JwtVerifier(
        expected_issuer=keycloak_service.issuer,
        expected_audience="avenel-api",
        jwks_uri=keycloak_service.jwks_url,
        cache_ttl_seconds=60,
    )

    # 2. Issue a real signed RS256 token with Key 1
    now = int(time.time())
    payload_1 = {
        "sub": f"user-{uuid.uuid4()}",
        "iss": keycloak_service.issuer,
        "aud": "avenel-api",
        "exp": now + 3600,
        "nbf": now - 10,
        "iat": now,
    }
    token_1 = jwt.encode(payload_1, key1["private_pem"], algorithm="RS256", headers={"kid": key1["kid"]})

    # Verify token 1 -> triggers first JWKS fetch
    verified_1 = verifier.verify_token(token_1)
    assert verified_1["sub"] == payload_1["sub"]
    assert verifier.fetch_count == 1

    # 3. Test JWKS Caching: verifying another token signed by kid_1 must NOT trigger a new fetch
    payload_1b = {
        "sub": f"user-{uuid.uuid4()}",
        "iss": keycloak_service.issuer,
        "aud": "avenel-api",
        "exp": now + 3600,
        "nbf": now - 10,
    }
    token_1b = jwt.encode(payload_1b, key1["private_pem"], algorithm="RS256", headers={"kid": key1["kid"]})
    verified_1b = verifier.verify_token(token_1b)
    assert verified_1b["sub"] == payload_1b["sub"]
    assert verifier.fetch_count == 1  # HIT CACHE! No new network request

    # 4. Key Rotation: Introduce Key 2 (kid_2) to Keycloak
    key2 = _generate_rsa_key_pair("keycloak-kid-2")
    keycloak_service.active_keys[key2["kid"]] = key2

    # Issue a real signed token with the new Key 2
    payload_2 = {
        "sub": f"user-new-key-{uuid.uuid4()}",
        "iss": keycloak_service.issuer,
        "aud": "avenel-api",
        "exp": now + 3600,
        "nbf": now - 10,
    }
    token_2 = jwt.encode(payload_2, key2["private_pem"], algorithm="RS256", headers={"kid": key2["kid"]})

    # Verifying token_2 must detect unknown kid in cache, dynamically refresh JWKS, and succeed!
    verified_2 = verifier.verify_token(token_2)
    assert verified_2["sub"] == payload_2["sub"]
    assert verifier.fetch_count == 2  # Refresh was triggered for new kid

    # 5. Key Revocation / Removal: Remove Key 1 from Keycloak
    del keycloak_service.active_keys[key1["kid"]]

    # Invalidate verifier cache to simulate TTL expiry
    verifier.clear_cache()

    # Token signed with kid_1 must now be REJECTED
    with pytest.raises(AuthenticationError) as exc_info:
        verifier.verify_token(token_1)
    assert "keycloak-kid-1" in str(exc_info.value)
    assert "No matching public key found" in str(exc_info.value)

    # But Token signed with kid_2 still succeeds
    verified_2_again = verifier.verify_token(token_2)
    assert verified_2_again["sub"] == payload_2["sub"]
