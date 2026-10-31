"""Unit tests for ClamAV malware scanner and fail-safe quarantine."""

import os
from unittest.mock import patch

from avenel.documents.scanner import EICAR_SIGNATURE, scan_bytes


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

