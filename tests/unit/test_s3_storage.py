"""Unit tests for S3-compatible storage backend with residency, SSE, and Object Lock handling."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from avenel.infrastructure.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    get_storage,
    set_storage,
)


def test_s3_storage_initialization_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.ma-casablanca-1.inwi.ma")
    monkeypatch.setenv("S3_REGION", "ma-casablanca-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("S3_SERVER_SIDE_ENCRYPTION", "AES256")
    monkeypatch.setenv("S3_ENABLE_OBJECT_LOCK", "false")

    backend = S3StorageBackend()
    assert backend.endpoint_url == "https://s3.ma-casablanca-1.inwi.ma"
    assert backend.region_name == "ma-casablanca-1"
    assert backend.bucket_name == "test-bucket"
    assert backend.server_side_encryption == "AES256"
    assert backend.enable_object_lock is False


def test_s3_put_object_with_sse() -> None:
    mock_client = MagicMock()
    backend = S3StorageBackend(
        bucket_name="test-bucket",
        server_side_encryption="AES256",
        enable_object_lock=False,
        s3_client=mock_client,
    )

    data = b"%PDF-1.4 sample invoice"
    backend.put_object("documents/tenant1/doc1/v1", data, "application/pdf")

    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="documents/tenant1/doc1/v1",
        Body=data,
        ContentType="application/pdf",
        ServerSideEncryption="AES256",
    )


def test_s3_put_original_with_object_lock_compliance() -> None:
    mock_client = MagicMock()
    backend = S3StorageBackend(
        bucket_name="test-bucket",
        server_side_encryption="AES256",
        enable_object_lock=True,
        s3_client=mock_client,
    )

    data = b"%PDF-1.4 sample invoice"
    retain_date = datetime.date(2036, 12, 31)
    backend.put_original("documents/tenant1/doc1/v1", data, "application/pdf", retain_until=retain_date)

    expected_dt = datetime.datetime.combine(
        retain_date,
        datetime.time(23, 59, 59, tzinfo=datetime.UTC),
    )
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="documents/tenant1/doc1/v1",
        Body=data,
        ContentType="application/pdf",
        ServerSideEncryption="AES256",
        ObjectLockMode="COMPLIANCE",
        ObjectLockRetainUntilDate=expected_dt,
    )


def test_s3_put_object_graceful_fallback_when_object_lock_unsupported() -> None:
    mock_client = MagicMock()
    # First call raises ClientError indicating ObjectLockConfigurationNotFoundError, second call succeeds
    error_response = {
        "Error": {
            "Code": "ObjectLockConfigurationNotFoundError",
            "Message": "Object Lock configuration does not exist for this bucket",
        }
    }
    mock_client.put_object.side_effect = [
        ClientError(error_response, "PutObject"),
        {"ETag": "dummy-etag"},
    ]

    backend = S3StorageBackend(
        bucket_name="test-bucket",
        server_side_encryption="AES256",
        enable_object_lock=True,
        s3_client=mock_client,
    )

    data = b"%PDF-1.4 sample invoice"
    retain_date = datetime.date(2036, 12, 31)
    backend.put_object("documents/tenant1/doc1/v1", data, "application/pdf", retain_until=retain_date)

    assert mock_client.put_object.call_count == 2
    # Second call must have stripped ObjectLockMode and ObjectLockRetainUntilDate but kept SSE
    second_call_kwargs = mock_client.put_object.call_args_list[1].kwargs
    assert "ObjectLockMode" not in second_call_kwargs
    assert "ObjectLockRetainUntilDate" not in second_call_kwargs
    assert second_call_kwargs["ServerSideEncryption"] == "AES256"


def test_s3_get_object_success_and_not_found() -> None:
    mock_client = MagicMock()
    body_mock = MagicMock()
    body_mock.read.return_value = b"sample content"
    mock_client.get_object.return_value = {"Body": body_mock}

    backend = S3StorageBackend(bucket_name="test-bucket", s3_client=mock_client)
    res = backend.get_object("documents/tenant1/doc1/v1")
    assert res == b"sample content"

    # Test not found raises FileNotFoundError
    not_found_response = {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}
    mock_client.get_object.side_effect = ClientError(not_found_response, "GetObject")
    with pytest.raises(FileNotFoundError, match="Object not found"):
        backend.get_object("documents/tenant1/missing/v1")


def test_s3_presigned_urls() -> None:
    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = lambda op, Params, ExpiresIn: f"https://s3.host/{Params['Key']}?sig={op}"

    backend = S3StorageBackend(
        bucket_name="test-bucket",
        server_side_encryption="AES256",
        s3_client=mock_client,
    )

    get_url = backend.generate_presigned_get_url("documents/doc1/v1", expiry_seconds=900)
    assert get_url == "https://s3.host/documents/doc1/v1?sig=get_object"

    put_data = backend.generate_presigned_put_url("documents/doc1/v1", expiry_seconds=900)
    assert put_data["method"] == "PUT"
    assert put_data["expires_in"] == 900
    assert put_data["upload_url"] == "https://s3.host/documents/doc1/v1?sig=put_object"
    assert put_data["headers"]["x-amz-server-side-encryption"] == "AES256"


def test_s3_object_exists() -> None:
    mock_client = MagicMock()
    mock_client.head_object.return_value = {"ContentLength": 100}

    backend = S3StorageBackend(bucket_name="test-bucket", s3_client=mock_client)
    assert backend.object_exists("documents/doc1/v1") is True

    # 404 response
    mock_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    assert backend.object_exists("documents/missing/v1") is False


def test_storage_factory_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "filesystem")
    set_storage(LocalStorageBackend())
    assert isinstance(get_storage(), LocalStorageBackend)
