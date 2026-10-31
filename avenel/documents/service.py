"""Document intake, processing, and field correction service.

Implements the Phase 2 intake and reading workflow:
1. Upload registration & exact duplicate detection
2. Magic-byte verification and malware scan
3. Page rendering and local OCR
4. Document classification and field extraction
5. Deterministic invoice validation (D.6)
6. Field correction with immutable evidence tracking
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from avenel.documents.renderer import render_document
from avenel.documents.scanner import record_scan_evidence, scan_bytes
from avenel.extraction.classifier import run_classifier
from avenel.extraction.extractor import run_extractor
from avenel.extraction.validation import (
    persist_validation_results,
    validate_invoice_extraction,
)
from avenel.infrastructure.storage import (
    ALLOWED_MIME_TYPES,
    MAX_DOCUMENT_BYTE_SIZE,
    compute_sha256,
    detect_magic_bytes,
    get_storage,
)
from avenel.ocr.adapter import get_ocr_engine


class DocumentNotFoundError(Exception):
    pass


class WorkRequestNotFoundError(Exception):
    pass


class DuplicateDocumentError(Exception):
    pass


class InvalidDocumentPayloadError(Exception):
    pass


class QuarantineError(Exception):
    pass


@dataclass(frozen=True)
class UploadInitResult:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    object_key: str
    presigned_upload: dict[str, Any]


def init_document_upload(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    original_filename: str,
    byte_size: int,
    mime_type: str,
    sha256: str,
    uploaded_by: uuid.UUID | None = None,
    source_channel: str = "console",
) -> UploadInitResult:
    """Initializes document and version records and checks for exact duplicates."""
    # 1. Resolve work request and client entity
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, client_entity_id, accounting_period_id
            FROM work_requests
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, work_request_id),
        )
        wr_row = cur.fetchone()
        if not wr_row:
            raise WorkRequestNotFoundError(f"Work request {work_request_id} not found")
        client_entity_id = uuid.UUID(str(wr_row[1]))

    # 2. Check byte size bounds
    if byte_size <= 0 or byte_size > MAX_DOCUMENT_BYTE_SIZE:
        raise InvalidDocumentPayloadError(
            f"Document byte size {byte_size} exceeds allowed limits (1 to {MAX_DOCUMENT_BYTE_SIZE} bytes)"
        )

    # 3. Check exact duplicate detection by (tenant_id, client_entity_id, sha256)
    normalized_sha256 = sha256.lower()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT document_id
            FROM document_versions
            WHERE tenant_id = %s AND client_entity_id = %s AND sha256 = %s;
            """,
            (tenant_id, client_entity_id, normalized_sha256),
        )
        dup_row = cur.fetchone()
        if dup_row:
            raise DuplicateDocumentError(
                f"Exact duplicate document detected (SHA-256: {normalized_sha256}) for this company"
            )

    # 4. Create document row
    storage = get_storage()
    doc_id = uuid.uuid4()
    doc_version_id = uuid.uuid4()
    object_key = f"documents/{tenant_id}/{client_entity_id}/{doc_id}/v1"

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (
                id, tenant_id, client_entity_id, work_request_id,
                doc_type, status, original_filename, source_channel, uploaded_by
            ) VALUES (%s, %s, %s, %s, 'purchase_invoice', 'received', %s, %s, %s);
            """,
            (
                doc_id,
                tenant_id,
                client_entity_id,
                work_request_id,
                original_filename,
                source_channel,
                uploaded_by,
            ),
        )

        cur.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, client_entity_id, document_id, version_number,
                object_key, sha256, mime_type, byte_size, page_count
            ) VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, 1)
            RETURNING id;
            """,
            (
                doc_version_id,
                tenant_id,
                client_entity_id,
                doc_id,
                object_key,
                normalized_sha256,
                mime_type,
                byte_size,
            ),
        )

    presigned = storage.generate_presigned_put_url(object_key)
    return UploadInitResult(
        document_id=doc_id,
        document_version_id=doc_version_id,
        object_key=object_key,
        presigned_upload=presigned,
    )


