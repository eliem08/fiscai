"""Malware detection and scanning adapter.

Inspects document streams for malicious payload signatures (including EICAR)
and appends immutable evidence records.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from avenel.infrastructure.storage import compute_sha256

EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass(frozen=True)
class ScanResult:
    is_clean: bool
    threat_name: str | None
    engine: str
    details: dict[str, Any]


def scan_bytes(data: bytes) -> ScanResult:
    """Deterministic local malware scan against signature database."""
    if EICAR_SIGNATURE in data:
        return ScanResult(
            is_clean=False,
            threat_name="EICAR_TEST_FILE",
            engine="avenel_local_scanner_v1",
            details={"signature": "EICAR standard test signature detected"},
        )

    # Embedded executable signature check in non-executable files
    if data.startswith(b"MZ") or b"This program cannot be run in DOS mode" in data[:1024]:
        return ScanResult(
            is_clean=False,
            threat_name="EMBEDDED_EXECUTABLE_PE",
            engine="avenel_local_scanner_v1",
            details={"signature": "Windows PE binary header detected in document payload"},
        )

    return ScanResult(
        is_clean=True,
        threat_name=None,
        engine="avenel_local_scanner_v1",
        details={"status": "clean", "scanned_bytes": len(data)},
    )


def record_scan_evidence(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    document_id: uuid.UUID,
    scan_result: ScanResult,
) -> uuid.UUID:
    """Appends an immutable malware scan record to evidence_records."""
    payload = {
        "is_clean": scan_result.is_clean,
        "threat_name": scan_result.threat_name,
        "engine": scan_result.engine,
        "details": scan_result.details,
    }
    content_sha256 = compute_sha256(json.dumps(payload, sort_keys=True).encode("utf-8"))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO evidence_records (
                tenant_id, work_request_id, subject_type, subject_id, kind, payload, content_sha256
            ) VALUES (%s, %s, 'document', %s, 'malware_scan', %s, %s)
            RETURNING id;
            """,
            (
                tenant_id,
                work_request_id,
                document_id,
                json.dumps(payload),
                content_sha256,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return uuid.UUID(str(row[0]))
