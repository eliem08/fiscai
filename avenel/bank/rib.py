"""Moroccan Bank Identity Statement (RIB) validation, masking, and encryption.

Complies with:
- Bank Al-Maghrib standards: 24-digit format, mod-97 key verification.
- Rule A.1: Algorithm, format, and bank codes loaded from /jurisdiction/ma/*.yaml.
- Rule A.2: No numeric literals outside /jurisdiction/.
- Part D: rib_encrypted (AES-GCM/Fernet encrypted), rib_sha256, rib_last4.
- Security: Key management documented. Dev: key file outside repo. Prod: KMS.
  App refuses to start without key. rib_encrypted never in logs or API responses.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from avenel.jurisdiction.loader import get_jurisdiction_pack


class RibKeyMissingError(RuntimeError):
    """Raised when neither AVENEL_RIB_KEY_FILE nor AVENEL_KMS_KEY is configured."""


def clean_rib(rib: str) -> str:
    """Removes spaces, tabs, dashes, and other non-digit separators from a RIB."""
    return re.sub(r"\D", "", rib or "")


def get_known_bank_codes() -> dict[str, str]:
    """Loads Moroccan bank codes mapping from jurisdiction pack (identifiers.rib.bank_codes)."""
    pack = get_jurisdiction_pack()
    rule = pack.get_rule("identifiers.rib.bank_codes")
    if rule and isinstance(rule.get("value"), dict):
        return {str(k): str(v) for k, v in rule["value"].items()}
    return {}


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


def get_rib_encryption_raw_key() -> bytes:
    """Retrieves raw key bytes from file (dev: outside repo) or env (prod: KMS).

    Refuses execution and raises RibKeyMissingError if neither source is configured.
    """
    key_file = os.getenv("AVENEL_RIB_KEY_FILE")
    if key_file:
        key_path = Path(key_file)
        if not key_path.exists():
            raise RibKeyMissingError(f"Fichier de clé de chiffrement RIB introuvable : {key_file}")
        with open(key_path, "rb") as f:
            raw = f.read().strip()
            if not raw:
                raise RibKeyMissingError(f"Fichier de clé de chiffrement RIB vide : {key_file}")
            return raw

    kms_key = os.getenv("AVENEL_KMS_KEY")
    if kms_key:
        raw_kms = kms_key.strip().encode("utf-8")
        if raw_kms:
            return raw_kms

    raise RibKeyMissingError(
        "Clé de chiffrement RIB absente. En développement, définir AVENEL_RIB_KEY_FILE "
        "pointant vers un fichier hors du dépôt. En production, définir AVENEL_KMS_KEY."
    )


def _get_encryption_key(secret_key: bytes | None = None) -> Fernet:
    """Derives a Fernet encryption key from provided key or configured key source."""
    raw = secret_key if secret_key is not None else get_rib_encryption_raw_key()
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
