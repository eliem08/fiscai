"""OIDC / Keycloak JWT Verification with JWKS, signature, audience, and MFA claim validation.

Enforces:
- Cryptographic signature check against Keycloak JWKS (RS256)
- Claims: iss, aud, exp, nbf
- MFA enforcement (acr/amr) for members with professional registration numbers (e.g. OEC / chartered accountants)
"""

from __future__ import annotations

import os
import time
from typing import Any

import jwt
from jwt.algorithms import RSAAlgorithm


class AuthenticationError(Exception):
    """Raised when JWT verification fails."""


class MfaRequiredError(AuthenticationError):
    """Raised when MFA claim is missing (RFC 9470 insufficient_user_authentication)."""

    def __init__(
        self,
        detail: str = "MFA (authentification multi-facteurs) obligatoire pour tout membre disposant d'une inscription professionnelle.",
    ) -> None:
        super().__init__(detail)
        self.detail = detail


class JwtVerifier:
    def __init__(
        self,
        expected_issuer: str | None = None,
        expected_audience: str | None = None,
        jwks: dict[str, Any] | None = None,
        jwks_uri: str | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self.expected_issuer = expected_issuer or os.environ.get(
            "KEYCLOAK_ISSUER", "http://localhost:8080/realms/avenel"
        )
        self.expected_audience = expected_audience or os.environ.get(
            "KEYCLOAK_AUDIENCE", "avenel-api"
        )
        self.jwks_uri = jwks_uri or os.environ.get(
            "KEYCLOAK_JWKS_URI", f"{self.expected_issuer}/protocol/openid-connect/certs"
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self.jwks = jwks or {}
        self._cached_jwks: dict[str, Any] | None = None
        self._cache_timestamp: float = 0.0
        self.fetch_count: int = 0

    def set_jwks(self, jwks: dict[str, Any]) -> None:
        """Sets or refreshes the static JWKS dictionary."""
        self.jwks = jwks
        self._cached_jwks = jwks
        self._cache_timestamp = time.time()

    def clear_cache(self) -> None:
        """Invalidates in-memory JWKS cache."""
        self._cached_jwks = None
        self._cache_timestamp = 0.0
        self.jwks = {}

    def fetch_jwks(self, force: bool = False) -> dict[str, Any]:
        """Fetches JWKS from jwks_uri with in-memory caching and TTL."""
        now = time.time()
        if not force and self._cached_jwks is not None and (now - self._cache_timestamp) < self.cache_ttl_seconds:
            return self._cached_jwks

        if not self.jwks_uri:
            return self.jwks

        try:
            import httpx
            resp = httpx.get(self.jwks_uri, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                self._cached_jwks = data
                self.jwks = data
                self._cache_timestamp = now
                self.fetch_count += 1
                return data
            raise AuthenticationError(f"JWKS fetch returned status {resp.status_code}")
        except Exception as e:
            if self._cached_jwks and not force:
                return self._cached_jwks
            raise AuthenticationError(f"Impossible de récupérer les clés publiques JWKS: {e}") from e

    def get_public_key_for_kid(self, kid: str) -> Any:
        """Looks up the public key for a given kid, fetching or refreshing JWKS on key rotation."""
        # 1. Search current cached keys
        current_jwks = self.fetch_jwks()
        keys = current_jwks.get("keys", [])
        key_dict = next((k for k in keys if k.get("kid") == kid), None)

        # 2. If missing, attempt dynamic JWKS refresh (Key Rotation: new kid added)
        if not key_dict and self.jwks_uri:
            try:
                refreshed_jwks = self.fetch_jwks(force=True)
                keys = refreshed_jwks.get("keys", [])
                key_dict = next((k for k in keys if k.get("kid") == kid), None)
            except (AuthenticationError, KeyError):
                key_dict = None

        if not key_dict:
            raise AuthenticationError(f"No matching public key found for kid: {kid}")

        try:
            return RSAAlgorithm.from_jwk(key_dict)
        except Exception as e:
            raise AuthenticationError(f"Failed to parse public key from JWKS: {e}") from e

    def verify_token(self, token: str) -> dict[str, Any]:
        """Decodes and validates JWT token signature, iss, aud, exp, and nbf."""
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise AuthenticationError(f"Malformed token header: {e}") from e

        kid = unverified_header.get("kid")
        if not kid:
            raise AuthenticationError("Token missing 'kid' in header")

        public_key = self.get_public_key_for_kid(kid)

        try:
            payload = jwt.decode(
                token,
                public_key,  # type: ignore[arg-type]
                algorithms=["RS256"],
                audience=self.expected_audience,
                issuer=self.expected_issuer,
                options={
                    "require": ["exp", "iss", "aud", "sub"],
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationError("Le jeton d'authentification a expiré (exp).") from e
        except jwt.ImmatureSignatureError as e:
            raise AuthenticationError("Le jeton d'authentification n'est pas encore valide (nbf).") from e
        except jwt.InvalidAudienceError as e:
            raise AuthenticationError(f"Audience du jeton invalide (aud: attendu {self.expected_audience}).") from e
        except jwt.InvalidIssuerError as e:
            raise AuthenticationError(f"Émetteur du jeton invalide (iss: attendu {self.expected_issuer}).") from e
        except jwt.InvalidSignatureError as e:
            raise AuthenticationError("Signature cryptographique du jeton invalide.") from e
        except jwt.PyJWTError as e:
            raise AuthenticationError(f"Jeton JWT invalide: {e}") from e

        # Check explicit nbf if present
        nbf = payload.get("nbf")
        if nbf is not None and time.time() < nbf:
            raise AuthenticationError("Le jeton d'authentification n'est pas encore valide (nbf).")

        return payload


def verify_mfa_requirement(claims: dict[str, Any], professional_registration_no: str | None) -> None:
    """Enforces MFA claim (acr/amr) for any membership with a professional registration number."""
    if professional_registration_no is None:
        return

    # Check acr claim (e.g. 'gold', '2', 'mfa', 'urn:mfa')
    acr = str(claims.get("acr", "")).lower()
    mfa_acrs = {"gold", "2", "mfa", "urn:mfa", "urn:oasis:names:tc:saml:2.0:ac:classes:mobiletwofactorunregistered"}
    if acr in mfa_acrs:
        return

    # Check amr claim (Authentication Methods References list)
    amr = claims.get("amr", [])
    if isinstance(amr, list):
        amr_set = {str(a).lower() for a in amr}
        if amr_set.intersection({"mfa", "otp", "totp", "sms", "hwk"}):
            return

    raise MfaRequiredError(
        "MFA (authentification multi-facteurs) obligatoire pour tout membre disposant d'une inscription professionnelle."
    )


# Global verifier instance
_GLOBAL_JWT_VERIFIER = JwtVerifier()


def get_jwt_verifier() -> JwtVerifier:
    return _GLOBAL_JWT_VERIFIER
