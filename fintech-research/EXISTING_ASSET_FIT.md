# Existing Asset Fit

> Assessed **after** ranking. Only the FiscAI PreClear repository was inspected. Other repositories mentioned in the brief (agent observability, governance, replay/eval, data quality, port operations) were **not inspected** in this pass. The fit for those is a hypothesis.

## FiscAI PreClear (this repo)

| Component | Reusable for the primary thesis? | Notes |
|---|---|---|
| Rule-engine pattern (`src/lib/riskScoring.ts`, `checklist.ts`, `alertRules.ts`) | **Yes (pattern)** | Pure, tested rule functions. The same shape is needed for 69-21 rules (term selection, days late, fine computation). |
| Audit log (`auditLogService`) | **Yes** | Traceability is a must-have for declarations |
| Report builder + disclaimer | Yes | Declaration summary / fine-forecast report |
| Org/role model, auth guards | Yes (UI-level only) | Needs a real backend anyway |
| Document extraction mock | Partly | Real need is ERP/CSV ingestion, not OCR |
| French/English i18n (half-finished) | Yes | Finish or drop |
| Mock backend (`db.ts`, localStorage) | **No** | Real product needs a server, a database and security |
| Customs/VAT findings | No (different domain) | Keep for Alternative 1 |

**Effort estimate [H]:** a 69-21 calculator MVP (CSV in → declaration + fine forecast out) is about 2–3 weeks for one developer, reusing the rule-engine pattern, the audit log and the UI shell.

**Is reuse a real advantage?** It is a small one: UI shell, tests and audit patterns. **The hard parts are new:** Moroccan legal rules, ERP connectors, finance partnerships. Do not choose this thesis because the code exists. It was ranked first before the repo was considered.

## Other repositories (not inspected)
- **Agent observability / governance / replay:** likely irrelevant for phase 1. Possibly useful later for auditable AI-assisted invoice matching **[H]**.
- **Data quality tooling:** possibly relevant for messy ERP exports **[H]**.
- **Port and trade operations:** relevant to Alternative 1 (FiscAI) and opportunity #8 (trade documents) **[H]**.
