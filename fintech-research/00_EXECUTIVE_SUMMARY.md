# Fintech Opportunity Lab — Executive Summary (first desk-research pass, 30 Oct 2026)

## Scope and honesty statement

This is a **first desk-research pass**, done in one session with web search. What it is and isn't:

- **Done:** problem-first scan across the financial value chain, YC 2026 thesis signals, a focused deep-dive on Morocco, 30 opportunities generated and scored, top 10 ranked, top 3 challenged, a primary thesis with a 90-day plan.
- **Not done (and why):**
  - No complete YC company database for every 2025–2026 batch: the YC site could not be fetched from this environment (certificate error), so batch data comes from secondary trackers and press, cited as such.
  - No systematic Reddit/G2 mining.
  - No customer interviews — none are claimed anywhere.
- Every market figure is cited or explicitly marked **[H] = hypothesis**. Treat this as a map for where to dig, not as validation.

## The answer in one paragraph

The strongest opportunity found is **not** in the crowded US themes (agent payments, stablecoin rails, AML copilots), where Stripe, Visa, Coinbase and well-funded YC companies are already active. It is a **regulation-forced, money-at-stake problem in Morocco**:

- Since Law 69-21 on payment terms, every company above MAD 2M turnover must file **quarterly supplier-payment declarations** to the DGI.
- Companies pay fines on invoices paid late. The government's Observatory reports **MAD 1.331 billion in fines in 2025** and **56,000+ declaring companies**.
- The 2026–2028 phased **e-invoicing mandate** adds a second compliance wave on the same data (invoices, due dates, payments).

The proposed company:

1. **Wedge:** automate the 69-21 declaration and late-fine forecasting from the company's ledger/ERP data.
2. **Expansion:** use that invoice-level data to offer **"pay on time" supplier finance** through licensed banks and factoring companies, priced below the fine. The fine is a known, computable cost, so the ROI is arithmetic, not a promise.

## Selection

| Role | Opportunity | One-line reason |
|---|---|---|
| **Primary** | **Moroccan payables compliance → supplier-finance platform** ("69-21 + e-invoicing + pay-on-time finance") | Mandatory, recurring (quarterly), measurable cost (MAD 1.33bn fines in 2025), weak incumbents (Sage module, consultants, Excel) |
| Alternative 1 | FiscAI PreClear — customs/VAT pre-check for importers and customs brokers (existing repo) | Real pain, but unproven frequency, unclear buyer, depends on document AI quality |
| Alternative 2 | Moroccan e-invoicing compliance middleware for ERPs/accounting firms | Forced by law 2026–2028, but heavy competition from global e-invoicing vendors once rules are final |
| Monitor | Stablecoin cross-border supplier payments for MENA/Africa importers | Real cost problem, but Morocco's crypto bill (42.25) is not enacted and FX rules route payments through banks |

## The three biggest risks to the primary thesis

1. **Incumbent bundling.** Sage Maroc launched a 69-21 compliance module in 2023, and ERPs (Sage, Odoo partners) can add the declaration for free. The declaration alone is a feature, not a company. The finance layer must be the business.
2. **Who actually pays the fines.** In 2025, 82.7% of declared late invoices came from large companies (turnover above MAD 50M). They have ERPs and bank relationships, so selling to them is slow enterprise sales. SMEs are mostly the victims of late payment, not the payers of fines.
3. **Finance is licensed.** Arranging or offering finance may require a Bank Al-Maghrib status, such as an intermediary under banking law, or a partnership with a licensed factoring company. This must be confirmed with a Moroccan lawyer before the finance layer is built. **[H]**

## What would prove it (next 30 days, zero code)

- 10 conversations with finance directors (DAF) of companies above MAD 50M turnover, and 5 with accounting firms (fiduciaires) that file 69-21 declarations for clients.
- Get 3 companies to share one quarter of anonymized supplier-invoice data, and compute their real fine exposure.
- 1 factoring company or bank says it would fund on-time supplier payments sourced from this data.
- 1 letter of intent or paid pilot (e.g. MAD 2–5k per quarter for the declaration plus fine forecast) **[H: pricing untested]**.

## Files

| # | File | Content |
|---|---|---|
| 1 | `YC_FINTECH_INTELLIGENCE.md` | YC 2026 RFS and batch signals |
| 2 | `FINTECH_PROBLEM_MAP.md` | Pain map across 9 segments |
| 3 | `CUSTOMER_PAIN_DISCOVERY.md` | Evidenced problems, with evidence strength |
| 4 | `COMPETITIVE_GAP_ANALYSIS.md` | Competitor matrices and gap types |
| 5 | `FINTECH_FUTURE_OPPORTUNITIES.md` | 2026–2030 shifts |
| 6 | `GEOGRAPHIC_FINTECH_OPPORTUNITIES.md` | Regions, Morocco deep-dive |
| 7 | `FINTECH_OPPORTUNITY_RANKING.md` / `.xlsx` | 30 opportunities scored |
| 8 | `TOP_10_FINTECH_OPPORTUNITIES.md` | Deep-dives and challenges |
| 9 | `FIRST_CUSTOMER_STRATEGY.md` | Prospects, interview scripts, pilot, ROI model |
| 10 | `FINTECH_REGULATORY_FEASIBILITY.md` | Regulatory paths |
| 11 | `EXISTING_ASSET_FIT.md` | What the FiscAI repo can reuse |
| 12 | `FINAL_STARTUP_THESIS.md` | Thesis, MVP, roadmap |
| 13 | `SOURCE_REGISTER.md` | Every source used, with a reliability rating |
