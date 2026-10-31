# Phase 2 Plan — Intake and Reading

## 1. Goal
Implement Phase 2 according to `ARCHITECTURE.md` (Version 2.0, 30 October 2026, Part G) and Part A mandatory rules.

### Phase 2 Scope & Deliverables
1. **Upload Flow & Ingestion**:
   - `POST /v1/work-requests/{id}/uploads`: generates upload URL/presigned parameters, validates file size ($\le 50$ MB), magic bytes, and permitted MIME types (`application/pdf`, `image/jpeg`, `image/png`, `image/heic`, `image/tiff`).
   - Exact duplicate detection by SHA-256 (unique per tenant + client company): duplicate SHA-256 returns 409 Conflict with code `DUPLICATE_DOCUMENT`.
   - `POST /v1/documents/{id}:complete-upload`: confirms upload, triggers malware scan and ingestion pipeline.

2. **Malware Scan Adapter**:
   - Analyzes file payload/stream for signatures (including standard EICAR test signature).
   - If infected, sets document status to `quarantined` and creates an append-only `evidence_records` row with `kind='malware_scan'`.

3. **Page Rendering & Local OCR Adapter**:
   - Renders multi-page documents (PDF, TIFF, JPEG, PNG) into standard page images.
   - Endpoint: `GET /v1/documents/{id}/pages/{n}` returning image URL.
   - Local OCR adapter returning extracted words, text spans, confidences, and bounding boxes in normalized coordinates `[ymin, xmin, ymax, xmax]`.

4. **Data Residency & Provider Router (C.6)**:
   - Tenant data residency policies: `MA_ONLY` (default), `EU_ALLOWED`, `GLOBAL_ALLOWED`.
   - Router strictly enforces:
     - Under `MA_ONLY`, forbids all external non-Moroccan calls, records `status='refused_by_policy'` in `provider_calls`.
     - In test environments, guarantees **zero external provider calls**.
     - Strips sensitive identifiers (ICE, IF, RIB, person names) unless permitted by policy.
     - Logs every call in `provider_calls` with provider, region, model, purpose, input_sha256, and token/cost tracking.

5. **Classifier & Extractor Agents (D.8)**:
   - AI agents wrapped with JSON Schema input/output and prompt versioning.
   - Classifier: determines `doc_type` (`purchase_invoice`, `sales_invoice`, `credit_note`, `receipt`, `bank_statement`, `expense_note`, `customs_document`, `other`), language (`fr`, `ar`), and confidence.
   - Extractor: extracts structured fields with bounding boxes and confidences.
   - Stores extraction results in `extractions` table with status `succeeded`, `partial`, or `failed`.

6. **Deterministic Invoice Validation (D.6)**:
   - Validates mandatory mentions loaded from jurisdiction pack (`invoices.yaml`): missing fields $\to$ `INVOICE_MISSING_MANDATORY_FIELD` (`review` for purchases, `info` for sales).
   - Per-rate arithmetic: $\sum \text{line HT} = \text{HT per rate}$; $\text{HT} \times \text{rate} = \text{TVA}$ (tolerance 0.01 MAD); $\sum = \text{TTC}$. Failure $\to$ `TOTALS_INCONSISTENT` (blocking).
   - VAT rate check against pack for invoice date $\to$ `VAT_RATE_UNKNOWN` (blocking).
   - Auto-entrepreneur supplier with TVA > 0 $\to$ `VAT_ON_AUTO_ENTREPRENEUR_INVOICE` (review).
   - Cash payment above pack limit $\to$ TVA marked non-deductible, `VAT_NOT_DEDUCTIBLE_CASH_LIMIT` (review).
   - Invoice date outside period $\to$ `PERIOD_MISMATCH` (review).
   - Writes detected exceptions to `issues` table.

7. **Document Viewer & Field Correction API**:
   - `GET /v1/work-requests/{id}/documents`
   - `GET /v1/documents/{id}`
   - `GET /v1/documents/{id}/extraction`
   - `PATCH /v1/documents/{id}/extraction`: allows human accountant to correct extracted fields; creates `evidence_records` with `kind='field_correction'`, updates `extractions.fields`, and reruns deterministic validation.

8. **Fixture Benchmark (300 Documents)**:
   - 300 test document fixtures covering French and Arabic, receipts and invoices, scans and digital PDFs, multi-page, clear and noisy/skewed samples.
   - Benchmark script evaluating field-level accuracy (Precision, Recall, F1) across critical fields (supplier ICE, invoice number, date, HT, TVA, TTC).

---

## 2. Phase 2 Exit Criteria
Per `ARCHITECTURE.md` Part G:
- **On the fixture set of 300 documents, field-level accuracy report generated.**
- **Residency router refuses disallowed calls.**
- **No provider call in tests (zero external network requests).**
- **All quality gates pass (`make lint test typecheck openapi-lint rls-check audit-verify`).**

