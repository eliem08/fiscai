"""Unit tests for ClamAV malware scanner and fail-safe quarantine."""

import os
from unittest.mock import MagicMock, patch
import uuid

from avenel.documents.scanner import (
    EICAR_SIGNATURE,
    SignatureStatus,
    check_and_record_clamav_freshness,
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


def test_check_and_record_clamav_freshness_creates_blocking_issue():
    """When ClamAV signatures are older than 48 hours, records INTEGRATION_FAILURE blocking issue."""
    mock_status = SignatureStatus(
        is_fresh=False,
        age_hours=52.5,
        signature_date="Wed Oct 28 08:30:00 2026",
        version_info="ClamAV 1.4.1/27600/Wed Oct 28 08:30:00 2026",
    )

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    issue_uuid = uuid.uuid4()
    mock_cursor.fetchone.return_value = (str(issue_uuid),)

    tenant_id = uuid.uuid4()
    client_entity_id = uuid.uuid4()
    work_request_id = uuid.uuid4()

    with patch("avenel.documents.scanner.get_clamav_signature_status", return_value=mock_status):
        st, created_id = check_and_record_clamav_freshness(
            conn=mock_conn,
            tenant_id=tenant_id,
            client_entity_id=client_entity_id,
            work_request_id=work_request_id,
        )

        assert st.is_fresh is False
        assert created_id == issue_uuid
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        sql_query = call_args[0]
        assert "INTEGRATION_FAILURE" in sql_query
        assert "blocking" in sql_query


