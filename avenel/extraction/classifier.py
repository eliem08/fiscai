"""Classifier Agent for Moroccan accounting and fiscal documents.

Classifies incoming documents into doc_type, language, and page roles.
Never rejects a document. Logs each run to agent_runs.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import psycopg

from avenel.extraction.schemas import CLASSIFIER_INPUT_SCHEMA, CLASSIFIER_OUTPUT_SCHEMA

PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier_v1.txt"


def classify_document_text(text: str) -> dict[str, Any]:
    """Deterministic, rule-backed classifier analyzing French & Arabic document terms."""
    lower_text = text.lower()

    # Detect language
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    if arabic_chars > 20 and latin_chars > 20:
        language = "bilingual"
    elif arabic_chars > latin_chars:
        language = "ar"
    else:
        language = "fr"

    # Detect doc_type
    if any(k in lower_text for k in ["avoir", "note d'avoir", "credit note", "إشعار دائن", "فاتورة إنقاص"]):
        doc_type = "credit_note"
        confidence = 0.96
    elif any(k in lower_text for k in ["relevé de compte", "relevé bancaire", "bank statement", "كشف حساب", "كشف بنكي"]):
        doc_type = "bank_statement"
        confidence = 0.98
    elif any(k in lower_text for k in ["reçu", "quittance", "ticket de caisse", "reçu de paiement", "إيصال", "وصل"]):
        doc_type = "receipt"
        confidence = 0.94
    elif any(k in lower_text for k in ["note de frais", "frais de déplacement", "expense report", "مصاريف"]):
        doc_type = "expense_note"
        confidence = 0.92
    elif any(k in lower_text for k in ["douane", "déclaration unique de marchandise", "dum", "جمارك"]):
        doc_type = "customs_document"
        confidence = 0.95
    elif any(k in lower_text for k in ["facture de vente", "sales invoice"]):
        doc_type = "sales_invoice"
        confidence = 0.94
    elif any(k in lower_text for k in ["facture", "facture n°", "facture no", "invoice", "فاتورة", "فاتورة رقم"]):
        doc_type = "purchase_invoice"
        confidence = 0.95
    else:
        doc_type = "other"
        confidence = 0.70

    return {
        "doc_type": doc_type,
        "language": language,
        "confidence": confidence,
        "page_roles": ["body"],
    }


def run_classifier(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    text: str,
    page_count: int = 1,
) -> dict[str, Any]:
    """Runs the classifier agent, validates schemas, and records agent_runs row."""
    agent_input = {"text": text, "page_count": page_count}
    jsonschema.validate(instance=agent_input, schema=CLASSIFIER_INPUT_SCHEMA)

    output = classify_document_text(text)
    jsonschema.validate(instance=output, schema=CLASSIFIER_OUTPUT_SCHEMA)

    # Record to agent_runs
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_runs (
                tenant_id, work_request_id, task, agent_version, prompt_version,
                input_refs, output, schema_valid
            ) VALUES (%s, %s, 'classify', '1.0.0', 'classifier_v1', %s, %s, true)
            RETURNING id;
            """,
            (
                tenant_id,
                work_request_id,
                json.dumps({"text_length": len(text), "page_count": page_count}),
                json.dumps(output),
            ),
        )

    return output

