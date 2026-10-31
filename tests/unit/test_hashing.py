"""Golden tests for canonical JSON and proposal set hashing per ARCHITECTURE.md D.4."""

from datetime import date
from decimal import Decimal

from avenel.approvals.hashing import canonical_json, compute_proposal_set_hash


def test_canonical_json_formatting():
    data = {
        "b": Decimal("1250.00"),
        "a": date(2026, 9, 15),
        "nested": {"z": 1, "y": Decimal("10.50")},
    }
    # Sorted keys, no whitespace, decimals 2 places, dates ISO-8601
    expected = '{"a":"2026-09-15","b":"1250.00","nested":{"y":"10.50","z":1}}'
    assert canonical_json(data) == expected


def test_proposal_set_hash_determinism():
    proposals = [
        {
            "id": "prop-2",
            "journal_code": "ACH",
            "lines": [
                {"line_no": 2, "debit_mad": Decimal("0.00"), "credit_mad": Decimal("1200.00")},
                {"line_no": 1, "debit_mad": Decimal("1200.00"), "credit_mad": Decimal("0.00")},
            ],
        },
        {
            "id": "prop-1",
            "journal_code": "BQ1",
            "lines": [
                {"line_no": 1, "debit_mad": Decimal("500.00"), "credit_mad": Decimal("0.00")},
                {"line_no": 2, "debit_mad": Decimal("0.00"), "credit_mad": Decimal("500.00")},
            ],
        },
    ]
    accepted_matches = [
        {"id": "match-1", "amount_mad": Decimal("1200.00")},
    ]

    h1 = compute_proposal_set_hash(proposals, accepted_matches)
    # Order of proposals passed shouldn't change the deterministic hash
    h2 = compute_proposal_set_hash(list(reversed(proposals)), accepted_matches)

    assert h1 == h2
    assert len(h1) == 64
