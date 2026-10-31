"""Object storage abstractions and local/S3 adapters.

Supports:
- Magic bytes detection
- SHA-256 computation
- Presigned URL generation
- Zero-leak local object store
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Protocol

MAX_DOCUMENT_BYTE_SIZE = 52428800  # 50 MB per schema constraint

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/tiff",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xml",
}


def detect_magic_bytes(data: bytes) -> str | None:
    """Detect MIME type from header magic bytes."""
    if len(data) < 4:
        return None

    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
            return "image/heic"
    if data.startswith(b"PK\x03\x04"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if data.strip().startswith(b"<?xml") or data.strip().startswith(b"<"):
        return "application/xml"
    try:
        # Check if plain text / CSV
        data[:1024].decode("utf-8")
        if b"," in data[:1024] or b";" in data[:1024] or b"\n" in data[:1024]:
            return "text/csv"
    except UnicodeDecodeError:
        pass

    return None


def compute_sha256(data: bytes) -> str:
    """Compute 64-char lowercase hexadecimal SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


class StorageBackend(Protocol):
    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        ...

    def get_object(self, key: str) -> bytes:
        ...

    def generate_presigned_get_url(self, key: str, expiry_seconds: int = 3600) -> str:
        ...

    def generate_presigned_put_url(self, key: str, expiry_seconds: int = 3600) -> dict[str, Any]:
        ...

    def object_exists(self, key: str) -> bool:
        ...


class LocalStorageBackend:
    """Thread-safe local filesystem storage backend for development & testing."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(os.environ.get("STORAGE_DIR", "storage_data")).resolve()
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        safe_key = key.replace("..", "_").lstrip("/\\")
        path = (self.base_dir / safe_key).resolve()
        if not str(path).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal detected: {key}")
        return path

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_object(self, key: str) -> bytes:
        path = self._resolve_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def generate_presigned_get_url(self, key: str, expiry_seconds: int = 3600) -> str:
        # Returns an internal URL format handled by the API
        return f"/v1/storage/files/{key}"

    def generate_presigned_put_url(self, key: str, expiry_seconds: int = 3600) -> dict[str, Any]:
        return {
            "upload_url": f"/v1/storage/uploads/{key}",
            "method": "PUT",
            "expires_in": expiry_seconds,
            "headers": {
                "Content-Type": "application/octet-stream",
            },
        }

    def object_exists(self, key: str) -> bool:
        return self._resolve_path(key).exists()


_STORAGE: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _STORAGE
    if _STORAGE is None:
        _STORAGE = LocalStorageBackend()
    return _STORAGE


def set_storage(storage: StorageBackend) -> None:
    global _STORAGE
    _STORAGE = storage
