# Phase 3 Plan — Proposals

## 1. Goal
Implement Phase 3 according to `ARCHITECTURE.md` (Version 2.0, 30 October 2026, Part G) and Part A mandatory rules.

### Phase 3 Scope & Deliverables
1. **Jurisdiction Pack Tax Mappings (`avenel/proposals/tax_mapping.py`)**:
   - Reads VAT rates and rules from `/jurisdiction/ma/vat_rates.yaml`, deduction rules from `vat_deduction.yaml`, and chart of accounts from `/jurisdiction/ma/cgnc_seed.yaml`.
   - Tax accounts must resolve through `client_tax_mappings` (per client, `approved_by` required).
   - If no approved mapping exists for a needed tax_code/direction, creates no proposal line and raises `ACCOUNT_UNMAPPED` (blocking).
   - Jurisdiction pack provides suggested defaults for UI assistance only, never applied automatically.
   - Zero numeric literals outside `/jurisdiction/ma/*.yaml`.

2. **Account Suggester (`avenel/proposals/account_suggester.py`)**:
   - Suggests CGNC accounts for invoice items based on document type, supplier activity, historical entries, counterparties, and description keywords.
   - Defaults:
     - Purchases of merchandise: `6111` ("Achats de marchandises")
     - Purchases of raw materials: `6121` ("Achats de matières premières")
     - External charges & services: `6125`, `6131`, `6134`, `6141`, `6144`, `6147`
     - Sales of goods: `7111` ("Ventes de marchandises au Maroc")
     - Sales of services: `7124` ("Ventes de services produits au Maroc")
     - Fixed assets: `2355` ("Matériel informatique"), `2351` ("Mobilier de bureau"), `2340` ("Matériel de transport"), `2332` ("Matériel et outillage")
     - Supplier payable: `4411` ("Fournisseurs")
     - Customer receivable: `3421` ("Clients")
     - Fixed asset supplier: `4481` ("Dettes sur acquisitions d'immobilisations")
   - Suggestion ranking with confidence and reasoning; top suggestion targeted at $\ge 80\%$ acceptance.

3. **Rule-Based Entry Builder (`avenel/proposals/entry_builder.py`)**:
   - Generates balanced journal entries for:
     - **Purchases** (`ACH` journal)
     - **Sales** (`VEN` journal)
     - **Credit Notes** (Purchase Avoir $\to$ `ACH`/`OD`; Sales Avoir $\to$ `VEN`/`OD`)
     - **Fixed Assets** (`IMM`/`ACH` journal)
   - Every line has `evidence_refs` referencing document regions (`document_version_id`/`document_id`, `page`, `bbox`) or bank lines only.
   - Rule references live in `journal_proposals.rule_refs`; a line with only rule references in `evidence_refs` is rejected.
   - Domain rules applied:
     - Non-deductible VAT by cash limit (CGI art. 106-II: VAT added to charge account)
     - Non-deductible VAT by nature (CGI art. 106-I: passenger vehicles, gifts, receptions)
     - Auto-entrepreneur supplier (Loi 114-13 / CGI art. 89: zero VAT lines debited)
     - Prorata deduction (CGI art. 104: uses `client_entities.vat_prorata`)
   - Invariant: `sum(debit_mad) == sum(credit_mad)` (strictly checked by PostgreSQL constraint trigger `journal_lines_balanced`).

4. **Foreign Exchange (FX) Handling (`avenel/proposals/fx.py`) & Migration 004**:
   - FX rates stored per tenant in `fx_rates` table (migration `004_fx_rates`) with `rate_date, currency, rate, source ('bam_fixing', 'manual', 'imported')`, forced RLS.
   - Missing rate $\to$ `FX_RATE_MISSING` (blocking issue).
   - Residual cents posted to an explicit rounding line (`account_code` from approved client tax mapping direction `rounding` or pack default `6588` marked `needs_expert`), never to counterparty.
   - Counterparty line strictly equals invoice TTC converted at the stated rate (`round(ttc_tx * fx_rate, 2)`).

5. **Probable Duplicate Detection (`avenel/proposals/duplicates.py`)**:
   - Detects potential duplicates when an upload is not an exact file hash duplicate:
     `same counterparty AND (same invoice number OR (same TTC AND |date delta| <= window from pack))`
   - Window lives in jurisdiction pack (`invoice.duplicate_window_days: 20`).
   - Uses issue code `DUPLICATE_PROBABLE` from `issues.yaml`.
   - Negative tests: monthly rent same amount same supplier different invoice numbers 30 days apart is not flagged; different suppliers never flagged.

6. **Proposal Revision Service & API (`avenel/proposals/service.py`, `apps/api/routes/proposals.py`)**:
   - Manages proposals in `journal_proposals` and `journal_lines`.
   - Immutable audit trail: editing creates revision $N+1$, marks revision $N$ as `superseded`, sets `supersedes_id`.
   - Content hash computed over proposal lines.
   - No per-entry approval endpoint; approval exists only at the monthly-file level (Phase 5).
   - Role checks renamed to require "edit proposals" permission (`owner`, `manager`, `accountant`).
   - Endpoints:
     - `GET /v1/work-requests/{id}/proposals`
     - `GET /v1/proposals/{id}`
     - `PUT /v1/proposals/{id}`

7. **Review Screen with Keyboard Flow (`src/components/domain/ProposalReview.tsx`, `apps/web/src/components/ProposalReview.tsx`)**:
   - Web interface complying with Part E:
     - Keyboard navigation: `j`/`k` (navigate proposals), `Enter` (confirms focused line only), `e` (toggle editing).
     - No approve action in ProposalReview; no keyboard path triggers approval.
     - Live balance delta display ($\Delta = 0,00\text{ MAD}$).
     - Direct linkage between journal line amounts and document bounding box overlays (160ms transition).

8. **Test Suite**:
   - Property tests with `hypothesis` (`max_examples >= 1000`) for proposal balancing across multi-rate, credit notes, FX, and 0.005 boundary amounts.
   - Golden tests:
     - Standard purchase invoice
     - Multi-rate purchase invoice
     - Sales invoice
     - Purchase credit note reversing purchase
     - Sales credit note
     - Fixed asset acquisition
     - Non-deductible VAT by cash limit
     - Non-deductible VAT by nature
     - Auto-entrepreneur supplier (no VAT lines)
     - Prorata deduction using `client_entities.vat_prorata`
     - Foreign currency EUR invoice with residual cents
     - Evidence refs validation (rejection of lines with only rule refs)
     - Missing approved tax mapping raises `ACCOUNT_UNMAPPED`
     - Missing FX rate raises `FX_RATE_MISSING`
   - Duplicate detection tests (positive and negative cases).
   - RLS isolation and migration rollback tests.

---

## 2. Phase 3 Exit Criteria
Per `ARCHITECTURE.md` Part G:
- **Property tests (Hypothesis) show every generated proposal balances.**
- **Golden tests for each invoice type.**
- **Every line has evidence.**
- **All quality checks pass (`make lint test typecheck openapi-lint rls-check audit-verify`).**

