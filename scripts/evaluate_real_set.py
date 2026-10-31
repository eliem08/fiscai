#!/usr/bin/env python3
"""Evaluation harness for real labelled document set against ARCHITECTURE.md Part H gates.

Strictly adheres to:
1. Exact-match per field reporting only (no macro F1, no unapproved thresholds).
2. Gates evaluated against Part H targets (ICE/number/date >= 97%, totals >= 98%).
3. Real local OCR (RapidOCR / PaddleOCR ONNX PP-OCRv4 v1.4.4).
4. No use of the word "Conforme" in any output or report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import jsonschema  # type: ignore[import-untyped]

from avenel.extraction.classifier import classify_document_text
from avenel.extraction.extractor import extract_fields_from_ocr
from avenel.ocr.adapter import ENGINE_NAME, ENGINE_VERSION, get_ocr_engine

REAL_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "real"
LABELS_SCHEMA_PATH = REAL_FIXTURES_DIR / "labels.schema.json"


def load_and_validate_labels(labels_file: Path, schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Loads and validates labels.jsonl against schema."""
    entries: list[dict[str, Any]] = []
    with open(labels_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                record = json.loads(line_str)
                jsonschema.validate(instance=record, schema=schema)
                entries.append(record)
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                raise ValueError(f"Invalid label at line {line_num} in {labels_file}: {e}") from e
    return entries


def evaluate_dataset(
    records: list[dict[str, Any]],
    docs_dir: Path,
) -> dict[str, Any]:
    """Runs extraction pipeline over real documents and computes Part H per-field exact match."""
    ocr_engine = get_ocr_engine()

    evaluated_fields = [
        "invoice_number",
        "invoice_date",
        "supplier_ice",
        "supplier_if",
        "total_ht",
        "total_vat",
        "total_ttc",
    ]

    field_counts = {f: {"total": 0, "exact_match": 0, "failures": 0} for f in evaluated_fields}
    composite_id_date_matches = 0
    composite_totals_matches = 0
    total_docs = len(records)

    for item in records:
        _doc_id = item["document_id"]
        rel_path = item["file_path"]
        mime_type = item["mime_type"]
        gt = item["ground_truth"]

        file_path = docs_dir / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"Real document file not found: {file_path}")

        raw_data = file_path.read_bytes()

        # 1. OCR execution
        ocr_res = ocr_engine.process(raw_data, mime_type=mime_type)

        # 2. Classifier
        classification = classify_document_text(ocr_res.full_text)
        predicted_doc_type = classification["doc_type"]

        # 3. Extractor
        extracted_fields = extract_fields_from_ocr(ocr_res, doc_type=predicted_doc_type)

        pred_ice = extracted_fields["supplier_ice"]["value"]
        pred_no = extracted_fields["invoice_number"]["value"]
        pred_date = extracted_fields["invoice_date"]["value"]
        pred_if = extracted_fields["supplier_if"]["value"]
        pred_ht = extracted_fields["total_ht"]["value"]
        pred_vat = extracted_fields["total_vat"]["value"]
        pred_ttc = extracted_fields["total_ttc"]["value"]

        # Field exact-match checks
        def is_exact(gt_val: Any, pred_val: Any, is_amount: bool = False) -> bool:
            if gt_val is None and pred_val is None:
                return True
            if gt_val is None or pred_val is None:
                return False
            if is_amount:
                try:
                    return abs(float(gt_val) - float(pred_val)) <= 0.01
                except (ValueError, TypeError):
                    return False
            return str(gt_val).strip() == str(pred_val).strip()

        ice_ok = is_exact(gt.get("supplier_ice"), pred_ice)
        no_ok = is_exact(gt.get("invoice_number"), pred_no)
        date_ok = is_exact(gt.get("invoice_date"), pred_date)
        if_ok = is_exact(gt.get("supplier_if"), pred_if)
        ht_ok = is_exact(gt.get("total_ht"), pred_ht, is_amount=True)
        vat_ok = is_exact(gt.get("total_vat"), pred_vat, is_amount=True)
        ttc_ok = is_exact(gt.get("total_ttc"), pred_ttc, is_amount=True)

        for f, ok in [
            ("supplier_ice", ice_ok),
            ("invoice_number", no_ok),
            ("invoice_date", date_ok),
            ("supplier_if", if_ok),
            ("total_ht", ht_ok),
            ("total_vat", vat_ok),
            ("total_ttc", ttc_ok),
        ]:
            field_counts[f]["total"] += 1
            if ok:
                field_counts[f]["exact_match"] += 1
            else:
                field_counts[f]["failures"] += 1

        # Composite Part H Gates
        if ice_ok and no_ok and date_ok:
            composite_id_date_matches += 1

        if ht_ok and vat_ok and ttc_ok:
            composite_totals_matches += 1

    per_field_rates = {}
    for f in evaluated_fields:
        tot = field_counts[f]["total"]
        em = field_counts[f]["exact_match"]
        rate = em / tot if tot > 0 else 0.0
        per_field_rates[f] = {
            "total": tot,
            "exact_match": em,
            "failures": field_counts[f]["failures"],
            "rate": round(rate, 4),
        }

    gate_id_date_rate = composite_id_date_matches / total_docs if total_docs > 0 else 0.0
    gate_totals_rate = composite_totals_matches / total_docs if total_docs > 0 else 0.0

    return {
        "total_documents": total_docs,
        "ocr_engine": ENGINE_NAME,
        "ocr_engine_version": ENGINE_VERSION,
        "per_field": per_field_rates,
        "part_h_gates": {
            "ice_no_date_exact_match": {
                "target": 0.97,
                "achieved": round(gate_id_date_rate, 4),
                "met": gate_id_date_rate >= 0.97,
            },
            "totals_exact_match": {
                "target": 0.98,
                "achieved": round(gate_totals_rate, 4),
                "met": gate_totals_rate >= 0.98,
            },
        },
    }


