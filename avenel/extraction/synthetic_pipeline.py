"""Synthetic pipeline evaluation test for Moroccan bookkeeping document extraction.

Runs synthetic documents through raster page rendering, image perturbations
(skew, Gaussian sensor noise, JPEG compression), and local OCR (RapidOCR / PaddleOCR ONNX PP-OCRv4 v1.4.4).
Evaluates per-field exact-match accuracy against Part H gates.
"""

from __future__ import annotations

import datetime
import io
import random
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from avenel.extraction.classifier import classify_document_text
from avenel.extraction.extractor import extract_fields_from_ocr
from avenel.ocr.adapter import ENGINE_NAME, ENGINE_VERSION, get_ocr_engine
from tests.fixtures.documents_300 import DocumentFixture, generate_300_fixtures


def _perturb_page_image(
    img: Image.Image,
    skew_angle: float | None = None,
    noise_std: float = 6.0,
    jpeg_quality: int = 70,
) -> Image.Image:
    """Applies realistic scanner perturbations: skew rotation, Gaussian noise, and lossy JPEG compression."""
    if skew_angle is None:
        skew_angle = random.uniform(-1.0, 1.0)

    # 1. Skew rotation with bilinear interpolation and white background
    rotated = img.rotate(skew_angle, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(255, 255, 255))

    # 2. Gaussian sensor noise
    arr = np.array(rotated, dtype=np.float32)
    noise = np.random.normal(0, noise_std, arr.shape)
    noisy_arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

    # 3. Lossy JPEG compression
    buf = io.BytesIO()
    Image.fromarray(noisy_arr).save(buf, format="JPEG", quality=jpeg_quality)
    buf.seek(0)
    return Image.open(buf)


