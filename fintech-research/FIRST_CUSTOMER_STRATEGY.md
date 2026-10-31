# First Customer Strategy

> **Prospect lists use organization profiles and public signals only.** No employee names, emails, budgets or buying interest are invented. Named organizations are publicly known entities whose relevance is a **hypothesis to verify**, not evidence that they want to buy.

## Opportunity 1 — 69-21 compliance → supplier finance

### 20 prospect profiles

| # | Profile | Why relevant | Decision-maker role |
|---|---|---|---|
| 1–5 | Listed Casablanca Stock Exchange companies in distribution, building materials and food industry | Publish financial statements, so supplier payables are visible; large supplier base **[H]** | DAF / Group financial controller |
| 6–8 | Public companies (EEP) in the Observatory's monitored list of 205; 12 have average terms above 90 days | Officially reported as late payers (S21) | DAF, internal audit |
| 9–12 | Mid-size (MAD 50–500M) Odoo or local-ERP users | Outside Sage's module **[H]** | DAF |
| 13–16 | Accounting firms (fiduciaires) in Casablanca/Tangier/Fès with 100+ SME clients | They file 69-21 declarations for many clients | Managing partner |
| 17 | The Moroccan accounting professional bodies (Ordre des Experts-Comptables, OEC) | Distribution and education channel | President / training committee |
| 18 | CGEM (the employers' confederation), SME commission | Advocacy on payment terms; event channel | Commission chair |
| 19 | A factoring company or the factoring arm of a bank **[names to verify]** | Capital partner for pay-on-time finance | Head of factoring / SCF |
| 20 | Tamwilcom (state guarantee agency) / Morocco Fintech Center | Guarantee, sandbox, credibility (S15, S30) | Innovation lead |

### Discovery interview (finance director, 30 minutes, no pitch)
1. Walk me through your last 69-21 quarterly declaration. Who did it, how long did it take, and with what tools?
2. What did you pay in fines last year? Did that number go to the CEO or board?
3. Which invoices go late, and why: cash, disputes, approvals, or deliberate terms?
4. Have you used reverse factoring or confirming? Why or why not?
5. If someone paid your suppliers on time, with you settling at day 90, at what cost would that beat the fine?
6. What happens when the declaration is wrong?
7. Who else in Morocco do you know who struggles with this?

### Problem-validation questionnaire (accounting firms)
- Number of clients subject to 69-21
- Hours per client per quarter
- Errors or rejections seen
- Current tool (Excel, Sage, DGI portal)
- Price currently charged for this service
- Would you pay per client for a tool? At what price?

### 5-minute demo (for after 5 interviews, built from their data, not before)
Upload the supplier-invoice export → see the declaration computed → see "next quarter's forecast fines: MAD X; financing them through partner Y costs MAD Z."

### Pilot proposal
- 1 quarter: we prepare the declaration plus a fine forecast for free or at a token price.
- In exchange: data access and a case study.
- Success = the declaration is accepted without correction, and the forecast lands within ±10% of actual fines.

### Pricing hypothesis [H]
- Compliance: MAD 1.5–5k per quarter per entity.
- Accounting firms: MAD 100–300 per client per quarter.
- Finance: a fee from the capital partner.

**All untested.**

### ROI model (template; parameters to be filled from a real customer)
- Late-invoice interest per Upsilon (S20): **BAM reference rate + 0.85% per month of delay [verify against the official text]**.
- Fine on an invoice ≈ amount × (reference rate/12 + 0.85%) × months late.
- Example **[H]**: MAD 10M of invoices paid 2 months late at a 2.25% reference rate (**illustrative, not a cited figure**) → 10M × (0.1875% + 0.85%) × 2 ≈ **MAD 207k in fines**.
- If on-time supplier finance costs 7%/year **[H]**: 10M × 7% × 2/12 ≈ **MAD 117k** → savings ≈ MAD 90k for that one batch.
- **The whole thesis rests on the gap between "fine" and "financing cost" being positive, so verify it first.**

### Validation targets (proposed, not achieved)
- 5 of 10 finance directors confirm they paid material fines **and** consider them a problem worth solving.
- 3 share one quarter of anonymized data.
- 2 accounting firms say they'd pay per client.
- 1 capital partner indicates willingness to fund.
- 1 paid pilot.

**Kill criteria:** most finance directors say fines are an accepted cost of their payment policy and financing doesn't beat them, **and** accounting firms say the DGI portal or Excel is enough.

## Opportunities 2–5 (condensed)

| Opportunity | Prospect profiles | First test |
|---|---|---|
| FiscAI PreClear | 10 customs brokers (Casablanca port, Tanger Med), 10 importers | "Last costly customs error?" interviews (see the earlier session) |
| E-invoicing middleware | Accounting firms, Odoo partners | Wait for the DGI decree; ask about integration pain |
| Payment-institution compliance | The about 31 BAM-licensed payment institutions (public list) | 5 compliance-officer interviews |
| Credit review for Maghreb microfinance institutions | Moroccan microfinance associations **[names to verify]** | Analyst time per file |
