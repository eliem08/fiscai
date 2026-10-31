# Top 10 Opportunities — Deep Dive and Challenge

Ranked from `FINTECH_OPPORTUNITY_RANKING.md`. Opportunity #7 (stablecoin supplier payments) scored 61, but is **excluded from the top 10 by its fatal regulatory flag** and moved to "monitor". Market sizes use only cited figures. Anything else is marked [H].

---

## 1. 69-21 payment-terms compliance → supplier finance (score 74)

### Customer
- **ICP:** Moroccan companies with turnover above MAD 50M and many suppliers (industry, distribution, construction, retail).
- **Economic buyer:** finance director (DAF/CFO).
- **Daily user:** AP accountant or credit manager.
- **Second channel:** accounting firms (fiduciaires) filing for SMEs in the MAD 2–50M band.
- **Buying trigger:** the quarterly deadline, a fine received, or an audit.
- **Existing vendors:** Sage, ERP integrators, auditors.
- **Switching barrier:** low for the declaration; high once financing is embedded.

### Workflow today [H, to confirm in interviews]
1. Export supplier invoices and payments from the ERP.
2. Match payments to invoices (partial payments, credit notes, disputes).
3. Determine the applicable term: 60 days by default, 120 days by agreement, or 180 days for some sectors.
4. Compute the days late per invoice.
5. Compute the fine.
6. Fill in the DGI declaration, including nil declarations.
7. Pay the fine.

**Errors:** wrong term applied, disputed invoices, wrong invoice dates. **Consequence:** fines, plus penalties of MAD 5k–250k for declaration failures.

### Product fit
- Connect to the ERP export or accounting files.
- Compute and file the declaration.
- **Forecast next quarter's fines invoice by invoice.**
- Recommend: pay now, extend the term contractually, or finance through a partner.

### Market (cited figures only)
- 56,000+ declarants (S19).
- MAD 1.331bn fines in 2025 (S19), shrinking as compliance improves.
- Pricing per declarant: **[H]** MAD 2k–20k/year depending on size → ARR potential [H] depends on adoption; not computed without real pricing evidence.
- Finance layer: MAD 43.98bn of late invoices declared by large companies in 2025 (S19) is the pool of invoices a pay-on-time product could address. A 1–2% take-rate is **[H]**.

### Business model
SaaS per entity, plus a finance take-rate (origination fee from partner factor/bank) or a share of the discount.

### Defensibility
- Rule engine for 69-21 and e-invoicing.
- ERP connectors.
- **Invoice-level payables data across buyers and suppliers** (network effect: suppliers of many buyers).
- Factor/bank partnerships.

### Challenge (why it could fail)
1. Sage or the DGI portal makes the declaration free and good enough → you must reach the finance layer fast.
2. Large companies pay late **on purpose** (it's their working capital) and accept fines as a cost; financing must be cheaper than the fine **[H: must verify the fine formula vs bank rates]**.
3. Finance partnership or licensing is slow.
4. The fine pool is shrinking (1.310 → 1.018bn for large companies, 2024→25).

**Verdict: still #1.** The problem is official, quantified and recurring, and both sides already spend money on it.

---

## 2. Reverse-factoring marketplace for large Moroccan buyers (64)

Phase 2 of #1. Standalone, it needs enterprise sales and licensed capital with no data advantage. **Merged into #1.**

## 3. Compliance stack for Moroccan payment institutions (63)

- About 31 licensees, growing (S30).
- Real need (AML, BAM reporting).
- **Market capped by customer count.** Viable services business, weak venture case.

## 4. Credit-review automation for EM lenders (62.5)

- Good YC fit, but a YC W26 company already does it (S1).
- Would need a sharp geographic or segment focus (Maghreb microfinance institutions **[H]**).

## 5. Supplier-side late-payment recovery (62)

- Pain is real: 95% of complaints come from SMEs (S19).
- Weak willingness to pay, and suppliers fear damaging client relationships.
- **Better as the supplier-side entry of #1.** A supplier who sees its buyer on the platform gets paid sooner.

## 6. Moroccan e-invoicing middleware (61.5)

- Forced by law.
- Commoditized by global vendors once specs are published.
- **Use as the data pipe for #1, not as the business.**

## 7. Multi-PSP payout reconciliation (61)

Crowded globally. No local edge. Deprioritized.

## 8. Trade-document verification for trade-finance banks (61)

- 41% SME rejection rate in trade finance (S14).
- Long bank sales cycles. Traydstream and others exist.
- Overlaps FiscAI's document know-how. **Alternative path for FiscAI.**

## 9. Bank-statement normalization API, North Africa (60)

- Infrastructure need **[H]**, but the buyers (local fintechs) are few.
- **Build internally for #1** if needed.

## 10. AML copilot for small banks/PSPs (59)

Crowded (S17). Deprioritized.

### (Below the cut) FiscAI PreClear — customs/VAT pre-check (58.5, rank 14 of 30)

Kept as **Alternative 1**: the product exists and the domain is the same (Moroccan DGI/ADII compliance). But its pain is **not yet evidenced**, while #1's pain is officially measured.

---

## Top-3 challenge round

| | #1 69-21 → finance | Alt: FiscAI PreClear | Alt: e-invoicing middleware |
|---|---|---|---|
| Official evidence of pain | Strong (Observatory annual report) | None found | Strong (law), but cost is compliance, not a loss |
| Money already spent | Fines (MAD 1.33bn) + factoring discounts | Penalties, demurrage (unquantified) | Vendor fees (future) |
| Competition | Sage module, consultants | None found (unverified) | Many global vendors |
| Path to venture scale | Finance layer + regional rule packs | Narrow (importers × customs brokers) | Commodity |
| Biggest unknown | Will buyers pay to avoid fines, or simply accept them? | Error frequency | Final DGI specs |

**Bias check:** #1 was found during this session's research and Morocco was studied more deeply, so its score may be inflated. The interviews in `FIRST_CUSTOMER_STRATEGY.md` are designed to **disprove** it first.
