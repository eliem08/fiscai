"""Unit tests for ClamAV malware scanner and fail-safe quarantine."""

import os
from unittest.mock import MagicMock, patch

from avenel.documents.scanner import (
    ANTIVIRUS_UNAVAILABLE_BANNER,
    EICAR_SIGNATURE,
    SignatureStatus,
    check_intake_health,
    get_clamav_signature_status,
    scan_bytes,
)


def test_clean_document_scan_in_fixture_mode():
    data = b"%PDF-1.4 clean document content"
    with patch.dict(os.environ, {"AVENEL_SCANNER_OFFLINE_FIXTURE": "true"}):
        res = scan_bytes(data)
        assert res.is_clean is True
        assert res.threat_name is None


def test_eicar_signature_detection():
    data = b"%PDF-1.4 " + EICAR_SIGNATURE
    with patch.dict(os.environ, {"AVENEL_SCANNER_OFFLINE_FIXTURE": "true"}):
        res = scan_bytes(data)
        assert res.is_clean is False
        assert res.threat_name == "EICAR_TEST_FILE"


def test_scanner_unavailable_fail_safe_quarantine():
    """When ClamAV daemon is unreachable, the document stays quarantined and is never processed."""
    data = b"%PDF-1.4 clean document content"
    with patch.dict(os.environ, {"AVENEL_SCANNER_OFFLINE_FIXTURE": "false", "AVENEL_CLAMAV_PORT": "59999"}):
        res = scan_bytes(data)
        assert res.is_clean is False
        assert res.threat_name == "SCANNER_UNAVAILABLE"
        assert res.details.get("quarantined_by_policy") is True


def test_clamav_signature_status_fresh_and_stale():
    """Tests ClamAV signature freshness check against the 48h SLA gate."""
    # 1. Fresh signatures (e.g. 5 hours ago)
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    fresh_time = now - datetime.timedelta(hours=5)
    fresh_str = fresh_time.strftime("%a %b %d %H:%M:%S %Y")
    mock_resp_fresh = f"ClamAV 1.4.1/27654/{fresh_str}\n".encode("utf-8")

    mock_sock = MagicMock()
    mock_sock.recv.return_value = mock_resp_fresh
    mock_sock.__enter__.return_value = mock_sock

    with patch("socket.create_connection", return_value=mock_sock):
        st = get_clamav_signature_status()
        assert st.is_fresh is True
        assert st.age_hours < 48.0

    # 2. Stale signatures (> 48h, e.g. 72 hours ago)
    stale_time = now - datetime.timedelta(hours=72)
    stale_str = stale_time.strftime("%a %b %d %H:%M:%S %Y")
    mock_resp_stale = f"ClamAV 1.4.1/27600/{stale_str}\n".encode("utf-8")

    mock_sock.recv.return_value = mock_resp_stale
    with patch("socket.create_connection", return_value=mock_sock):
        st = get_clamav_signature_status()
        assert st.is_fresh is False
        assert st.age_hours >= 70.0


def test_check_intake_health_paused_when_stale():
    """When ClamAV signatures are older than 48 hours, intake_paused is True, banner is set, and no issue row is inserted."""
    mock_status = SignatureStatus(
        is_fresh=False,
        age_hours=52.5,
        signature_date="Wed Oct 28 08:30:00 2026",
        version_info="ClamAV 1.4.1/27600/Wed Oct 28 08:30:00 2026",
    )

    with patch("avenel.documents.scanner.get_clamav_signature_status", return_value=mock_status):
        health = check_intake_health()

        assert health.intake_paused is True
        assert health.signature_age_hours == 52.5
        assert health.banner_message == ANTIVIRUS_UNAVAILABLE_BANNER
        assert "52.5h" in (health.reason or "")


def test_check_intake_health_paused_when_scanner_down():
    """When ClamAV daemon is unreachable in live mode, intake_paused is True with console banner."""
    mock_status = SignatureStatus(
        is_fresh=True,
        age_hours=2.0,
        signature_date="Sat Oct 31 12:00:00 2026",
        version_info="ClamAV 1.4.1/27654",
    )

    with (
        patch.dict(os.environ, {"AVENEL_SCANNER_OFFLINE_FIXTURE": "false", "AVENEL_CLAMAV_PORT": "59999"}),
        patch("avenel.documents.scanner.get_clamav_signature_status", return_value=mock_status),
    ):
        health = check_intake_health()

        assert health.intake_paused is True
        assert health.scanner_available is False
        assert health.banner_message == ANTIVIRUS_UNAVAILABLE_BANNER


def test_check_intake_health_active_when_fresh():
    """When ClamAV daemon is reachable and signatures <= 48h, intake_paused is False."""
    mock_status = SignatureStatus(
        is_fresh=True,
        age_hours=4.0,
        signature_date="Sat Oct 31 12:00:00 2026",
        version_info="ClamAV 1.4.1/27654",
    )

    with patch("avenel.documents.scanner.get_clamav_signature_status", return_value=mock_status):
        health = check_intake_health()

        assert health.intake_paused is False
        assert health.banner_message is None
        assert health.reason is None



