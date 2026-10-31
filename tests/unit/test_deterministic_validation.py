"""Unit tests for Section D.6 Deterministic Invoice Validation."""

from __future__ import annotations

import datetime
from avenel.extraction.validation import validate_invoice_extraction
from avenel.jurisdiction.loader import get_jurisdiction_pack


def test_validation_all_clean_purchase_invoice():
    """Clean purchase invoice with standard verified VAT passes validation with zero issues."""
    pack = get_jurisdiction_pack()
    std_rate = float(pack.get_value("vat.rate.standard", 0.20))

    base_ht = 1000.0
    tax_amt = base_ht * std_rate
    ttc_amt = base_ht + tax_amt

    fields = {
        "invoice_number": {"value": "FAC-2026-001"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": "Fournisseur Avenel SARL"},
        "supplier_ice": {"value": "001234567890123"},
        "supplier_if": {"value": "12345678"},
        "client_name": {"value": "Client SA"},
        "total_ht": {"value": base_ht},
        "total_vat": {"value": tax_amt},
        "total_ttc": {"value": ttc_amt},
        "tax_breakdown": [{"rate": std_rate, "base_ht": base_ht, "tax_amount": tax_amt}],
        "supplier_is_auto_entrepreneur": {"value": False},
        "payment_method": {"value": "bank_transfer"},
    }

    report = validate_invoice_extraction(
        fields=fields,
        doc_type="purchase_invoice",
        period_start=datetime.date(2026, 3, 1),
        period_end=datetime.date(2026, 3, 31),
    )

    assert report.is_valid is True
    assert report.blocking_count == 0
    assert report.review_count == 0


def test_validation_missing_mandatory_purchase_mention():
    """Missing mandatory mentions on purchase invoice triggers INVOICE_MISSING_MANDATORY_FIELD with review severity."""
    fields = {
        "invoice_number": {"value": "FAC-2026-001"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": None},  # Missing supplier name
        "supplier_ice": {"value": None},   # Missing supplier ICE
        "total_ht": {"value": 1000.0},
        "total_vat": {"value": 200.0},
        "total_ttc": {"value": 1200.0},
    }

    report = validate_invoice_extraction(fields=fields, doc_type="purchase_invoice")
    missing_issues = [i for i in report.issues if i.code == "INVOICE_MISSING_MANDATORY_FIELD"]
    assert len(missing_issues) >= 2
    assert all(i.severity == "review" for i in missing_issues)


def test_validation_arithmetic_inconsistency_blocks():
    """Inconsistent totals trigger TOTALS_INCONSISTENT blocking issue."""
    fields = {
        "invoice_number": {"value": "FAC-2026-001"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": "Fournisseur SARL"},
        "supplier_ice": {"value": "001234567890123"},
        "supplier_if": {"value": "12345678"},
        "client_name": {"value": "Client SA"},
        "total_ht": {"value": 1000.0},
        "total_vat": {"value": 200.0},
        "total_ttc": {"value": 1500.0},  # Inconsistent: 1000 + 200 != 1500
        "tax_breakdown": [{"rate": 0.20, "base_ht": 1000.0, "tax_amount": 200.0}],
    }

    report = validate_invoice_extraction(fields=fields, doc_type="purchase_invoice")
    assert report.is_valid is False
    assert report.blocking_count >= 1
    assert any(i.code == "TOTALS_INCONSISTENT" and i.severity == "blocking" for i in report.issues)


def test_validation_unknown_vat_rate_blocks():
    """Unrecognized VAT rate not in pack triggers VAT_RATE_UNKNOWN blocking issue."""
    fields = {
        "invoice_number": {"value": "FAC-2026-001"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": "Fournisseur SARL"},
        "supplier_ice": {"value": "001234567890123"},
        "supplier_if": {"value": "12345678"},
        "client_name": {"value": "Client SA"},
        "total_ht": {"value": 1000.0},
        "total_vat": {"value": 150.0},
        "total_ttc": {"value": 1150.0},
        "tax_breakdown": [{"rate": 0.15, "base_ht": 1000.0, "tax_amount": 150.0}],  # 15% does not exist in Morocco
    }

    report = validate_invoice_extraction(fields=fields, doc_type="purchase_invoice")
    assert report.is_valid is False
    assert any(i.code == "VAT_RATE_UNKNOWN" and i.severity == "blocking" for i in report.issues)


def test_validation_auto_entrepreneur_charging_vat():
    """Auto-entrepreneur invoicing VAT triggers VAT_ON_AUTO_ENTREPRENEUR_INVOICE review issue."""
    fields = {
        "invoice_number": {"value": "AE-2026-01"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": "Prestataire AE"},
        "supplier_ice": {"value": "001234567890123"},
        "supplier_if": {"value": "12345678"},
        "client_name": {"value": "Client SA"},
        "supplier_is_auto_entrepreneur": {"value": True},
        "total_ht": {"value": 1000.0},
        "total_vat": {"value": 200.0},  # Forbidden for auto-entrepreneurs
        "total_ttc": {"value": 1200.0},
        "tax_breakdown": [{"rate": 0.20, "base_ht": 1000.0, "tax_amount": 200.0}],
    }

    report = validate_invoice_extraction(fields=fields, doc_type="purchase_invoice")
    assert any(i.code == "VAT_ON_AUTO_ENTREPRENEUR_INVOICE" and i.severity == "review" for i in report.issues)


def test_validation_cash_limit_exceeded():
    """Cash payment exceeding daily limit triggers VAT_NOT_DEDUCTIBLE_CASH_LIMIT review issue."""
    pack = get_jurisdiction_pack()
    limit = float(pack.get_value("vat.deduction.cash_limit.daily", 5000.00))

    over_ttc = limit + 1000.0
    fields = {
        "invoice_number": {"value": "CASH-2026-01"},
        "invoice_date": {"value": "2026-03-15"},
        "supplier_name": {"value": "Magasin SARL"},
        "supplier_ice": {"value": "001234567890123"},
        "supplier_if": {"value": "12345678"},
        "client_name": {"value": "Client SA"},
        "payment_method": {"value": "cash"},
        "total_ht": {"value": 5000.0},
        "total_vat": {"value": 1000.0},
        "total_ttc": {"value": over_ttc},
        "tax_breakdown": [{"rate": 0.20, "base_ht": 5000.0, "tax_amount": 1000.0}],
    }

    report = validate_invoice_extraction(fields=fields, doc_type="purchase_invoice")
    assert any(i.code == "VAT_NOT_DEDUCTIBLE_CASH_LIMIT" and i.severity == "review" for i in report.issues)


def test_validation_period_mismatch():
    """Invoice date outside period date range triggers PERIOD_MISMATCH review issue."""
    fields = {
        "invoice_number": {"value": "FAC-2026-01"},
        "invoice_date": {"value": "2026-01-15"},  # Prior to March period
        "supplier_name": {"value": "Fournisseur SARL"},
        "supplier_ice": {"value": "001234567890123"},
        "supplier_if": {"value": "12345678"},
        "client_name": {"value": "Client SA"},
        "total_ht": {"value": 1000.0},
        "total_vat": {"value": 200.0},
        "total_ttc": {"value": 1200.0},
        "tax_breakdown": [{"rate": 0.20, "base_ht": 1000.0, "tax_amount": 200.0}],
    }

    report = validate_invoice_extraction(
        fields=fields,
        doc_type="purchase_invoice",
        period_start=datetime.date(2026, 3, 1),
        period_end=datetime.date(2026, 3, 31),
    )

    assert any(i.code == "PERIOD_MISMATCH" and i.severity == "review" for i in report.issues)

