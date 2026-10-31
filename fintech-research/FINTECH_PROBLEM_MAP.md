# Fintech Problem Map

Evidence strength: **A** = regulator or official data · **B** = multilateral body or reputable press · **C** = vendor or marketing source · **H** = hypothesis, not yet evidenced.

| Segment | Persistent problem (even after Stripe/Adyen/Wise etc.) | Who suffers | Evidence |
|---|---|---|---|
| A. Payments | Cross-border B2B and remittance costs stay high into Africa: SSA averages about 7.97% to send $200 vs a 6.49% global average (Q1 2025) | SMEs, migrants | B (S13, World Bank RPW via SARB deck) |
| A. Payments | Reconciliation of payouts, fees and refunds across PSPs and banks into the ERP is still done in spreadsheets | Finance ops at multi-PSP merchants | H / C |
| A. Payments | Chargeback and dispute handling is manual | Merchants | C |
| B. Banking infra | Emerging-market bank connectivity: no open-banking APIs, statements arrive as PDF/CSV/MT940 | Treasurers, accounting firms | H (Morocco has no PSD2 equivalent; to verify) |
| C. Lending | SME trade-finance rejection rate is 41%; global trade-finance gap is $2.5tn | Importers and exporters | B (S14, ADB 2025) |
| C. Lending | Morocco's MSME finance gap is $20.4bn, attributed to "weak risk architecture", not a shortage of capital | Moroccan SMEs | B (S15, IFC April 2026) |
| C. Lending | Factoring in Morocco serves mainly large accounts | Moroccan SME suppliers | C (S16, dated) |
| D. Fraud and identity | AML alerts: 90–95% false positives is the commonly cited figure, but weakly sourced | Bank compliance teams | C (S17) |
| D. Fraud and identity | Agent identity: who authorized the AI agent to pay? | Merchants, PSPs | B (S10–S12); crowded |
| E. Compliance | **Morocco Law 69-21: mandatory quarterly payment-terms declarations, fines on late invoices. MAD 1.331bn fines in 2025; 56,000+ declarants** | Every company above MAD 2M turnover, plus their accounting firms | **A/B (S18–S21)** |
| E. Compliance | **Morocco e-invoicing mandate, phased 2026–2028**: large companies, then SMEs, then micro-businesses. Decree and technical specs not final as of April 2026. | Same population | B/C (S22–S24) |
| E. Compliance | Exchange-control documentation for import/export payments (Office des Changes 2026 General Instruction; SARF platform from June 2026) | Importers, banks | A/B (S25) |
| F. Finance ops | AP/AR fragmentation: invoices, bank statements, ERP and payments don't reconcile | Mid-market finance teams | H |
| F. Finance ops | **Late payment hurts Moroccan suppliers**: SMEs/micro-businesses filed 95% of late-payment complaints in 2025. Client payment terms were about 98 days of revenue (year to verify). | Moroccan SME suppliers | A/B (S19, S21) |
| G. Insurance | Commercial-insurance brokerage is manual (a YC W26 company is attacking it) | Brokers, SMEs | C (S1) |
| H. Digital assets | Stablecoins as B2B settlement for emerging markets: YC RFS. In Morocco, Bill 42.25 is still under review, and stablecoin issuance would be limited to banks/payment institutions. | Importers, global SMEs | B (S2, S26) |
| I. New workflows | Agent spending controls, budgets and audit trails | Companies deploying agents | C; crowded |

## Key pattern

Most crowded problems (agent payments, AML triage, US AP automation) have **weak or vendor-only evidence and heavy competition**. The problem with the **strongest official evidence of a recurring, quantified cost** is Moroccan payment-terms compliance (Law 69-21). The e-invoicing mandate, the late-payment burden on suppliers and the SME finance gap all reinforce it.
