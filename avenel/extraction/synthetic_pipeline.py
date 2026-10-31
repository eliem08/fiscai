"""Synthetic pipeline evaluation test for Moroccan bookkeeping document extraction.

Runs synthetic documents through raster page rendering, image perturbations
(skew ±1.0°, Gaussian sensor noise σ=6.0, lossy JPEG compression Q=70),
and local OCR (RapidOCR / PaddleOCR ONNX PP-OCRv4 + Multilingual v3).
Evaluates per-field and per-language exact-match accuracy against Part H gates.
"""

from __future__ import annotations

import datetime
import io
import os
import random
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from avenel.extraction.classifier import classify_document_text
from avenel.extraction.extractor import extract_fields_from_ocr
from avenel.ocr.adapter import ENGINE_NAME, ENGINE_VERSION, get_ocr_engine
from tests.fixtures.documents_300 import DocumentFixture, generate_300_fixtures


def _get_font(size: int = 18) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidate_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except (OSError, RuntimeError):
                pass
    try:
        return ImageFont.load_default()
    except (OSError, RuntimeError):
        return None  # type: ignore[return-value]


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


def _render_fixture_to_image(fixture: DocumentFixture, width: int = 800, height: int = 1100) -> Image.Image:
    """Renders fixture content into an image canvas representing a scanned document page."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _get_font(18)

    text = fixture.raw_content.decode("utf-8", errors="ignore")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    y = 50
    for line in lines:
        if font:
            draw.text((40, y), line, fill=(10, 10, 10), font=font)
        else:
            draw.text((40, y), line, fill=(10, 10, 10))
        y += 30
    return img


def get_default_synthetic_set() -> list[DocumentFixture]:
    """Builds the 45-document synthetic test corpus: 30 French, 10 Arabic, 5 Mixed FR/AR."""
    all_300 = generate_300_fixtures()
    fr_docs = [f for f in all_300 if f.language == "fr"][:30]
    ar_docs = [f for f in all_300 if f.language == "ar"][:10]
    mixed_docs = [f for f in all_300 if f.language == "mixed"][:5]
    return fr_docs + ar_docs + mixed_docs


def run_synthetic_pipeline_test(
    fixtures: list[DocumentFixture] | None = None,
    sample_size: int | None = None,
    perturb: bool = True,
) -> dict[str, Any]:
    """Runs the synthetic pipeline test over rendered page images through real local OCR.

    Computes per-field exact-match and per-language stats against Part H gates.
    """
    if fixtures is None:
        fixtures = get_default_synthetic_set()

    if sample_size is not None:
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

    languages = ["fr", "ar", "mixed"]
    stats_overall: dict[str, dict[str, int]] = {
        f: {"total": 0, "exact_match": 0, "failures": 0} for f in evaluated_fields
    }
    stats_by_lang: dict[str, dict[str, dict[str, int]]] = {
        lang: {f: {"total": 0, "exact_match": 0, "failures": 0} for f in evaluated_fields}
        for lang in languages
    }

    doc_counts_by_lang: dict[str, int] = {lang: 0 for lang in languages}

    composite_id_date_matches = 0
    composite_totals_matches = 0
    failure_samples: list[dict[str, Any]] = []

    for fix in fixtures:
        doc_lang = fix.language if fix.language in stats_by_lang else "fr"
        doc_counts_by_lang[doc_lang] = doc_counts_by_lang.get(doc_lang, 0) + 1

        # 1. Render to page image and apply perturbations
        page_img = _render_fixture_to_image(fix)
        if perturb:
            page_img = _perturb_page_image(page_img)

        # 2. Local OCR execution on image bytes with script detection and multi-model recognition
        buf = io.BytesIO()
        page_img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        ocr_res = ocr_engine.process(data=jpeg_bytes, mime_type="image/jpeg", page_count=1)

        # 3. Classifier
        classification = classify_document_text(ocr_res.full_text)
        doc_type_val = str(classification.get("doc_type", "purchase_invoice"))

        # 4. Extractor
        extracted_fields = extract_fields_from_ocr(ocr_res, doc_type=doc_type_val)

        # 5. Field comparisons
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
            stats_overall[f]["total"] += 1
            stats_by_lang[doc_lang][f]["total"] += 1
            if ok:
                stats_overall[f]["exact_match"] += 1
                stats_by_lang[doc_lang][f]["exact_match"] += 1
            else:
                stats_overall[f]["failures"] += 1
                stats_by_lang[doc_lang][f]["failures"] += 1
                doc_has_failure = True

        if doc_has_failure and len(failure_samples) < 8:
            failure_samples.append({
                "doc_id": fix.doc_id,
                "language": doc_lang,
                "category": fix.category,
                "failures": {
                    f: {"gt": gt.get(f), "extracted": extracted_fields.get(f, {}).get("value")}
                    for f, ok in checks.items()
                    if not ok
                },
            })

        if ice_ok and no_ok and date_ok:
            composite_id_date_matches += 1

        if ht_ok and vat_ok and ttc_ok:
            composite_totals_matches += 1

    total_fixtures = len(fixtures)
    per_field_rates = {}
    for f in evaluated_fields:
        tot = stats_overall[f]["total"]
        em = stats_overall[f]["exact_match"]
        rate = em / tot if tot > 0 else 0.0
        per_field_rates[f] = {
            "total": tot,
            "exact_match": em,
            "failures": stats_overall[f]["failures"],
            "rate": round(rate, 4),
        }

    # Per language rates
    per_language_rates: dict[str, dict[str, float]] = {}
    for lang in languages:
        l_dict = {}
        for f in evaluated_fields:
            l_tot = stats_by_lang[lang][f]["total"]
            l_em = stats_by_lang[lang][f]["exact_match"]
            l_dict[f] = round(l_em / l_tot if l_tot > 0 else 0.0, 4)
        per_language_rates[lang] = l_dict

    id_date_rate = composite_id_date_matches / total_fixtures if total_fixtures > 0 else 0.0
    totals_rate = composite_totals_matches / total_fixtures if total_fixtures > 0 else 0.0

    return {
        "fixture_count": total_fixtures,
        "composition": {
            "fr": doc_counts_by_lang.get("fr", 0),
            "ar": doc_counts_by_lang.get("ar", 0),
            "mixed": doc_counts_by_lang.get("mixed", 0),
        },
        "ocr_engine": ENGINE_NAME,
        "ocr_engine_version": ENGINE_VERSION,
        "perturbations": "skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70",
        "per_field": per_field_rates,
        "per_language": per_language_rates,
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


def format_synthetic_pipeline_report(results: dict[str, Any]) -> str:
    """Formats synthetic pipeline evaluation report as clean markdown per Part H specifications."""
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    comp = results["composition"]

    lines = [
        "# Rapport de Test du Pipeline Synthétique — Ingestion & Extraction",
        "",
        f"**Date d'exécution :** {timestamp}",
        f"**Moteur OCR :** `{results['ocr_engine']}` (version `{results['ocr_engine_version']}`)",
        "**Modèles de reconnaissance :** ONNX Latin & Arabe multilingues (ancrés par checksums SHA-256)",
        f"**Taille du corpus synthétique :** **{results['fixture_count']} documents**",
        f"**Composition du corpus :** **{comp['fr']} factures Français (FR)**, **{comp['ar']} factures Arabe (AR)**, **{comp['mixed']} factures Bilingues/Mixtes (FR/AR)**",
        f"**Perturbations appliquées aux images :** {results['perturbations']}",
        "",
        "> [!IMPORTANT]",
        "> Ce test évalue la robustesse de l'extraction sur des images synthétiques dégradées par bruit et compression.",
        "> Conformément à la Partie H d'ARCHITECTURE.md, les portes cibles officielles ne sont validées",
        "> que sur le corpus de test réel labellisé (tests/fixtures/real/).",
        "",
        "## 1. Résultats Exact Match par Champ (Ensemble du Corpus)",
        "",
        "| Champ extrait | Total | Exact Match | Échecs | Taux Exact Match | Seuil Cible Partie H |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for field, data in results["per_field"].items():
        score_pct = f"{data['exact_match'] / data['total'] * 100:.2f}%" if data["total"] > 0 else "0.00%"
        target_str = ">= 97.0%" if field in ("supplier_ice", "invoice_number", "invoice_date") else (
            ">= 98.0%" if field in ("total_ht", "total_vat", "total_ttc") else "—"
        )
        lines.append(
            f"| `{field}` | {data['total']} | {data['exact_match']} | {data['failures']} | **{score_pct}** | {target_str} |"
        )

    lines.extend([
        "",
        "## 2. Résultats Exact Match par Langue",
        "",
        "| Champ extrait | Français (FR - 30 docs) | Arabe (AR - 10 docs) | Bilingue / Mixte (FR/AR - 5 docs) |",
        "| :--- | :---: | :---: | :---: |",
    ])

    per_lang = results.get("per_language", {})
    for field in ["invoice_number", "invoice_date", "supplier_ice", "supplier_if", "total_ht", "total_vat", "total_ttc"]:
        fr_pct = f"{per_lang.get('fr', {}).get(field, 0.0) * 100:.1f}%"
        ar_pct = f"{per_lang.get('ar', {}).get(field, 0.0) * 100:.1f}%"
        mix_pct = f"{per_lang.get('mixed', {}).get(field, 0.0) * 100:.1f}%"
        lines.append(f"| `{field}` | {fr_pct} | {ar_pct} | {mix_pct} |")

    lines.extend([
        "",
        "## 3. Évaluation face aux Portes Cibles Partie H (Pilote)",
        "",
        "| Porte Cible Partie H | Métrique | Cible Pilote | Résultat Obtenu | Statut |",
        "| :--- | :--- | :---: | :---: | :---: |",
    ])

    gates = results["part_h_gates"]
    id_date = gates["ice_no_date_exact_match"]
    id_status = "Atteint" if id_date["met"] else "Non atteint"
    id_target_pct = f"{id_date['target'] * 100:.1f}%"
    id_achieved_pct = f"{id_date['achieved'] * 100:.2f}%"
    lines.append(
        f"| **ICE, N° Facture, Date** | Exact Match | >= {id_target_pct} | **{id_achieved_pct}** | {id_status} |"
    )

    totals = gates["totals_exact_match"]
    tot_status = "Atteint" if totals["met"] else "Non atteint"
    tot_target_pct = f"{totals['target'] * 100:.1f}%"
    tot_achieved_pct = f"{totals['achieved'] * 100:.2f}%"
    lines.append(
        f"| **HT, TVA par taux, TTC** | Exact Match | >= {tot_target_pct} | **{tot_achieved_pct}** | {tot_status} |"
    )

    lines.extend([
        "",
        "## 4. Analyse Transparente des Échecs sous Bruit d'Image",
        "",
        "Détail des documents ayant présenté des écarts sous les perturbations de scan :",
        "",
    ])

    failures = results.get("failure_samples", [])
    if failures:
        for fail in failures:
            lines.append(f"- **Document `{fail['doc_id']}`** (Langue: `{fail.get('language')}`, Catégorie: `{fail['category']}`) :")
            for f, err in fail["failures"].items():
                lines.append(f"  - `{f}` : attendu `{err['gt']}`, extrait `{err['extracted']}`")
    else:
        lines.append("Aucun échec constaté sur le corpus évalué.")

    lines.append("")
    return "\n".join(lines)


generate_synthetic_pipeline_markdown_report = format_synthetic_pipeline_report

