# Phase 3 Plan — Proposals

## 1. Goal
Implement Phase 3 according to `ARCHITECTURE.md` (Version 2.0, 30 October 2026, Part G) and Part A mandatory rules.

### Phase 3 Scope & Deliverables
1. **Jurisdiction Pack Tax Mappings (`avenel/proposals/tax_mapping.py`)**:
   - Reads VAT rates and rules from `/jurisdiction/ma/vat_rates.yaml` and chart of accounts from `/jurisdiction/ma/cgnc_seed.yaml`.
   - Maps VAT rates (standard 20%, reduced 10%, exempt) to CGNC VAT accounts:
     - Deductible VAT on charges: `34552` ("État - TVA récupérable sur charges")
     - Deductible VAT on fixed assets: `34551` ("État - TVA récupérable sur immobilisations")
     - Collected VAT on sales: `4455` ("État - TVA facturée")
   - Supports client-specific account tax overrides (`client_tax_mappings` table).
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
   - Every line has `evidence_refs` linking to source document bounding boxes and extraction fields.
   - Invariant: `sum(debit_mad) == sum(credit_mad)` (strictly checked by PostgreSQL constraint trigger `journal_lines_balanced`).

4. **Foreign Exchange (FX) Handling (`avenel/proposals/fx.py`)**:
   - Handles transactions in foreign currencies (EUR, USD, etc.).
   - Resolves exchange rate from Bank Al-Maghrib (BAM) daily fixing rate fixtures (`fx_rate`, `fx_rate_date`, `fx_source = 'BAM'`).
   - Computes `debit_mad` and `credit_mad`, ensuring exact penny balance without rounding discrepancies.
   - Respects database check constraints on `journal_lines`.

5. **Probable Duplicate Detection (`avenel/proposals/duplicates.py`)**:
   - Detects potential duplicates when an upload is not an exact file hash duplicate:
     - Same supplier ICE/name + same invoice number, OR
     - Same supplier + exact amount + transaction date within $\pm 30$ days.
   - Raises issue `PROBABLE_DUPLICATE_INVOICE` with references to conflicting document and proposal.
   - Fixture recall $\ge 99\%$.

6. **Proposal Revision Service & API (`avenel/proposals/service.py`, `apps/api/routes/proposals.py`)**:
   - Manages proposals in `journal_proposals` and `journal_lines`.
   - Immutable audit trail: editing creates revision $N+1$, marks revision $N$ as `superseded`, sets `supersedes_id`.
   - Content hash computed over proposal lines.
   - Endpoints:
     - `GET /v1/work-requests/{id}/proposals`
     - `GET /v1/proposals/{id}`
     - `PUT /v1/proposals/{id}`
     - `POST /v1/proposals/{id}:approve`

7. **Review Screen with Keyboard Flow (`apps/web/src/components/ProposalReview.tsx`)**:
   - Web interface complying with Part E:
     - Keyboard navigation: `j`/`k` (navigate entries), `Enter` (approve), `e` (edit), `d` (flag duplicate).
     - Live balance delta display ($\Delta = 0.00\text{ MAD}$).
     - Direct linkage between journal line amounts and document bounding box overlays.

8. **Test Suite**:
   - Property tests with `hypothesis`: proposal balancing for arbitrary amounts, rates, and currencies.
   - Golden tests for each invoice type (Purchase, Multi-rate Purchase, Sale, Purchase Credit Note, Sales Credit Note, Fixed Asset, Foreign Currency EUR).
   - Duplicate detection tests.
   - RLS isolation tests.

---

## 2. Phase 3 Exit Criteria
Per `ARCHITECTURE.md` Part G:
- **Property tests (Hypothesis) show every generated proposal balances.**
- **Golden tests for each invoice type.**
- **Every line has evidence.**
- **All quality checks pass (`make lint test typecheck openapi-lint rls-check audit-verify`).**
