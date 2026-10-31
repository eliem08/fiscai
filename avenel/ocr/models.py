"""Pinned ONNX model registry and checksum verification for local OCR.

PaddleOCR multilingual recognition models (Arabic and Latin).
Every model artifact is verified by its SHA-256 checksum before execution.
"""

from __future__ import annotations

import hashlib
import os

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

PINNED_CHECKSUMS: dict[str, str] = {
    "arabic_rec.onnx": "1be9c242e6f4cb974ba19e75b55368eee776c8fe411a7150616f82a210b974c0",
    "arabic_dict.txt": "637c27c88512c22089bef927b34ada08f748dc132ac70facd68d8202384c2726",
    "latin_rec.onnx": "f26feb219f30a5bf6cc8e8e69e5d05dae9114f10c657245747e5629edfacd0ad",
    "latin_dict.txt": "8e6d4e3629788c35c31f7e530287d6147b549bb7a265bd6708bb281134429e2c",
}


def verify_model_checksum(filename: str) -> bool:
    """Verifies that a local model artifact matches its pinned SHA-256 checksum."""
    expected = PINNED_CHECKSUMS.get(filename)
    if not expected:
        return False
    path = os.path.join(MODELS_DIR, filename)
    if not os.path.exists(path):
        return False
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()


def get_model_path(filename: str) -> str | None:
    """Returns absolute path of model file if it exists and checksum matches."""
    path = os.path.join(MODELS_DIR, filename)
    if os.path.exists(path) and verify_model_checksum(filename):
        return path
    return None