def process_uploaded_document(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    data: bytes | None = None,
) -> dict[str, Any]:
    """Completes upload, executes malware scan, rendering, OCR, classification, extraction, and validation."""
    storage = get_storage()

    # 1. Fetch document and version details
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.client_entity_id, d.work_request_id, d.status,
                   dv.id, dv.object_key, dv.mime_type, dv.byte_size, dv.sha256
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s AND d.id = %s
            ORDER BY dv.version_number DESC
            LIMIT 1;
            """,
            (tenant_id, document_id),
        )
        row = cur.fetchone()
        if not row:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        doc_id = uuid.UUID(str(row[0]))
        client_entity_id = uuid.UUID(str(row[1]))
        work_request_id = uuid.UUID(str(row[2]))
        version_id = uuid.UUID(str(row[4]))
        object_key = str(row[5])
        declared_mime = str(row[6])

    # 2. Retrieve payload from storage if not passed directly
    if data is None:
        data = storage.get_object(object_key)

    # 3. Magic-byte verification
    detected_mime = detect_magic_bytes(data)
    if detected_mime is None and declared_mime not in ALLOWED_MIME_TYPES:
        raise InvalidDocumentPayloadError("Unsupported document file format or corrupted magic bytes")
    effective_mime = detected_mime or declared_mime

    # 4. Malware scan
    scan_result = scan_bytes(data)
    record_scan_evidence(
        conn=conn,
        tenant_id=tenant_id,
        work_request_id=work_request_id,
        document_id=doc_id,
        scan_result=scan_result,
    )

    if not scan_result.is_clean:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET status = 'quarantined'
                WHERE tenant_id = %s AND id = %s;
                """,
                (tenant_id, doc_id),
            )
            cur.execute(
                """
                INSERT INTO issues (
                    tenant_id, client_entity_id, work_request_id, subject_document_id,
                    code, severity, status, evidence_refs
                ) VALUES (%s, %s, %s, %s, 'DOC_MALWARE', 'blocking', 'open', %s);
                """,
                (
                    tenant_id,
                    client_entity_id,
                    work_request_id,
                    doc_id,
                    json.dumps([scan_result.details] if scan_result.details else []),
                ),
            )
        raise QuarantineError(f"Document quarantined: {scan_result.threat_name}")

    # 5. Page rendering
    render_res = render_document(
        tenant_id=str(tenant_id),
        document_id=str(doc_id),
        data=data,
        mime_type=effective_mime,
    )

    # 6. Local OCR execution
    ocr_engine = get_ocr_engine()
    ocr_res = ocr_engine.process(data, mime_type=effective_mime, page_count=render_res.page_count)

    # 7. Classifier Agent
    classification = run_classifier(
        conn=conn,
        tenant_id=tenant_id,
        work_request_id=work_request_id,
        text=ocr_res.full_text,
        page_count=render_res.page_count,
    )
    doc_type = classification["doc_type"]

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
            SET doc_type = %s
            WHERE tenant_id = %s AND id = %s;
            """,
            (doc_type, tenant_id, doc_id),
        )

    # 8. Deterministic validation (D.6) before extraction insert
    # Fetch period bounds for period mismatch check
    period_start = None
    period_end = None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ap.starts_on, ap.ends_on
            FROM work_requests wr
            JOIN accounting_periods ap ON ap.id = wr.accounting_period_id
            WHERE wr.tenant_id = %s AND wr.id = %s;
            """,
            (tenant_id, work_request_id),
        )
        p_row = cur.fetchone()
        if p_row:
            period_start = p_row[0]
            period_end = p_row[1]

    # Pre-extract fields for deterministic validation
    from avenel.extraction.extractor import extract_fields_from_ocr
    extracted_fields = extract_fields_from_ocr(ocr_res, doc_type)
    val_report = validate_invoice_extraction(
        fields=extracted_fields,
        doc_type=doc_type,
        period_start=period_start,
        period_end=period_end,
    )

    # 9. Extractor Agent (writes append-only extractions with validation report included)
    extraction_out = run_extractor(
        conn=conn,
        tenant_id=tenant_id,
        work_request_id=work_request_id,
        document_version_id=version_id,
        ocr=ocr_res,
        doc_type=doc_type,
        validation_report=val_report,
    )
    extraction_id = extraction_out["extraction_id"]

    persist_validation_results(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        work_request_id=work_request_id,
        document_id=doc_id,
        extraction_id=extraction_id,
        report=val_report,
    )

    doc_status = "needs_review" if (val_report.blocking_count > 0 or val_report.review_count > 0) else "read"
    return {
        "document_id": str(doc_id),
        "doc_type": doc_type,
        "status": doc_status,
        "page_count": render_res.page_count,
        "extraction_id": str(extraction_id),
        "fields": extracted_fields,
        "validation": val_report.to_dict(),
    }


