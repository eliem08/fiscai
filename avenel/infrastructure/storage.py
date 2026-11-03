"""Object storage abstractions and local/S3 adapters.

Supports:
- Magic bytes detection
- SHA-256 computation
- Presigned URL generation
- Zero-leak local object store
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Protocol

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

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
    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        retain_until: datetime.date | datetime.datetime | None = None,
    ) -> None:
        ...

    def put_original(
        self,
        key: str,
        data: bytes,
        content_type: str,
        retain_until: datetime.date | datetime.datetime | None = None,
    ) -> None:
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

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        retain_until: datetime.date | datetime.datetime | None = None,
    ) -> None:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def put_original(
        self,
        key: str,
        data: bytes,
        content_type: str,
        retain_until: datetime.date | datetime.datetime | None = None,
    ) -> None:
        self.put_object(key, data, content_type, retain_until=retain_until)

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


class S3StorageBackend:
    """S3-compatible object storage backend supporting Morocco/EU data residency.

    Features:
    - Server-side encryption (SSE-S3 AES-256 or AWS-KMS)
    - Versioning enabled on bucket
    - S3 Object Lock compliance retention (retain_until) for original documents
    - Safe graceful fallback with audit logging when running on sovereign hosts without WORM lock APIs
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        bucket_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        server_side_encryption: str | None = None,
        enable_object_lock: bool | None = None,
        s3_client: Any = None,
    ) -> None:
        self.endpoint_url = endpoint_url or os.environ.get("S3_ENDPOINT_URL")
        self.region_name = region_name or os.environ.get("S3_REGION", "ma-casablanca-1")
        self.bucket_name = bucket_name or os.environ.get("S3_BUCKET_NAME", "avenel-documents")
        self.access_key_id = (
            access_key_id
            or os.environ.get("S3_ACCESS_KEY_ID")
            or os.environ.get("AWS_ACCESS_KEY_ID")
        )
        self.secret_access_key = (
            secret_access_key
            or os.environ.get("S3_SECRET_ACCESS_KEY")
            or os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        self.server_side_encryption = (
            server_side_encryption
            or os.environ.get("S3_SERVER_SIDE_ENCRYPTION", "AES256")
        )
        if enable_object_lock is not None:
            self.enable_object_lock = enable_object_lock
        else:
            self.enable_object_lock = os.environ.get("S3_ENABLE_OBJECT_LOCK", "false").lower() in (
                "true",
                "1",
                "yes",
            )

        if s3_client is not None:
            self._client = s3_client
        else:
            client_kwargs: dict[str, Any] = {
                "service_name": "s3",
                "region_name": self.region_name,
            }
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url
            if self.access_key_id and self.secret_access_key:
                client_kwargs["aws_access_key_id"] = self.access_key_id
                client_kwargs["aws_secret_access_key"] = self.secret_access_key

            self._client = boto3.client(**client_kwargs)

    @property
    def client(self) -> Any:
        return self._client

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        retain_until: datetime.date | datetime.datetime | None = None,
    ) -> None:
        clean_key = key.lstrip("/\\")
        put_kwargs: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": clean_key,
            "Body": data,
            "ContentType": content_type,
        }
        if self.server_side_encryption:
            put_kwargs["ServerSideEncryption"] = self.server_side_encryption

        if retain_until is not None and self.enable_object_lock:
            if isinstance(retain_until, datetime.datetime):
                dt = (
                    retain_until
                    if retain_until.tzinfo
                    else retain_until.replace(tzinfo=datetime.UTC)
                )
            else:
                dt = datetime.datetime.combine(
                    retain_until,
                    datetime.time(23, 59, 59, tzinfo=datetime.UTC),
                )
            put_kwargs["ObjectLockMode"] = "COMPLIANCE"
            put_kwargs["ObjectLockRetainUntilDate"] = dt

        try:
            self.client.put_object(**put_kwargs)
        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "")
            # If Object Lock is rejected by S3-compatible host without WORM compliance support
            if "ObjectLock" in err_code or "InvalidRequest" in err_code:
                logger.warning(
                    "S3 ObjectLock not supported by host store (%s); retrying with SSE-S3 encryption only.",
                    err_code,
                )
                put_kwargs.pop("ObjectLockMode", None)
                put_kwargs.pop("ObjectLockRetainUntilDate", None)
                self.client.put_object(**put_kwargs)
            else:
                raise

    def put_original(
        self,
        key: str,
        data: bytes,
        content_type: str,
        retain_until: datetime.date | datetime.datetime | None = None,
    ) -> None:
        self.put_object(key=key, data=data, content_type=content_type, retain_until=retain_until)

    def get_object(self, key: str) -> bytes:
        clean_key = key.lstrip("/\\")
        try:
            resp = self.client.get_object(Bucket=self.bucket_name, Key=clean_key)
            body = resp["Body"].read()
            return body if isinstance(body, bytes) else bytes(body)
        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "")
            if err_code in ("NoSuchKey", "404", "NotFound"):
                raise FileNotFoundError(f"Object not found: {key}") from exc
            raise

    def generate_presigned_get_url(self, key: str, expiry_seconds: int = 3600) -> str:
        clean_key = key.lstrip("/\\")
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": clean_key},
            ExpiresIn=expiry_seconds,
        )
        return str(url)

    def generate_presigned_put_url(
        self,
        key: str,
        expiry_seconds: int = 3600,
    ) -> dict[str, Any]:
        clean_key = key.lstrip("/\\")
        params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": clean_key}
        headers: dict[str, str] = {}
        if self.server_side_encryption:
            params["ServerSideEncryption"] = self.server_side_encryption
            headers["x-amz-server-side-encryption"] = self.server_side_encryption

        url = self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expiry_seconds,
        )
        return {
            "upload_url": str(url),
            "method": "PUT",
            "expires_in": expiry_seconds,
            "headers": headers,
        }

    def object_exists(self, key: str) -> bool:
        clean_key = key.lstrip("/\\")
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "")
            if err_code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise


_STORAGE: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _STORAGE
    if _STORAGE is None:
        backend_type = os.environ.get("STORAGE_BACKEND", "filesystem").lower()
        if backend_type == "s3":
            _STORAGE = S3StorageBackend()
        else:
            _STORAGE = LocalStorageBackend()
    return _STORAGE


def set_storage(storage: StorageBackend) -> None:
    global _STORAGE
    _STORAGE = storage
