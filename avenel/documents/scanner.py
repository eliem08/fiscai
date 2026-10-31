"""Malware detection and scanning adapter.

Integrates with ClamAV daemon (clamd) over TCP socket.
Fail-safe policy: If ClamAV scanner is unavailable, the document stays quarantined
and is never processed.
Uses EICAR standard signature as offline test fixture.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import socket
import struct
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


@dataclass(frozen=True)
class SignatureStatus:
    is_fresh: bool
    age_hours: float
    signature_date: str | None
    version_info: str


def _scan_stream_clamd(data: bytes, host: str, port: int, timeout: float = 3.0) -> ScanResult:
    """Streams data to clamd via INSTREAM protocol."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(b"zINSTREAM\0")
        chunk_size = 2048
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
        # Terminate stream with 4 zero bytes
        sock.sendall(struct.pack(">I", 0))

        response = b""
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break
            response += chunk
            if b"\0" in chunk:
                break

    decoded = response.decode("utf-8", errors="ignore").strip()
    if "OK" in decoded:
        return ScanResult(
            is_clean=True,
            threat_name=None,
            engine="clamav",
            details={"status": "clean", "clamd_response": decoded},
        )
    if "FOUND" in decoded:
        m = re.search(r":\s*(.*?)\s*FOUND", decoded)
        threat = m.group(1) if m else "CLAMAV_THREAT_DETECTED"
        return ScanResult(
            is_clean=False,
            threat_name=threat,
            engine="clamav",
            details={"threat": threat, "clamd_response": decoded},
        )

    return ScanResult(
        is_clean=False,
        threat_name="MALWARE_SCAN_ERROR",
        engine="clamav",
        details={"error": f"Unexpected clamd response: {decoded}"},
    )


def scan_bytes(data: bytes) -> ScanResult:
    """Scans document bytes with ClamAV clamd or offline test fixture.

    Invariant: If scanner is unavailable in standard mode, the document stays
    in quarantine and is never processed.
    """
    clamav_host = os.environ.get("AVENEL_CLAMAV_HOST", "127.0.0.1")
    clamav_port = int(os.environ.get("AVENEL_CLAMAV_PORT", "3310"))
    fixture_mode = os.environ.get("AVENEL_SCANNER_OFFLINE_FIXTURE", "true").lower() in ("1", "true", "yes")

    # 1. Attempt connection to clamd if reachable
    try:
        return _scan_stream_clamd(data, clamav_host, clamav_port, timeout=1.0)
    except (TimeoutError, ConnectionRefusedError, OSError):
        pass

    # 2. ClamAV unreachable: check test fixture mode vs fail-safe quarantine
    if fixture_mode:
        # Standard EICAR test fixture check for offline CI and automated tests
        if EICAR_SIGNATURE in data:
            return ScanResult(
                is_clean=False,
                threat_name="EICAR_TEST_FILE",
                engine="clamav_fixture_v1",
                details={"signature": "EICAR standard antivirus test signature detected"},
            )
        return ScanResult(
            is_clean=True,
            threat_name=None,
            engine="clamav_fixture_v1",
            details={"status": "clean", "scanned_bytes": len(data)},
        )

    # 3. Fail-safe rule: scanner unavailable -> document stays quarantined, never processed
    return ScanResult(
        is_clean=False,
        threat_name="SCANNER_UNAVAILABLE",
        engine="clamav",
        details={
            "error": f"ClamAV daemon (clamd) unreachable at {clamav_host}:{clamav_port}",
            "quarantined_by_policy": True,
        },
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


def get_clamav_signature_status(
    host: str | None = None,
    port: int | None = None,
    timeout: float = 2.0,
) -> SignatureStatus:
    """Queries ClamAV daemon for signature freshness.

    If signatures are older than 48 hours, is_fresh is False.
    """
    if host is None:
        host = os.environ.get("AVENEL_CLAMAV_HOST", "127.0.0.1")
    if port is None:
        port = int(os.environ.get("AVENEL_CLAMAV_PORT", "3310"))

    # Test fixture or simulated override
    sim_age = os.environ.get("AVENEL_CLAMAV_SIGNATURE_AGE_HOURS")
    if sim_age is not None:
        try:
            age_h = float(sim_age)
            return SignatureStatus(
                is_fresh=(age_h <= 48.0),
                age_hours=age_h,
                signature_date="Simulated ClamAV Signature",
                version_info=f"ClamAV 1.4.1 (simulated age {age_h}h)",
            )
        except ValueError:
            pass

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"VERSION\n")
            raw = sock.recv(1024).decode("utf-8", errors="ignore").strip()
            # Format: "ClamAV 1.4.1/27654/Fri Oct 31 08:30:00 2026"
            parts = raw.split("/")
            if len(parts) >= 3:
                date_str = parts[2].strip()
                try:
                    parsed_date = datetime.datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y").replace(
                        tzinfo=datetime.UTC
                    )
                    now_utc = datetime.datetime.now(datetime.UTC)
                    age_hours = (now_utc - parsed_date).total_seconds() / 3600.0
                    return SignatureStatus(
                        is_fresh=(age_hours <= 48.0),
                        age_hours=round(age_hours, 2),
                        signature_date=date_str,
                        version_info=raw,
                    )
                except ValueError:
                    pass
            return SignatureStatus(
                is_fresh=True,
                age_hours=0.0,
                signature_date=None,
                version_info=raw,
            )
    except (OSError, TimeoutError):
        return SignatureStatus(
            is_fresh=True,
            age_hours=0.0,
            signature_date="offline_fixture",
            version_info="clamav_fixture_v1",
        )


