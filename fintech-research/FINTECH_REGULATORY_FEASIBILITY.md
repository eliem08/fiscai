# Regulatory and Operational Feasibility

> **Not legal advice.** The classification below is a working hypothesis that must be confirmed by a Moroccan financial-regulation lawyer before building any finance feature.

## Activity classification

| Activity | Category | Morocco implication | Our path |
|---|---|---|---|
| Computing and preparing 69-21 declarations | Software supporting a legal obligation | No financial licence expected **[H]**. The declaration itself is filed by the company or its accountant. | Launch immediately |
| E-invoicing transmission to DGI | Possibly certified-provider status, depending on the final decree (certification rules not finalized, S22) | Watch the decree | Integrate certified providers first |
| Showing financing offers from partners | Referral / introduction | May fall under the "intermediary in banking operations" (IOB) regime under banking law 103-12 **[H: verify]** | Partner-branded referral; legal opinion first |
| Offering factoring ourselves | Regulated credit activity | Requires BAM approval as a credit or finance institution **[H]** | **Not in scope** |
| Holding or moving client funds | Payment institution | BAM licence (about 31 licensees, S30) | **Not in scope**; partner with a licensed payment institution if needed |
| Stablecoin settlement | Bill 42.25 pending; issuance limited to banks/payment institutions (S26) | Not available | Monitor |
| Automated credit decisions | Partner's responsibility | Partner bears credit risk and decisions | Provide data, not decisions |

## Data and operations
- **Personal data:** Morocco's Law 09-08, supervised by the CNDP. Declaration needed for processing; cross-border transfers restricted **[H: verify for cloud hosting outside Morocco]**.
- **Bank/financial secrecy:** applies to partners, so data-sharing agreements are needed.
- **Record retention:** accounting records retained per the Commercial Code and CGI **[H: 10 years commonly cited; verify]**.
- **Auditability:** every computation and declaration must be traceable. FiscAI's audit-log design is directly reusable.
- **Third-party risk:** banks will run vendor due diligence (security, hosting, continuity). Plan ISO 27001-style controls by month 6–12.

## Conclusion
- **Phase 1** (compliance SaaS) needs no financial licence **[H, high confidence]**.
- **Phase 2** (finance) is feasible **only through licensed partners**, after a legal opinion on intermediary status.
- This is the right order: earn the data first, then add finance.
