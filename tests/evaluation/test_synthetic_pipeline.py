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
    generate_synthetic_pipeline_markdown_report,
    run_synthetic_pipeline_test,
)
from tests.fixtures.documents_300 import generate_300_fixtures


def test_synthetic_pipeline_per_field_exact_match():
    """Runs synthetic pipeline test over rendered page images through real local OCR."""
    fixtures = generate_300_fixtures()
    assert len(fixtures) == 300, f"Expected exactly 300 fixtures, got {len(fixtures)}"

    # In fast test suite, evaluate on a representative subset of 30 documents (or full if env set)
    sample_size = 300 if os.environ.get("FULL_SYNTHETIC_RUN") == "1" else 30
    results = run_synthetic_pipeline_test(fixtures, sample_size=sample_size, perturb=True)

    assert results["fixture_count"] == sample_size
    assert results["ocr_engine"] == "RapidOCR / PaddleOCR ONNX PP-OCRv4"
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
