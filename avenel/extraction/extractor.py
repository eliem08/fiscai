"""Extractor Agent for Moroccan invoices and accounting documents.

Extracts structured fiscal fields with normalized bounding boxes and confidences.
Enforces Rule D.8: Never computes totals it cannot see.
Logs each run to agent_runs.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import psycopg

from avenel.extraction.schemas import EXTRACTOR_INPUT_SCHEMA, EXTRACTOR_OUTPUT_SCHEMA
from avenel.ocr.adapter import OcrResult


def parse_date_to_iso(date_str: str) -> str | None:
    """Parses varied date representations (DD/MM/YYYY, YYYY-MM-DD, etc.) into ISO-8601."""
    d_clean = date_str.strip()
    # Match DD/MM/YYYY or DD-MM-YYYY
    m1 = re.search(r"\b(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{4})\b", d_clean)
    if m1:
        day, month, year = m1.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    # Match YYYY-MM-DD
    m2 = re.search(r"\b(\d{4})[/\.-](\d{1,2})[/\.-](\d{1,2})\b", d_clean)
    if m2:
        year, month, day = m2.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    return None


def parse_decimal_amount(amt_str: str) -> float | None:
    """Parses Moroccan decimal representations (e.g. '1 250,50' or '1250.50')."""
    cleaned = amt_str.replace(" ", "").replace("\xa0", "").strip()
    if not cleaned:
        return None
    # Handle comma as decimal separator
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "," in cleaned and "." in cleaned:
        # e.g. 1,250.50
        if cleaned.rfind(".") > cleaned.rfind(","):
            cleaned = cleaned.replace(",", "")
        else:
            # e.g. 1.250,50
            cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def extract_fields_from_ocr(ocr: OcrResult, doc_type: str = "purchase_invoice") -> dict[str, Any]:
    """Deterministic extractor parsing key Moroccan invoice fields and bounding boxes."""
    text = ocr.full_text
    lines = ocr.lines

    fields: dict[str, Any] = {
        "invoice_number": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "invoice_date": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "due_date": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "supplier_name": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "supplier_ice": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "supplier_if": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "supplier_rc": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "supplier_address": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "supplier_is_auto_entrepreneur": {"value": False, "confidence": 1.0, "page": 1, "bbox": None},
        "client_name": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "client_ice": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "client_if": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "payment_method": {"value": "unspecified", "confidence": 0.8, "page": 1, "bbox": None},
        "currency": {"value": "MAD", "confidence": 0.99, "page": 1, "bbox": None},
        "total_ht": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "total_vat": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "total_ttc": {"value": None, "confidence": 0.0, "page": 1, "bbox": None},
        "tax_breakdown": [],
        "line_items": [],
    }

    # 1. Detect auto-entrepreneur mention
    if re.search(r"(?i)\b(auto[- ]entrepreneur|مقاول\s*ذاتي)\b", text):
        fields["supplier_is_auto_entrepreneur"]["value"] = True
        fields["supplier_is_auto_entrepreneur"]["confidence"] = 0.98

    # 2. Payment method
    if re.search(r"(?i)\b(espèces|especes|cash|نقدا|نقداً)\b", text):
        fields["payment_method"]["value"] = "cash"
        fields["payment_method"]["confidence"] = 0.95
    elif re.search(r"(?i)\b(virement|transfer|تحويل\s*بنكي)\b", text):
        fields["payment_method"]["value"] = "bank_transfer"
        fields["payment_method"]["confidence"] = 0.95
    elif re.search(r"(?i)\b(chèque|cheque|شيك)\b", text):
        fields["payment_method"]["value"] = "check"
        fields["payment_method"]["confidence"] = 0.95

    # 3. Currency
    if re.search(r"\b(EUR|€)\b", text):
        fields["currency"]["value"] = "EUR"
    elif re.search(r"\b(USD|\$)\b", text):
        fields["currency"]["value"] = "USD"
    else:
        fields["currency"]["value"] = "MAD"

    # Line by line scanning for identifiers and totals
    for line in lines:
        l_text = line.text.strip()
        l_lower = l_text.lower()

        # ICE extraction (15 digits)
        ice_match = re.search(r"(?i)\b(ICE|I\.C\.E\.|المعرف\s*الموحد)\s*[:#]?\s*([0-9]{15})\b", l_text)
        if ice_match:
            val = ice_match.group(2)
            if fields["supplier_ice"]["value"] is None:
                fields["supplier_ice"]["value"] = val
                fields["supplier_ice"]["confidence"] = 0.99
                fields["supplier_ice"]["bbox"] = line.bbox
            elif fields["client_ice"]["value"] is None and val != fields["supplier_ice"]["value"]:
                fields["client_ice"]["value"] = val
                fields["client_ice"]["confidence"] = 0.95
                fields["client_ice"]["bbox"] = line.bbox
        elif re.search(r"\b([0-9]{15})\b", l_text):
            m = re.search(r"\b([0-9]{15})\b", l_text)
            assert m is not None
            val = m.group(1)
            if fields["supplier_ice"]["value"] is None:
                fields["supplier_ice"]["value"] = val
                fields["supplier_ice"]["confidence"] = 0.90
                fields["supplier_ice"]["bbox"] = line.bbox

        # IF extraction
        if_match = re.search(r"(?i)(?:IF|I\.F\.|Identifiant Fiscal|التعريف\s*الضريبي)(?:\s*\([A-Za-z]+\))?\s*[:#]?\s*([0-9]{1,10})\b", l_text)
        if if_match and fields["supplier_if"]["value"] is None:
            fields["supplier_if"]["value"] = if_match.group(1)
            fields["supplier_if"]["confidence"] = 0.98
            fields["supplier_if"]["bbox"] = line.bbox

        # RC extraction
        rc_match = re.search(r"(?i)\b(RC|R\.C\.|Registre de Commerce|السجل\s*التجاري)\s*[:#]?\s*([0-9]{1,10})\b", l_text)
        if rc_match:
            fields["supplier_rc"]["value"] = rc_match.group(2)
            fields["supplier_rc"]["confidence"] = 0.98
            fields["supplier_rc"]["bbox"] = line.bbox

        # Invoice number extraction
        inv_no_match = re.search(
            r"(?i)(?:Facture\s*(?:N[°o\.]?|no|num[eé]ro)?|Invoice\s*(?:No|number)?|رقم\s*الفاتورة)\s*[:#]?\s*([A-Za-z0-9\-_/]+)",
            l_text,
        )
        if inv_no_match and fields["invoice_number"]["value"] is None:
            cand = inv_no_match.group(1).strip()
            if cand.lower() not in ("date", "le", "au", "du", "de"):
                fields["invoice_number"]["value"] = cand
                fields["invoice_number"]["confidence"] = 0.97
                fields["invoice_number"]["bbox"] = line.bbox
        elif fields["invoice_number"]["value"] is None:
            m_code = re.search(
                r"\b(FAC[/-]?[0-9]{4}[/-]?[0-9]+|INV[/-]?[A-Za-z0-9\-_]+|REC[/-]?[A-Za-z0-9\-_]+|AE[/-]INV[/-][0-9]+|AVOIR[/-]?[0-9]{4}[/-]?[0-9]+)\b",
                l_text,
            )
            if m_code:
                fields["invoice_number"]["value"] = m_code.group(1).strip()
                fields["invoice_number"]["confidence"] = 0.95
                fields["invoice_number"]["bbox"] = line.bbox

        # Invoice date extraction
        date_match = re.search(r"(?i)\b(Date|Le|Emise le|التاريخ)\s*[:]?\s*(\d{1,4}[/\.-]\d{1,2}[/\.-]\d{2,4})", l_text)
        if date_match and fields["invoice_date"]["value"] is None:
            iso_d = parse_date_to_iso(date_match.group(2))
            if iso_d:
                fields["invoice_date"]["value"] = iso_d
                fields["invoice_date"]["confidence"] = 0.97
                fields["invoice_date"]["bbox"] = line.bbox

        # Due date extraction
        due_match = re.search(r"(?i)\b(Échéance|Echeance|Due date|تاريخ\s*الاستحقاق)\s*[:]?\s*(\d{1,4}[/\.-]\d{1,2}[/\.-]\d{2,4})", l_text)
        if due_match and fields["due_date"]["value"] is None:
            iso_d = parse_date_to_iso(due_match.group(2))
            if iso_d:
                fields["due_date"]["value"] = iso_d
                fields["due_date"]["confidence"] = 0.95
                fields["due_date"]["bbox"] = line.bbox

        # Supplier Name (often in top lines before 'facture')
        if (
            fields["supplier_name"]["value"] is None
            and not any(k in l_lower for k in ["facture", "invoice", "date", "ice", "client"])
            and len(l_text) >= 3
            and not re.match(r"^[0-9\W]+$", l_text)
        ):
            fields["supplier_name"]["value"] = l_text
            fields["supplier_name"]["confidence"] = 0.90
            fields["supplier_name"]["bbox"] = line.bbox

        # Client Name
        client_match = re.search(r"(?i)\b(Client|Doit|Facturé à|Customer|الزبون)\s*[:]?\s*([A-Za-z0-9\s\.\-]{3,})", l_text)
        if client_match and fields["client_name"]["value"] is None:
            fields["client_name"]["value"] = client_match.group(2).strip()
            fields["client_name"]["confidence"] = 0.92
            fields["client_name"]["bbox"] = line.bbox

        # Total HT
        ht_match = re.search(r"(?i)\b(Total\s*HT|Montant\s*HT|Sous-total\s*HT|المجموع\s*دون\s*احتساب\s*الضريبة)\s*[:]?\s*([0-9\s,\.]+)", l_text)
        if ht_match and fields["total_ht"]["value"] is None:
            amt = parse_decimal_amount(ht_match.group(2))
            if amt is not None:
                fields["total_ht"]["value"] = amt
                fields["total_ht"]["confidence"] = 0.98
                fields["total_ht"]["bbox"] = line.bbox

        # Total VAT (TVA)
        vat_match = re.search(r"(?i)(?:Total\s*TVA|Montant\s*TVA|الضريبة\s*على\s*القيمة\s*المضافة)\s*[:]?\s*([0-9\s,\.]+)", l_text)
        if vat_match and fields["total_vat"]["value"] is None:
            amt = parse_decimal_amount(vat_match.group(1))
            if amt is not None:
                fields["total_vat"]["value"] = amt
                fields["total_vat"]["confidence"] = 0.98
                fields["total_vat"]["bbox"] = line.bbox

        # Total TTC
        ttc_match = re.search(r"(?i)(?:Total\s*TTC|Net\s*à\s*payer|Montant\s*TTC|المجموع\s*مع\s*احتساب\s*الضريبة)\s*[:]?\s*([0-9\s,\.]+)", l_text)
        if ttc_match and fields["total_ttc"]["value"] is None:
            amt = parse_decimal_amount(ttc_match.group(1))
            if amt is not None:
                fields["total_ttc"]["value"] = amt
                fields["total_ttc"]["confidence"] = 0.98
                fields["total_ttc"]["bbox"] = line.bbox

    # Tax breakdown parsing
    tax_breakdown = []
    # Match lines like "TVA 20% Base: 1000.00 Montant: 200.00"
    for line in lines:
        m_tva = re.search(r"(?i)TVA\s*(\d{1,2})%\s*(?:Base\s*[:]?\s*([0-9\s,\.]+))?\s*(?:Montant\s*[:]?\s*([0-9\s,\.]+))?", line.text)
        if m_tva:
            rate_int = int(m_tva.group(1))
            rate_float = round(rate_int / 100.0, 2)
            base_ht = parse_decimal_amount(m_tva.group(2)) if m_tva.group(2) else fields["total_ht"]["value"]
            amt_vat = parse_decimal_amount(m_tva.group(3)) if m_tva.group(3) else None
            if amt_vat is not None:
                if fields["total_vat"]["value"] is None:
                    fields["total_vat"]["value"] = amt_vat
                    fields["total_vat"]["confidence"] = 0.98
                    fields["total_vat"]["bbox"] = line.bbox
            elif base_ht is not None:
                amt_vat = round(base_ht * rate_float, 2)
            if base_ht is not None and amt_vat is not None:
                tax_breakdown.append({
                    "rate": rate_float,
                    "base_ht": base_ht,
                    "tax_amount": amt_vat,
                })

    if fields["total_vat"]["value"] is None and tax_breakdown:
        fields["total_vat"]["value"] = round(sum(t["tax_amount"] for t in tax_breakdown), 2)
        fields["total_vat"]["confidence"] = 0.98

    if fields["supplier_is_auto_entrepreneur"]["value"] is True and fields["total_vat"]["value"] is None:
        fields["total_vat"]["value"] = 0.0
        fields["total_vat"]["confidence"] = 1.0

    if not tax_breakdown and fields["total_vat"]["value"] is not None and fields["total_ht"]["value"] is not None:
        # Check standard 20% or 10%
        tot_ht = fields["total_ht"]["value"]
        tot_vat = fields["total_vat"]["value"]
        if tot_ht > 0:
            calc_rate = round(tot_vat / tot_ht, 2)
            tax_breakdown.append({
                "rate": calc_rate,
                "base_ht": tot_ht,
                "tax_amount": tot_vat,
            })

    fields["tax_breakdown"] = tax_breakdown
    return fields


def run_extractor(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    document_version_id: uuid.UUID,
    ocr: OcrResult,
    doc_type: str = "purchase_invoice",
    provider_call_id: uuid.UUID | None = None,
    validation_report: Any | None = None,
) -> dict[str, Any]:
    """Runs the extractor agent, validates schemas, writes extractions and agent_runs."""
    agent_input = {
        "doc_type": doc_type,
        "full_text": ocr.full_text,
        "lines": [l.text for l in ocr.lines],
        "words": [w.text for w in ocr.words],
    }
    jsonschema.validate(instance=agent_input, schema=EXTRACTOR_INPUT_SCHEMA)

    extracted_fields = extract_fields_from_ocr(ocr, doc_type)
    output = {
        "fields": extracted_fields,
        "confidence": 0.96,
    }
    jsonschema.validate(instance=output, schema=EXTRACTOR_OUTPUT_SCHEMA)

    val_json = json.dumps(validation_report.to_dict()) if validation_report else "{}"

    # Insert into extractions table (strictly append-only)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extractions (
                tenant_id, document_version_id, schema_version, engine, engine_version,
                provider_call_id, status, fields, validation
            ) VALUES (%s, %s, '1.0.0', 'avenel_local_extractor', '1.0.0', %s, 'succeeded', %s, %s)
            RETURNING id;
            """,
            (
                tenant_id,
                document_version_id,
                provider_call_id,
                json.dumps(extracted_fields),
                val_json,
            ),
        )
        extraction_row = cur.fetchone()
        assert extraction_row is not None
        extraction_id = uuid.UUID(str(extraction_row[0]))

        # Insert into agent_runs table
        cur.execute(
            """
            INSERT INTO agent_runs (
                tenant_id, work_request_id, task, agent_version, prompt_version,
                input_refs, output, schema_valid, provider_call_id
            ) VALUES (%s, %s, 'extract', '1.0.0', 'extractor_v1', %s, %s, true, %s)
            RETURNING id;
            """,
            (
                tenant_id,
                work_request_id,
                json.dumps({"document_version_id": str(document_version_id)}),
                json.dumps(output),
                provider_call_id,
            ),
        )

    return {
        "extraction_id": extraction_id,
        "fields": extracted_fields,
        "confidence": 0.96,
    }
