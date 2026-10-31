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
