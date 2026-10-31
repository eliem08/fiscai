# Real Labelled Dataset Harness (Part H Gates)

This directory is the evaluation harness for **real client bookkeeping documents** (purchase invoices, sales invoices, cash receipts, bank statements) collected under non-disclosure agreements with pilot *fiduciaires*.

## Privacy & Legal Compliance (CNDP / Loi 09-08)
- Real documents contain personal data and commercial secrets subject to Moroccan Law 09-08 (CNDP).
- **All real document files in this directory are strictly gitignored** and must never be committed to source control.
- Documents are **encrypted at rest** using AES-256-GCM or age (`age -r ...`).

## Ground Truth Labels Schema
Ground truth annotations must be provided in `labels.jsonl` adhering strictly to [`labels.schema.json`](labels.schema.json). Each line is a JSON object with:
- `document_id`: unique identifier
- `file_path`: relative path to decrypted document file
- `mime_type`: `application/pdf`, `image/png`, or `image/jpeg`
- `category`: `french_corporate`, `arabic_commercial`, `cash_quittance`, `auto_entrepreneur`, etc.
- `ground_truth`: exact values for `invoice_number`, `invoice_date`, `supplier_ice`, `supplier_if`, `total_ht`, `total_vat`, `total_ttc`, `payment_method`, `supplier_is_auto_entrepreneur`.

## Pilot Target Gates (ARCHITECTURE.md Part H)
Per ARCHITECTURE.md Part H, gates are measured on a real labelled set of **≥ 300 documents**:
1. `ICE, invoice number, date exact match`: **≥ 97.0%**
2. `HT, TVA per rate, TTC exact match after arithmetic check`: **≥ 98.0%**
3. `Exact duplicate detection`: **100%**
4. `Probable duplicate recall`: **≥ 99%**
5. `Cross-tenant leak tests`: **0 failures**

> [!IMPORTANT]
> **Do not claim Part H gates are met until this harness is executed against the real decrypted document set.**
> Synthetic pipeline tests provide indicative pipeline performance but do NOT constitute fulfillment of Part H pilot gates.

## Running the Evaluation
To decrypt documents and run the Part H evaluation script:
```bash
python scripts/evaluate_real_set.py \
  --labels-file tests/fixtures/real/labels.jsonl \
  --docs-dir tests/fixtures/real/
```

