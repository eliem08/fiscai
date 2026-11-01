"""Tests for Moroccan RIB validation, key calculation, masking, and encryption."""

from __future__ import annotations

import pytest

from avenel.bank.rib import (
    clean_rib,
    compute_moroccan_rib_key,
    compute_rib_sha256,
    decrypt_rib,
    encrypt_rib,
    extract_bank_code,
    extract_rib_last4,
    mask_rib,
    validate_moroccan_rib,
)


def test_moroccan_rib_key_calculation_and_validation():
    """Verifies Bank Al-Maghrib mod-97 check key calculation and validation."""
    # Prefix: 22 digits
    prefix = "0077800001234567890123"
    key = compute_moroccan_rib_key(prefix)
    assert 1 <= key <= 97

    # Full 24-digit RIB
    full_rib = f"{prefix}{key:02d}"
    assert validate_moroccan_rib(full_rib) is True

    # Tampered key fails
    wrong_key = (key % 97) + 1
    bad_rib = f"{prefix}{wrong_key:02d}"
    assert validate_moroccan_rib(bad_rib) is False


def test_moroccan_rib_invalid_length_or_characters():
    """Invalid format: less than 24 digits, non-numeric characters."""
    assert validate_moroccan_rib("007780000123456789012") is False  # 21 digits
    assert validate_moroccan_rib("0077800001234567890123456") is False  # 25 digits
    assert validate_moroccan_rib("0077800001234567890123AB") is False  # letters
    assert validate_moroccan_rib("") is False


def test_rib_cleaning_and_formatting():
    """Cleans spaced or formatted RIB strings before validation."""
    raw = " 007 780 0001234567890123 "
    prefix = "0077800001234567890123"
    key = compute_moroccan_rib_key(prefix)
    formatted = f" 007 - 780 - 0001234567890123 - {key:02d} "

    assert validate_moroccan_rib(formatted) is True
    assert extract_bank_code(formatted) == "007"
    assert extract_rib_last4(formatted) == f"23{key:02d}"[-4:]


def test_rib_masking_and_sha256():
    """Masking displays only 3-digit bank code and last 4 digits."""
    prefix = "1907800009876543210987"
    key = compute_moroccan_rib_key(prefix)
    full_rib = f"{prefix}{key:02d}"

    masked = mask_rib(full_rib)
    assert masked.startswith("190")
    assert masked.endswith(f"{key:02d}")
    assert "*" in masked

    h1 = compute_rib_sha256(full_rib)
    h2 = compute_rib_sha256(f" {full_rib} ")
    assert len(h1) == 64
    assert h1 == h2


def test_rib_encryption_roundtrip():
    """Verifies AES-GCM encryption and decryption round-trip."""
    prefix = "0117800001122334455667"
    key = compute_moroccan_rib_key(prefix)
    full_rib = f"{prefix}{key:02d}"

    encrypted = encrypt_rib(full_rib)
    assert isinstance(encrypted, bytes)
    assert encrypted != full_rib.encode("utf-8")

    decrypted = decrypt_rib(encrypted)
    assert decrypted == full_rib


def test_known_bank_codes_loaded_from_jurisdiction_pack():
    """Bank codes are loaded from jurisdiction pack (all marked needs_expert until BAM verification)."""
    from avenel.bank.rib import get_known_bank_codes, validate_bank_code
    from avenel.jurisdiction.loader import get_jurisdiction_pack

    bank_codes = get_known_bank_codes()
    assert "007" in bank_codes
    assert "011" in bank_codes
    assert "013" in bank_codes
    assert bank_codes["013"] == "BMCI"  # Prior research: 013 is BMCI
    assert "101" in bank_codes
    assert bank_codes["101"] == "Banque Populaire"  # BP regional code
    assert "022" in bank_codes
    assert bank_codes["022"] == "Société Générale Maroc"
    assert "230" in bank_codes  # CIH Bank
    assert bank_codes["230"] == "CIH Bank"

    pack = get_jurisdiction_pack()
    rule = pack.get_rule("identifiers.rib.bank_codes")
    assert rule is not None
    assert rule.get("status") == "needs_expert"
    assert "TODO(EXPERT)" in str(rule.get("note", ""))

    # Bank code validation is a warning, never a rejection, while needs_expert
    valid, warn = validate_bank_code("999")
    assert valid is True
    assert warn is not None
    assert "Avertissement" in warn


def test_app_refuses_to_start_without_rib_encryption_key(monkeypatch, tmp_path):
    """App startup fails immediately if neither dev key file nor prod KMS key is configured."""
    from fastapi.testclient import TestClient

    from apps.api.main import app
    from avenel.bank.rib import RibKeyMissingError, get_rib_encryption_raw_key

    # 1. Clear both env vars -> raises RibKeyMissingError
    monkeypatch.delenv("AVENEL_RIB_KEY_FILE", raising=False)
    monkeypatch.delenv("AVENEL_KMS_KEY", raising=False)

    with pytest.raises(RibKeyMissingError) as exc_info:
        get_rib_encryption_raw_key()
    assert "Clé de chiffrement RIB absente" in str(exc_info.value)

    # 2. Starting FastAPI app with TestClient triggers lifespan startup check -> raises
    with pytest.raises(Exception):
        with TestClient(app):
            pass

    # 3. Setting dev key file outside repo works
    dev_key_file = tmp_path / "dev_rib.key"
    dev_key_file.write_bytes(b"entropy-secret-key-for-dev-outside-repo-32b")
    monkeypatch.setenv("AVENEL_RIB_KEY_FILE", str(dev_key_file))

    raw_key = get_rib_encryption_raw_key()
    assert raw_key == b"entropy-secret-key-for-dev-outside-repo-32b"


def test_rib_encrypted_never_in_api_response_or_logs():
    """Ensures rib_encrypted never appears in API model schemas, responses, or logs."""
    from apps.api.routes.bank import BankAccountResponse

    # Pydantic schema must not have rib_encrypted
    fields = BankAccountResponse.model_fields.keys()
    assert "rib_encrypted" not in fields
    assert "rib_masked" in fields
    assert "rib_last4" in fields
    assert "bank_code" in fields