def generate_real_set_markdown_report(results: dict[str, Any]) -> str:
    """Generates the Part H evaluation report without prohibited words."""
    res = results
    pf = res["per_field"]
    gates = res["part_h_gates"]

    lines = [
        "# Rapport d'évaluation sur jeu de données réelles (Part H)",
        "",
        f"**Nombre de documents réels évalués** : {res['total_documents']}",
        f"**Moteur OCR** : {res['ocr_engine']} v{res['ocr_engine_version']}",
        "",
        "## 1. Taux d'exactitude stricte par champ (Exact-Match)",
        "",
        "| Champ fiscal | Total | Exact-Match | Échecs / Non-reconnus | Taux d'exactitude |",
        "|---|---|---|---|---|",
        f"| `supplier_ice` (ICE Fournisseur) | {pf['supplier_ice']['total']} | {pf['supplier_ice']['exact_match']} | {pf['supplier_ice']['failures']} | {pf['supplier_ice']['rate']:.2%} |",
        f"| `invoice_number` (Numéro facture) | {pf['invoice_number']['total']} | {pf['invoice_number']['exact_match']} | {pf['invoice_number']['failures']} | {pf['invoice_number']['rate']:.2%} |",
        f"| `invoice_date` (Date de pièce) | {pf['invoice_date']['total']} | {pf['invoice_date']['exact_match']} | {pf['invoice_date']['failures']} | {pf['invoice_date']['rate']:.2%} |",
        f"| `supplier_if` (IF Fournisseur) | {pf['supplier_if']['total']} | {pf['supplier_if']['exact_match']} | {pf['supplier_if']['failures']} | {pf['supplier_if']['rate']:.2%} |",
        f"| `total_ht` (Total Hors Taxe) | {pf['total_ht']['total']} | {pf['total_ht']['exact_match']} | {pf['total_ht']['failures']} | {pf['total_ht']['rate']:.2%} |",
        f"| `total_vat` (Total TVA) | {pf['total_vat']['total']} | {pf['total_vat']['exact_match']} | {pf['total_vat']['failures']} | {pf['total_vat']['rate']:.2%} |",
        f"| `total_ttc` (Total TTC) | {pf['total_ttc']['total']} | {pf['total_ttc']['exact_match']} | {pf['total_ttc']['failures']} | {pf['total_ttc']['rate']:.2%} |",
        "",
        "## 2. Portails de validation Part H (Gates)",
        "",
        "| Portail Part H | Seuil cible | Résultat obtenu | Statut |",
        "|---|---|---|---|",
        f"| ICE, invoice number, date exact match | ≥ 97,0% | {gates['ice_no_date_exact_match']['achieved']:.2%} | {'Validé' if gates['ice_no_date_exact_match']['met'] else 'Non atteint'} |",
        f"| HT, TVA par taux, TTC exact match | ≥ 98,0% | {gates['totals_exact_match']['achieved']:.2%} | {'Validé' if gates['totals_exact_match']['met'] else 'Non atteint'} |",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate real labelled document set against Part H gates")
    parser.add_argument("--labels-file", type=Path, default=REAL_FIXTURES_DIR / "labels.jsonl")
    parser.add_argument("--docs-dir", type=Path, default=REAL_FIXTURES_DIR)
    parser.add_argument("--output-report", type=Path, default=None)
    args = parser.parse_args()

    if not LABELS_SCHEMA_PATH.exists():
        print(f"Error: Schema file missing at {LABELS_SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)

    schema = json.loads(LABELS_SCHEMA_PATH.read_text(encoding="utf-8"))

    if not args.labels_file.exists():
        print(
            f"Note: Labels file not found at {args.labels_file}.\n"
            "Per ARCHITECTURE.md Part H, Part H gates cannot be claimed until >=300 real documents are evaluated.\n"
            "The harness is ready. Place decrypted real documents and labels.jsonl in tests/fixtures/real/ to evaluate.",
            file=sys.stderr,
        )
        sys.exit(0)

    records = load_and_validate_labels(args.labels_file, schema)
    if not records:
        print("Note: labels.jsonl is empty. Part H gates remain unverified until real documents are evaluated.")
        sys.exit(0)

    print(f"Loaded {len(records)} verified label records. Running evaluation with {ENGINE_NAME} v{ENGINE_VERSION}...")
    results = evaluate_dataset(records, args.docs_dir)
    report_md = generate_real_set_markdown_report(results)

    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(report_md, encoding="utf-8")
        print(f"Report written to {args.output_report}")
    else:
        print("\n" + report_md)


if __name__ == "__main__":
    main()
