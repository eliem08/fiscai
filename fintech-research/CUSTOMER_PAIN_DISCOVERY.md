# Customer Pain Discovery

> No customer interviews were conducted. All evidence is public. Community mining (Reddit, G2, Capterra) was **not** done systematically in this pass. Quotes are only used where a source states them. The ten fields are: problem · who · frequency · impact · workaround · software · why insufficient · evidence · willingness to pay (WTP) · trend.

## P1. Moroccan payment-terms compliance (Law 69-21) — strongest evidence

| Field | Finding |
|---|---|
| Problem | Companies must compute supplier-payment delays invoice by invoice, file a declaration every quarter (including a nil declaration), file a detailed statement of unpaid invoices, and pay fines on late invoices. Applies to all invoices since 1 Jan 2025; quarterly declarations from Q1 2026 for the MAD 2–10M band (S20, S23). |
| Who | Every company with turnover excluding VAT of MAD 2M or more (DGI position, 27 Mar 2026, reportedly extended to holdings, SCPs and individuals: S20, S21), plus the accounting firms (fiduciaires) that file for them |
| Frequency | Quarterly declaration, plus a per-invoice obligation |
| Impact | **MAD 1.331bn in fines in 2025** (S19). Large companies' fines fell from MAD 1.310bn to 1.018bn (2024→25). Large companies made up 82.7% of declared late invoices (MAD 43.98bn). Public companies paid MAD 423.2M. Declaration-failure penalties range from MAD 5,000 to 250,000 (S21). |
| Workaround | Excel exports from the ERP; the accounting firm computes by hand; consultancies (Upsilon) |
| Software | Sage Maroc compliance module (launched Oct 2023: reporting, automation, e-filing; S27); ERP localizations **[H: Odoo partners, to verify]** |
| Why insufficient | **[H]** Only helps Sage users. Computes after the fact rather than forecasting fines. Doesn't help the company actually pay on time. |
| Evidence | A (Observatory annual report on finances.gov.ma, S19), B (press) |
| WTP | Indirect: fines are paid in cash, and companies already pay consultancies **[H: no price data found]** |
| Trend | **Increasing scope** (threshold lowered to MAD 2M, more entity types). Fines decreasing, as companies comply better (S19). The fine pool is shrinking over time. |

## P2. Moroccan e-invoicing mandate (2026–2028)

| Field | Finding |
|---|---|
| Problem | Issuing and receiving compliant electronic invoices through the DGI platform. A CTC (real-time clearance) model is expected. Format: UBL (some sources say UBL+CII). |
| Who | Large companies first, then SMEs, then micro-businesses (S24) |
| Status | Finance Law 2026, CGI art. 145-IX. Implementing decree pending as of April 2026; specs and certification rules not finalized (S22) |
| Software | Edicom, Comarch, Sage, Upsilon, Inyad (S22–S24); more global vendors will come |
| Implication | Forced adoption, but it will become a commodity. Its value here is as a **data source** (structured invoices with due dates) for the payment-terms and finance layers. |

## P3. Late payment and working-capital stress on Moroccan suppliers

- SMEs/micro-businesses filed 95% of late-payment complaints in 2025 (S19).
- Client payment terms: about 98 days of revenue vs 125 in 2023 (Observatory; the year is ambiguous in press, S21).
- Morocco's MSME finance gap is $20.4bn (S15).
- Factoring outstanding is about MAD 12bn in 2025 (vendor guide, S16; weak source).
- Existing factors focus on large accounts (dated, S16).
- **WTP:** suppliers pay factoring discounts today. The buyer side pays fines. **Both sides already spend money on this problem.**

## P4. Customs/VAT dossier errors for importers (FiscAI PreClear's thesis)

- No public data found on how often errors happen or what they cost in Morocco. **Evidence is weak (H).**
- Requires interviews with customs brokers (see the earlier session).

## P5. Cross-border payments into Africa

- SSA remittance cost is about 7.97% for $200, the highest region (S13).
- B2B evidence is less clear.
- In Morocco, import payments are bank-routed with justification documents (S28, S29; dated). Bill 42.25 is not enacted (S26).
- Pain is real; **access is blocked by regulation for a non-bank startup.**

## P6. AML false positives

- 90–95% is widely repeated, but traces to a 2018 PwC figure via vendor blogs (S17).
- Real, but crowded (Lucinity, Flagright, Facctum, NICE Actimize, YC W26 Fenrock AI…).

## P7. Agent payments and identity

- Real emerging need, but mostly tests so far (x402 at about $28k/day, S11).
- Dominated by networks and Stripe.
