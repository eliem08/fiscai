"""Synthetic pipeline evaluation test: Moroccan bookkeeping document extraction.

Tests extraction on rendered page images with perturbations (noise, skew, JPEG compression)
using local OCR (RapidOCR / PaddleOCR ONNX PP-OCRv4 v1.4.4).
Reports per-field exact match only against Part H gates.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from avenel.extraction.synthetic_pipeline import (
    format_synthetic_pipeline_report,
    generate_synthetic_pipeline_markdown_report,
    get_default_synthetic_set,
    run_synthetic_pipeline_test,
)
from avenel.extraction.validation import validate_invoice_extraction
from tests.fixtures.documents_300 import generate_300_fixtures


def test_synthetic_corpus_count_and_report_header_reconciliation():
    """Asserts that corpus counts in fixture generator match the default synthetic set and report header."""
    corpus = get_default_synthetic_set()
    fr_count = len([f for f in corpus if f.language == "fr"])
    ar_count = len([f for f in corpus if f.language == "ar"])
    mixed_count = len([f for f in corpus if f.language == "mixed"])

    assert len(corpus) == 60, f"Expected 60 total fixtures (30 FR + 10 AR + 20 Mixed), got {len(corpus)}"
    assert fr_count == 30, f"Expected 30 FR fixtures, got {fr_count}"
    assert ar_count == 10, f"Expected 10 AR fixtures, got {ar_count}"
    assert mixed_count == 20, f"Expected 20 Mixed fixtures, got {mixed_count}"

    # Generate sample results dict to format report header
    mock_results = {
        "fixture_count": len(corpus),
        "composition": {"fr": fr_count, "ar": ar_count, "mixed": mixed_count},
        "ocr_engine": "RapidOCR / PaddleOCR ONNX PP-OCRv4",
        "ocr_engine_version": "1.4.4",
        "perturbations": "skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70",
        "per_field": {
            "supplier_ice": {"total": 60, "exact_match": 59, "failures": 1, "caught": 1, "silent": 0},
            "invoice_number": {"total": 60, "exact_match": 60, "failures": 0, "caught": 0, "silent": 0},
            "invoice_date": {"total": 60, "exact_match": 60, "failures": 0, "caught": 0, "silent": 0},
            "supplier_if": {"total": 60, "exact_match": 58, "failures": 2, "caught": 2, "silent": 0},
            "total_ht": {"total": 60, "exact_match": 59, "failures": 1, "caught": 1, "silent": 0},
            "total_vat": {"total": 60, "exact_match": 60, "failures": 0, "caught": 0, "silent": 0},
            "total_ttc": {"total": 60, "exact_match": 59, "failures": 1, "caught": 1, "silent": 0},
        },
        "per_language": {
            "fr": {"supplier_ice": 1.0, "total_ttc": 1.0},
            "ar": {"supplier_ice": 0.9, "total_ttc": 1.0},
            "mixed": {"supplier_ice": 1.0, "total_ttc": 0.95},
        },
        "part_h_gates": {
            "ice_no_date_exact_match": {"target": 0.97, "achieved": 0.9833, "met": True},
            "totals_exact_match": {"target": 0.98, "achieved": 0.9833, "met": True},
            "totals_silent_error_rate": {"target": 0.0, "achieved": 0.0, "met": True},
        },
        "failure_samples": [],
    }

    report = format_synthetic_pipeline_report(mock_results)

    # Assert exact header matching
    assert "**Taille du corpus synthétique :** **60 documents**" in report
    assert "**Composition du corpus :** **30 factures Français (FR)**, **10 factures Arabe (AR, synthetic, clean rendering)**, **20 factures Bilingues/Mixtes (FR/AR)**" in report
    assert "| Champ extrait | Français (FR - 30 docs) | Arabe (AR - 10 docs, synthetic, clean rendering) | Bilingue / Mixte (FR/AR - 20 docs) |" in report
    assert "| **Erreurs silencieuses HT/TVA/TTC** | Silent Error Rate | 0.0% | **0.00%** | Atteint |" in report
    assert "## 4. Taux d'Erreurs Silencieuses (Silent Error Rate)" in report
    assert "Conforme" not in report


def test_mixed_inv_002_raises_totals_inconsistent_validator():
    """Confirms mixed_inv_002 error condition is caught by deterministic validator."""
    # When OCR incorrectly extracts HT as 17672.68 instead of 7672.68:
    mock_extracted = {
        "invoice_number": {"value": "FA-2026-0042", "confidence": 0.98, "confirmed": True},
        "invoice_date": {"value": "2026-02-14", "confidence": 0.98, "confirmed": True},
        "supplier_ice": {"value": "001234567000085", "confidence": 0.98, "confirmed": True},
        "supplier_if": {"value": "12345678", "confidence": 0.98, "confirmed": True},
        "total_ht": {"value": 17672.68, "confidence": 0.95, "confirmed": True},  # Wrong amount under noise
        "total_vat": {"value": 1534.54, "confidence": 0.95, "confirmed": True},
        "total_ttc": {"value": 9207.22, "confidence": 0.95, "confirmed": True},
    }
    report = validate_invoice_extraction(mock_extracted, doc_type="invoice_purchase")
    issue_codes = {issue.code for issue in report.issues}

    assert "TOTALS_INCONSISTENT" in issue_codes, "Validator must flag arithmetic inconsistency as TOTALS_INCONSISTENT"
    assert not report.is_valid, "Validation report must mark document invalid when totals do not balance"


def test_synthetic_pipeline_per_field_exact_match():
    """Runs synthetic pipeline test over rendered page images through real local OCR."""
    fixtures = generate_300_fixtures()
    assert len(fixtures) == 300, f"Expected exactly 300 fixtures, got {len(fixtures)}"

    # In fast test suite, evaluate on a fast representative subset (or full if env set)
    sample_size = 300 if os.environ.get("FULL_SYNTHETIC_RUN") == "1" else 5
    results = run_synthetic_pipeline_test(fixtures, sample_size=sample_size, perturb=True)

    assert results["fixture_count"] == sample_size
    assert "RapidOCR / PaddleOCR ONNX PP-OCRv4" in results["ocr_engine"]
    assert results["ocr_engine_version"] == "1.4.4"

    # Per-field exact match metrics
    pf = results["per_field"]
    assert "invoice_number" in pf
    assert "invoice_date" in pf
    assert "supplier_ice" in pf
    assert "total_ht" in pf
    assert "total_vat" in pf
    assert "total_ttc" in pf

    # Verify report generation without prohibited words
    report_md = generate_synthetic_pipeline_markdown_report(results)
    assert "Conforme" not in report_md, "Word 'Conforme' is strictly prohibited"
    assert "Macro F1" not in report_md, "Macro F1 metric must be removed"

    report_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "synthetic-pipeline-test.md"
    report_path.write_text(report_md, encoding="utf-8")

    assert report_path.exists(), "Synthetic pipeline test report must be generated and persisted"

