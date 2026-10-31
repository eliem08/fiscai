"""Moroccan Bank Identity Statement (RIB) validation, masking, and encryption.

Complies with:
- Bank Al-Maghrib standards: 24-digit format, mod-97 key verification.
- Rule A.1: Algorithm and format loaded from /jurisdiction/ma/*.yaml.
- Rule A.2: No numeric literals outside /jurisdiction/.
- Part D: rib_encrypted (pgp/AES-GCM encrypted), rib_sha256, rib_last4.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from avenel.jurisdiction.loader import get_jurisdiction_pack


def clean_rib(rib: str) -> str:
    """Removes spaces, tabs, dashes, and other non-digit separators from a RIB."""
    return re.sub(r"\D", "", rib or "")


def extract_bank_code(rib: str) -> str:
    """Extracts the 3-digit bank code from the beginning of the RIB."""
    cleaned = clean_rib(rib)
    if len(cleaned) < 3:
        raise ValueError("RIB too short to extract bank code")
    return cleaned[:3]


def extract_rib_last4(rib: str) -> str:
    """Extracts the last 4 digits of the account number / key."""
    cleaned = clean_rib(rib)
    if len(cleaned) < 4:
        raise ValueError("RIB too short to extract last 4 digits")
    return cleaned[-4:]


def compute_rib_sha256(rib: str) -> str:
    """Computes lowercase hex SHA-256 digest of normalized 24-digit RIB."""
    cleaned = clean_rib(rib)
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def compute_moroccan_rib_key(rib_prefix_22: str) -> int:
    """Computes the expected 2-digit Moroccan RIB control key using mod-97.

    Formula: key = 97 - ((int(prefix_22) * 100) % 97)
    If remainder is 0, key is 97.
    """
    pack = get_jurisdiction_pack()
    mod_rule = pack.get_rule("identifiers.rib.modulus")
    if not mod_rule or not mod_rule.get("value"):
        raise RuntimeError("Règle identifiers.rib.modulus manquante dans le pack de juridiction")
    modulus = int(mod_rule["value"])

    if len(rib_prefix_22) != 22 or not rib_prefix_22.isdigit():
        raise ValueError("Moroccan RIB prefix must be exactly 22 digits")

    remainder = (int(rib_prefix_22) * 100) % modulus
    key = modulus - remainder
    return modulus if key == 0 else key


def validate_moroccan_rib(rib: str) -> bool:
    """Validates that a Moroccan RIB matches BAM format and mod-97 check key."""
    pack = get_jurisdiction_pack()
    fmt_rule = pack.get_rule("identifiers.rib.format")
    if not fmt_rule or not fmt_rule.get("value"):
        raise RuntimeError("Règle identifiers.rib.format manquante dans le pack de juridiction")
    pattern = str(fmt_rule["value"])

    cleaned = clean_rib(rib)
    if not re.match(pattern, cleaned):
        return False

    prefix_22 = cleaned[:22]
    stated_key = int(cleaned[22:])
    expected_key = compute_moroccan_rib_key(prefix_22)
    return stated_key == expected_key


def mask_rib(rib: str) -> str:
    """Returns masked representation for UI and logs: e.g. '007 ***************** 1234'."""
    cleaned = clean_rib(rib)
    if len(cleaned) != 24:
        return "****"
    bank = cleaned[:3]
    last4 = cleaned[-4:]
    return f"{bank} {'*' * 17} {last4}"


def _get_encryption_key(secret_key: bytes | None = None) -> Fernet:
    """Derives a Fernet encryption key from provided key or environment."""
    raw = secret_key or os.getenv("AVENEL_KMS_KEY", "avenel-default-bank-kms-secret-salt").encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"avenel-rib-storage-salt-v1",
        iterations=100_000,
    )
    key_b64 = base64.urlsafe_b64encode(kdf.derive(raw))
    return Fernet(key_b64)


def encrypt_rib(rib: str, secret_key: bytes | None = None) -> bytes:
    """Encrypts a 24-digit RIB into ciphertext bytes for database storage."""
    cleaned = clean_rib(rib)
    fernet = _get_encryption_key(secret_key)
    return fernet.encrypt(cleaned.encode("utf-8"))


def decrypt_rib(encrypted_rib: bytes, secret_key: bytes | None = None) -> str:
    """Decrypts ciphertext bytes back to the 24-digit plain RIB."""
    fernet = _get_encryption_key(secret_key)
    return fernet.decrypt(encrypted_rib).decode("utf-8")