def correct_extraction_fields(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    field_updates: dict[str, Any],
) -> dict[str, Any]:
    """Allows human accountant to correct extracted fields, creating immutable evidence and re-validating."""
    # 1. Fetch document and current extraction
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.client_entity_id, d.work_request_id, d.doc_type,
                   e.id, e.fields, dv.id
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            JOIN extractions e ON e.document_version_id = dv.id AND e.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s AND d.id = %s
            ORDER BY e.created_at DESC
            LIMIT 1;
            """,
            (tenant_id, document_id),
        )
        row = cur.fetchone()
        if not row:
            raise DocumentNotFoundError(f"Extraction for document {document_id} not found")

        doc_id = uuid.UUID(str(row[0]))
        client_entity_id = uuid.UUID(str(row[1]))
        work_request_id = uuid.UUID(str(row[2]))
        doc_type = str(row[3])
        prev_extraction_id = uuid.UUID(str(row[4]))
        current_fields = row[5]
        doc_version_id = uuid.UUID(str(row[6]))
        if isinstance(current_fields, str):
            current_fields = json.loads(current_fields)

    # 2. Merge field updates
    for k, v in field_updates.items():
        if k in current_fields:
            if isinstance(current_fields[k], dict):
                current_fields[k]["value"] = v
                current_fields[k]["confidence"] = 1.0  # Human validated
            else:
                current_fields[k] = v
        else:
            current_fields[k] = {"value": v, "confidence": 1.0, "page": 1, "bbox": None}

    # 3. Re-run deterministic validation
    period_start = None
    period_end = None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ap.starts_on, ap.ends_on
            FROM work_requests wr
            JOIN accounting_periods ap ON ap.id = wr.accounting_period_id
            WHERE wr.tenant_id = %s AND wr.id = %s;
            """,
            (tenant_id, work_request_id),
        )
        p_row = cur.fetchone()
        if p_row:
            period_start = p_row[0]
            period_end = p_row[1]

    val_report = validate_invoice_extraction(
        fields=current_fields,
        doc_type=doc_type,
        period_start=period_start,
        period_end=period_end,
    )

    # 4. Insert new append-only extraction and immutable evidence record
    new_extraction_id = uuid.uuid4()
    evidence_payload = {
        "action": "field_correction",
        "document_id": str(doc_id),
        "previous_extraction_id": str(prev_extraction_id),
        "new_extraction_id": str(new_extraction_id),
        "field_updates": field_updates,
        "corrected_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    content_sha256 = compute_sha256(json.dumps(evidence_payload, sort_keys=True).encode("utf-8"))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extractions (
                id, tenant_id, document_version_id, schema_version, engine, engine_version,
                status, fields, validation
            ) VALUES (%s, %s, %s, '1.0.0', 'human_correction', '1.0.0', 'succeeded', %s, %s);
            """,
            (
                new_extraction_id,
                tenant_id,
                doc_version_id,
                json.dumps(current_fields),
                json.dumps(val_report.to_dict()),
            ),
        )

        cur.execute(
            """
            INSERT INTO evidence_records (
                tenant_id, work_request_id, subject_type, subject_id, kind, payload, content_sha256
            ) VALUES (%s, %s, 'extraction', %s, 'field_correction', %s, %s);
            """,
            (
                tenant_id,
                work_request_id,
                new_extraction_id,
                json.dumps(evidence_payload),
                content_sha256,
            ),
        )

    persist_validation_results(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        work_request_id=work_request_id,
        document_id=doc_id,
        extraction_id=new_extraction_id,
        report=val_report,
    )

    return {
        "extraction_id": str(new_extraction_id),
        "fields": current_fields,
        "validation": val_report.to_dict(),
    }