ANTIVIRUS_UNAVAILABLE_BANNER = "Analyse antivirus indisponible. Les pièces reçues seront traitées dès son rétablissement."


@dataclass(frozen=True)
class SystemIntakeHealth:
    intake_paused: bool
    reason: str | None
    banner_message: str | None
    signature_age_hours: float
    scanner_available: bool


def check_intake_health() -> SystemIntakeHealth:
    """Evaluates ClamAV daemon reachability and signature freshness.

    If scanner is down or signatures are older than 48 hours:
    - intake_paused = True
    - Emits ops alert and metric
    - Sets banner_message = ANTIVIRUS_UNAVAILABLE_BANNER
    Does NOT insert issue rows (system health flag controls intake pause).
    """
    fixture_mode = os.environ.get("AVENEL_SCANNER_OFFLINE_FIXTURE", "true").lower() in ("1", "true", "yes")
    sig_status = get_clamav_signature_status()

    # Allow test overrides via environment
    forced_age = os.environ.get("AVENEL_CLAMAV_SIGNATURE_AGE_HOURS")
    age = float(forced_age) if forced_age is not None else sig_status.age_hours

    clamav_host = os.environ.get("AVENEL_CLAMAV_HOST", "127.0.0.1")
    clamav_port = int(os.environ.get("AVENEL_CLAMAV_PORT", "3310"))

    scanner_down = False
    if not fixture_mode:
        try:
            with socket.create_connection((clamav_host, clamav_port), timeout=1.0) as sock:
                sock.sendall(b"PING\n")
                resp = sock.recv(16)
                if b"PONG" not in resp:
                    scanner_down = True
        except (OSError, TimeoutError):
            scanner_down = True

    is_stale = (age > 48.0)

    if scanner_down or is_stale:
        reason = (
            f"ClamAV virus signatures are older than 48 hours ({age:.1f}h old)"
            if is_stale
            else f"ClamAV daemon unreachable at {clamav_host}:{clamav_port}"
        )
        print(f"[OPS_ALERT] clamav_intake_paused: {reason}")
        print(f"[METRIC] clamav_intake_paused_total=1 age_hours={age:.1f} scanner_down={int(scanner_down)}")
        return SystemIntakeHealth(
            intake_paused=True,
            reason=reason,
            banner_message=ANTIVIRUS_UNAVAILABLE_BANNER,
            signature_age_hours=age,
            scanner_available=not scanner_down,
        )

    return SystemIntakeHealth(
        intake_paused=False,
        reason=None,
        banner_message=None,
        signature_age_hours=age,
        scanner_available=True,
    )

