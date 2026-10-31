# Final Startup Thesis (working name: "Délai")

## Startup thesis
Moroccan companies with turnover above MAD 2M must declare supplier-payment delays to the DGI every quarter and pay fines on late invoices. That was **MAD 1.331bn in 2025, across 56,000+ declaring companies** (S19). From 2026–2028 they must also switch to mandatory e-invoicing.

We automate the declaration and **forecast fines invoice by invoice**, starting with mid-size and large companies and the accounting firms (fiduciaires) that serve SMEs. We then use that payables data to offer **"pay on time" supplier finance through licensed factors and banks**, priced below the fine. The buyer avoids the fine, the supplier gets paid on time, and the financier gets verified receivables.

Compliance is the wedge. Finance is the business.

## Problem statement
- Payment-terms compliance is quarterly, invoice-level, error-prone and costly. The fines are paid in cash.
- Meanwhile, SME suppliers carry the cost of late payment: they filed 95% of complaints in 2025 (S19).
- Morocco's SME finance gap is $20.4bn, attributed to weak risk architecture (S15).

## Customer
- **Economic buyer:** finance director (DAF) of companies with turnover above MAD 50M.
- **User:** AP accountant.
- **Channel:** accounting firms (fiduciaires) for the MAD 2–50M band.
- **Financier partner:** a factoring company or a bank's factoring arm (second customer).

## Product (MVP)
1. Upload or connect: supplier invoices and payments (CSV/Excel from any ERP; Sage/Odoo connectors later).
2. Rule engine: applicable term (60/120/180), days late, fine, nil-declaration handling, disputed invoices.
3. Output: declaration ready to file + audit trail + **next-quarter fine forecast**.
4. Phase 2: "finance these invoices" — partner offer vs fine, one click to refer.

**Measurable value:** hours saved per declaration, declarations accepted without correction, fines avoided.

## Differentiation
- ERP-neutral, where Sage's module covers Sage users.
- Forward-looking (forecast) rather than after-the-fact.
- Connects compliance to cash (financing).
- Becomes e-invoicing-native as the DGI regime arrives: cleared invoices make receivables cheaper to finance **[H]**.

## Business model
- SaaS per entity, or per client for accounting firms.
- Plus a finance origination fee or revenue share from capital partners.
- **No balance-sheet lending at the start.**

## Initial market
Morocco: Casablanca–Tangier industrial and distribution companies (MAD 50–500M turnover) plus 10 accounting firms.

## First ten customers
1. Warm introductions via CEED Maroc, the Morocco Fintech Center, and the accounting profession (OEC).
2. Free declaration in exchange for data and a case study.
3. CGEM SME commission events around the quarterly deadline (deadline-driven outreach).
4. Accounting firms as multipliers: one firm brings dozens of clients.

## Roadmap
| Period | Goal |
|---|---|
| Days 1–30 | 15 interviews (10 finance directors, 5 accounting firms) + **lawyer opinion** on intermediary status + read the official 69-21 text and DGI circulars. No code beyond a spreadsheet model. |
| Days 31–60 | Spreadsheet/CLI calculator run on 3 real (anonymized) datasets; compare with the declarations actually filed. Approach 2 factoring partners. |
| Days 61–90 | Web MVP (reuse FiscAI's rule-engine/audit patterns); 1–3 paid pilots for the next quarterly deadline. |
| Months 4–6 | 10 paying entities / 3 accounting firms; first financed invoice batch via a partner. |
| Months 6–12 | ERP connectors; e-invoicing integration once the DGI specs are final; supplier-side portal; assess Tunisia / francophone West Africa rule packs. |

## Three biggest reasons it could fail
1. **Buyers accept fines** as the price of their payment policy, and financing doesn't beat them, so no pull for the finance layer. Compliance alone is then a feature that Sage or the DGI commoditizes.
2. **Capital partners won't engage** with a startup, or the intermediary status takes too long.
3. **Market ceiling:** Morocco-only compliance is a small business. Venture scale depends on the finance volume, or on multi-country rule packs that are not yet researched.

## YC thesis
- **Timely:** regulation-forced and recurring (quarterly deadlines, scope widened in 2026, e-invoicing 2026–28).
- **Matches YC's 2026 interest:** AI-native finance operations, plus financial services for emerging-market businesses.
- **Strong application evidence:** paid pilots, MAD of fines forecast vs actual, a signed capital partner, and the first financed invoice volume. **None of this exists yet.**

## Alternatives and monitor
- **Alt 1 — FiscAI PreClear:** validate error frequency with customs brokers.
- **Alt 2 — e-invoicing middleware:** revisit when the DGI decree lands.
- **Monitor — stablecoin supplier payments for MENA importers:** revisit if Bill 42.25 passes with a path for non-bank participation.