def _render_fixture_to_image(fixture: DocumentFixture, width: int = 700, height: int = 950) -> Image.Image:
    """Renders fixture content into an image canvas representing a scanned document page."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    text = fixture.raw_content.decode("utf-8", errors="ignore")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    y = 50
    for line in lines:
        draw.text((40, y), line, fill=(10, 10, 10))
        y += 28

    return img


def run_synthetic_pipeline_test(
    fixtures: list[DocumentFixture] | None = None,
    sample_size: int | None = None,
    perturb: bool = True,
) -> dict[str, Any]:
    """Runs the synthetic pipeline test over rendered page images through real local OCR.
    
    Computes per-field exact-match only against Part H gates.
    """
    if fixtures is None:
        fixtures = generate_300_fixtures()

    if sample_size is not None and sample_size < len(fixtures):
        # Deterministic sample
        fixtures = fixtures[:sample_size]

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

    stats: dict[str, dict[str, int]] = {
        f: {"total": 0, "exact_match": 0, "failures": 0} for f in evaluated_fields
    }

    composite_id_date_matches = 0
    composite_totals_matches = 0
    failure_samples: list[dict[str, Any]] = []

    for fix in fixtures:
        # 1. Render to page image and apply perturbations
        page_img = _render_fixture_to_image(fix)
        if perturb:
            page_img = _perturb_page_image(page_img)

        # 2. Local OCR execution on image raster
        img_arr = np.array(page_img)
        ocr_res = ocr_engine.process(data=b"", mime_type="image/jpeg", page_count=1)
        # Process image directly through RapidOCR
        rapid = ocr_engine._get_ocr()
        if rapid:
            try:
                res, _ = rapid(img_arr)
                if res:
                    ocr_res = ocr_engine.process(data=b"", mime_type="image/jpeg", page_count=1)
                    # Reconstruct OcrResult from direct array call
                    lines = []
                    words = []
                    w_w, h_h = page_img.size
                    for item in res:
                        pts, text_val, score = item
                        t_str = str(text_val).strip()
                        if not t_str:
                            continue
                        min_x = max(0.0, min(float(p[0]) for p in pts))
                        min_y = max(0.0, min(float(p[1]) for p in pts))
                        max_x = min(float(w_w), max(float(p[0]) for p in pts))
                        max_y = min(float(h_h), max(float(p[1]) for p in pts))
                        bx = [round(min_x / w_w, 4), round(min_y / h_h, 4), round(max_x / w_w, 4), round(max_y / h_h, 4)]
                        from avenel.ocr.adapter import OcrLine, OcrWord
                        w_objs = [OcrWord(text=w, confidence=round(float(score), 4), page=1, bbox=bx) for w in t_str.split()]
                        words.extend(w_objs)
                        lines.append(OcrLine(text=t_str, confidence=round(float(score), 4), page=1, bbox=bx, words=w_objs))
                    from avenel.ocr.adapter import OcrResult
                    ocr_res = OcrResult(
                        full_text="\n".join(l.text for l in lines),
                        page_count=1,
                        lines=lines,
                        words=words,
                        engine=ENGINE_NAME,
                        engine_version=ENGINE_VERSION,
                    )
            except (ValueError, RuntimeError, OSError):
                pass

        # 3. Classifier
        classification = classify_document_text(ocr_res.full_text)
        predicted_doc_type = classification["doc_type"]

        # 4. Extractor
        extracted_fields = extract_fields_from_ocr(ocr_res, doc_type=predicted_doc_type)

        # Field comparisons
        gt = fix.ground_truth
        pred_ice = extracted_fields["supplier_ice"]["value"]
        pred_no = extracted_fields["invoice_number"]["value"]
        pred_date = extracted_fields["invoice_date"]["value"]
        pred_if = extracted_fields["supplier_if"]["value"]
        pred_ht = extracted_fields["total_ht"]["value"]
        pred_vat = extracted_fields["total_vat"]["value"]
        pred_ttc = extracted_fields["total_ttc"]["value"]

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

        checks = {
            "supplier_ice": ice_ok,
            "invoice_number": no_ok,
            "invoice_date": date_ok,
            "supplier_if": if_ok,
            "total_ht": ht_ok,
            "total_vat": vat_ok,
            "total_ttc": ttc_ok,
        }

        doc_has_failure = False
        for f, ok in checks.items():
            stats[f]["total"] += 1
            if ok:
                stats[f]["exact_match"] += 1
            else:
                stats[f]["failures"] += 1
                doc_has_failure = True

        if doc_has_failure and len(failure_samples) < 5:
            failure_samples.append({
                "doc_id": fix.doc_id,
                "category": fix.category,
                "failures": {
                    f: {"gt": gt.get(f), "extracted": extracted_fields.get(f, {}).get("value")}
                    for f, ok in checks.items() if not ok
                },
            })

        if ice_ok and no_ok and date_ok:
            composite_id_date_matches += 1

        if ht_ok and vat_ok and ttc_ok:
            composite_totals_matches += 1

    total_fixtures = len(fixtures)
    per_field_rates = {}
    for f in evaluated_fields:
        tot = stats[f]["total"]
        em = stats[f]["exact_match"]
        rate = em / tot if tot > 0 else 0.0
        per_field_rates[f] = {
            "total": tot,
            "exact_match": em,
            "failures": stats[f]["failures"],
            "rate": round(rate, 4),
        }

    id_date_rate = composite_id_date_matches / total_fixtures if total_fixtures > 0 else 0.0
    totals_rate = composite_totals_matches / total_fixtures if total_fixtures > 0 else 0.0

    return {
        "fixture_count": total_fixtures,
        "ocr_engine": ENGINE_NAME,
        "ocr_engine_version": ENGINE_VERSION,
        "perturbations": "skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70",
        "per_field": per_field_rates,
        "part_h_gates": {
            "ice_no_date_exact_match": {
                "target": 0.97,
                "achieved": round(id_date_rate, 4),
                "met": id_date_rate >= 0.97,
            },
            "totals_exact_match": {
                "target": 0.98,
                "achieved": round(totals_rate, 4),
                "met": totals_rate >= 0.98,
            },
        },
        "failure_samples": failure_samples,
    }


def generate_synthetic_pipeline_markdown_report(results: dict[str, Any]) -> str:
    """Renders the synthetic pipeline test report in clean Markdown without prohibited words."""
    res = results
    pf = res["per_field"]
    gates = res["part_h_gates"]

    lines = [
        "# Rapport de test du pipeline synthétique (Phase 2)",
        "",
        f"**Date du test** : {datetime.date.today().isoformat()}",
        f"**Nombre de documents synthétiques évalués** : {res['fixture_count']}",
        f"**Moteur OCR** : {res['ocr_engine']} v{res['ocr_engine_version']}",
        f"**Perturbations appliquées** : {res['perturbations']}",
        "",
        "> [!NOTE]",
        "> Ce test évalue la robustesse de la chaîne d'extraction sur des images raster générées et bruitées.",
        "> Conformément à ARCHITECTURE.md Part H, les portails de validation du pilote sont mesurés",
        "> exclusivement sur le jeu de données réelles (≥ 300 pièces). Ce test synthétique valide le pipeline",
        "> mais ne constitue pas la validation finale du pilote.",
        "",
        "## 1. Taux d'exactitude stricte par champ (Exact-Match)",
        "",
        "| Champ fiscal | Total évalué | Exact-Match | Échecs | Taux d'exactitude |",
        "|---|---|---|---|---|",
        f"| `supplier_ice` (ICE Fournisseur) | {pf['supplier_ice']['total']} | {pf['supplier_ice']['exact_match']} | {pf['supplier_ice']['failures']} | {pf['supplier_ice']['rate']:.2%} |",
        f"| `invoice_number` (Numéro facture) | {pf['invoice_number']['total']} | {pf['invoice_number']['exact_match']} | {pf['invoice_number']['failures']} | {pf['invoice_number']['rate']:.2%} |",
        f"| `invoice_date` (Date de facture) | {pf['invoice_date']['total']} | {pf['invoice_date']['exact_match']} | {pf['invoice_date']['failures']} | {pf['invoice_date']['rate']:.2%} |",
        f"| `supplier_if` (IF Fournisseur) | {pf['supplier_if']['total']} | {pf['supplier_if']['exact_match']} | {pf['supplier_if']['failures']} | {pf['supplier_if']['rate']:.2%} |",
        f"| `total_ht` (Total Hors Taxe) | {pf['total_ht']['total']} | {pf['total_ht']['exact_match']} | {pf['total_ht']['failures']} | {pf['total_ht']['rate']:.2%} |",
        f"| `total_vat` (Total TVA) | {pf['total_vat']['total']} | {pf['total_vat']['exact_match']} | {pf['total_vat']['failures']} | {pf['total_vat']['rate']:.2%} |",
        f"| `total_ttc` (Total TTC) | {pf['total_ttc']['total']} | {pf['total_ttc']['exact_match']} | {pf['total_ttc']['failures']} | {pf['total_ttc']['rate']:.2%} |",
        "",
        "## 2. Comparaison indicative avec les seuils cibles Part H",
        "",
        "| Portail Part H | Seuil cible Part H | Résultat synthétique obtenu | Statut indicatif |",
        "|---|---|---|---|",
        f"| ICE, invoice number, date exact match | ≥ 97,0% | {gates['ice_no_date_exact_match']['achieved']:.2%} | {'Atteint' if gates['ice_no_date_exact_match']['met'] else 'Non atteint'} |",
        f"| HT, TVA par taux, TTC exact match | ≥ 98,0% | {gates['totals_exact_match']['achieved']:.2%} | {'Atteint' if gates['totals_exact_match']['met'] else 'Non atteint'} |",
    ]

    if res.get("failure_samples"):
        lines.extend([
            "",
            "## 3. Analyse des échecs d'extraction sous bruit OCR",
            "",
            "Exemples d'écarts observés lors du test sur images perturbées :",
            "",
        ])
        for sample in res["failure_samples"]:
            lines.append(f"- **Pièce `{sample['doc_id']}`** ({sample['category']}) :")
            for f_name, f_diff in sample["failures"].items():
                lines.append(f"  - `{f_name}` : attendu `{f_diff['gt']}`, extrait `{f_diff['extracted']}`")

    return "\n".join(lines)
