"""Phase 2 evaluation benchmark test: 300 Moroccan bookkeeping documents.

Exit criterion:
- On the fixture set of 300 documents, field-level accuracy report generated.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from avenel.extraction.benchmark import (
    generate_accuracy_markdown_report,
    run_benchmark,
)
from tests.fixtures.documents_300 import generate_300_fixtures


def test_300_document_field_level_accuracy_benchmark():
    """Evaluates the 300 document fixture suite and generates the Phase 2 report."""
    fixtures = generate_300_fixtures()
    assert len(fixtures) == 300, f"Expected exactly 300 fixtures, got {len(fixtures)}"

    results = run_benchmark(fixtures)

    # Verify overall performance
    macro_f1 = results["overall_macro_f1"]
    assert macro_f1 >= 0.90, f"Macro F1 {macro_f1} is below target 0.90"

    field_metrics = results["field_metrics"]
    assert field_metrics["invoice_number"]["f1"] >= 0.95
    assert field_metrics["supplier_ice"]["f1"] >= 0.95
    assert field_metrics["total_ttc"]["f1"] >= 0.95
    assert field_metrics["total_ht"]["f1"] >= 0.95

    # Generate and persist the Markdown report
    report_md = generate_accuracy_markdown_report(results)
    report_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "phase-2-accuracy-report.md"
    report_path.write_text(report_md, encoding="utf-8")

    assert report_path.exists(), "Benchmark accuracy report must be generated and persisted"

