# Builds FINTECH_OPPORTUNITY_RANKING.md and .xlsx from one source of truth.
# Scores are analyst judgements (0-10) based on the evidence in CUSTOMER_PAIN_DISCOVERY.md.
import os

W = dict(pain=15, freq=10, wtp=15, market=10, white=15, reach=10, tech=10, reg=5, timing=5, defe=5)
COLS = list(W)

# (id, name, customer, region, scores dict, fatal flag or "", rationale)
O = [
 (1, "69-21 payment-terms compliance + fine forecasting → supplier finance", "Companies > MAD 2M turnover; fiduciaires", "Morocco",
  dict(pain=8,freq=9,wtp=7,market=6,white=7,reach=7,tech=8,reg=7,timing=9,defe=6), "",
  "Official data: MAD 1.33bn fines 2025, 56k declarants, quarterly. Sage module exists; finance layer is the moat."),
 (2, "FiscAI PreClear: customs/VAT dossier pre-check", "Customs brokers (transitaires), importers", "Morocco",
  dict(pain=6,freq=6,wtp=5,market=5,white=7,reach=6,tech=5,reg=8,timing=6,defe=5), "",
  "No public frequency/cost data; buyer unclear; depends on document-AI quality."),
 (3, "Moroccan e-invoicing compliance middleware (DGI CTC)", "Mid-market, ERPs, fiduciaires", "Morocco",
  dict(pain=7,freq=9,wtp=6,market=6,white=4,reach=6,tech=6,reg=7,timing=8,defe=3), "",
  "Forced, but specs not final and Edicom/Comarch/Sage will commoditize it."),
 (4, "Reverse factoring marketplace for Moroccan large buyers", "Large buyers + suppliers + factors", "Morocco",
  dict(pain=7,freq=8,wtp=7,market=7,white=6,reach=4,tech=6,reg=4,timing=7,defe=7), "",
  "Strong economics; needs licensed partners; enterprise sales. Best as phase 2 of #1."),
 (5, "Supplier-side late-payment recovery & dunning (relances + legal interest)", "SME suppliers", "Morocco",
  dict(pain=7,freq=8,wtp=4,market=6,white=6,reach=6,tech=8,reg=8,timing=6,defe=3), "",
  "SMEs file 95% of complaints, but low WTP; relationship fear with clients."),
 (6, "Import FX & payment documentation automation (Office des Changes)", "Importers, banks' trade desks", "Morocco",
  dict(pain=6,freq=7,wtp=5,market=5,white=6,reach=4,tech=6,reg=5,timing=7,defe=5), "",
  "SARF/2026 Instruction changes the workflow; banks are gatekeepers."),
 (7, "Stablecoin cross-border supplier payments (MA→CN/EU)", "Importers", "Morocco/MENA",
  dict(pain=7,freq=8,wtp=7,market=7,white=6,reach=5,tech=6,reg=1,timing=4,defe=5), "Regulatory: Bill 42.25 not enacted; crypto not a means of payment",
  "Fatal today for a non-bank in Morocco; monitor."),
 (8, "Bank-statement normalization API for N. African banks", "Fintechs, accounting software", "Maghreb",
  dict(pain=6,freq=8,wtp=5,market=5,white=7,reach=5,tech=6,reg=7,timing=5,defe=6), "",
  "Real data gap [H], infra buyer small in Morocco."),
 (9, "Credit-review automation for emerging-market lenders", "MFIs, digital lenders", "Global EM",
  dict(pain=7,freq=8,wtp=7,market=7,white=4,reach=5,tech=6,reg=7,timing=7,defe=5), "",
  "Already a YC W26 company; competition."),
 (10, "AML alert investigation copilot for small banks/PSPs", "Compliance teams", "Global",
  dict(pain=7,freq=9,wtp=7,market=8,white=2,reach=4,tech=6,reg=6,timing=6,defe=4), "",
  "Crowded: Lucinity, Flagright, Facctum, Fenrock (YC W26)..."),
 (11, "Compliance stack for newly licensed Moroccan payment institutions (31 licensees)", "Payment institutions", "Morocco",
  dict(pain=7,freq=8,wtp=7,market=3,white=6,reach=7,tech=6,reg=6,timing=7,defe=5), "",
  "Small customer count (~31) caps the market."),
 (12, "Agent payment authorization / spend controls", "Companies deploying agents", "US",
  dict(pain=5,freq=7,wtp=5,market=8,white=2,reach=4,tech=7,reg=6,timing=8,defe=3), "",
  "Visa/Stripe/Mastercard/Coinbase + many startups."),
 (13, "Agent identity (KYA)", "Merchants, PSPs", "US",
  dict(pain=5,freq=6,wtp=4,market=7,white=3,reach=3,tech=6,reg=6,timing=8,defe=5), "",
  "Skyfire et al.; real volume still tiny."),
 (14, "Multi-PSP payout reconciliation for marketplaces", "Marketplaces", "Global",
  dict(pain=7,freq=9,wtp=7,market=7,white=3,reach=5,tech=6,reg=8,timing=5,defe=4), "",
  "Modern Treasury, Ledge, Stripe Recon... crowded."),
 (15, "Trade-document verification for trade-finance banks (LC/doc check)", "Bank trade desks", "Global/EM",
  dict(pain=7,freq=8,wtp=7,market=7,white=5,reach=3,tech=5,reg=7,timing=6,defe=6), "",
  "Long bank sales cycles; Traydstream, Conpend exist."),
 (16, "Embedded invoice financing inside Moroccan POS/merchant apps", "Small merchants", "Morocco",
  dict(pain=6,freq=7,wtp=5,market=6,white=4,reach=4,tech=6,reg=3,timing=6,defe=5), "",
  "Chari (licensed, $12M Series A) adjacent."),
 (17, "Mobile-money interoperability for SSA SMEs", "SMEs", "SSA",
  dict(pain=7,freq=9,wtp=5,market=8,white=3,reach=3,tech=5,reg=3,timing=5,defe=5), "",
  "PAPSS, Onafriq, Flutterwave; needs licences."),
 (18, "Tax-compliance copilot for Maroc fiduciaires (all DGI filings)", "Accounting firms", "Morocco",
  dict(pain=6,freq=8,wtp=5,market=5,white=5,reach=7,tech=6,reg=8,timing=6,defe=4), "",
  "Broad; fiduciaires price-sensitive; overlaps #1 as a channel."),
 (19, "Insurance premium reconciliation for brokers", "Brokers", "Global",
  dict(pain=6,freq=8,wtp=6,market=5,white=5,reach=4,tech=6,reg=7,timing=4,defe=4), "", "Niche, weakly evidenced."),
 (20, "Claims document fraud detection (genAI-forged docs)", "Insurers", "Global",
  dict(pain=7,freq=7,wtp=7,market=7,white=4,reach=3,tech=5,reg=6,timing=8,defe=5), "", "Shift Technology etc."),
 (21, "Bank back-office AI agents", "Banks", "Global",
  dict(pain=7,freq=9,wtp=8,market=8,white=3,reach=2,tech=5,reg=4,timing=7,defe=5), "", "YC W26 has one; enterprise sales."),
 (22, "SME cash-forecasting from bank + invoice data", "SMEs", "Morocco",
  dict(pain=5,freq=8,wtp=3,market=6,white=5,reach=5,tech=6,reg=8,timing=5,defe=3), "No economic buyer at SME level", "Nice-to-have."),
 (23, "Remittance-to-SME-credit scoring (diaspora flows)", "Lenders", "Morocco",
  dict(pain=5,freq=6,wtp=5,market=6,white=6,reach=3,tech=5,reg=3,timing=5,defe=6), "Data access depends on banks/MTOs", "Data inaccessible."),
 (24, "Public-procurement supplier finance (marchés publics)", "SME suppliers to the State", "Morocco",
  dict(pain=7,freq=6,wtp=6,market=6,white=5,reach=4,tech=6,reg=4,timing=5,defe=5), "", "Public payment delays improving (16.2 days state, 2025)."),
 (25, "Sanctions/KYB for MENA SMEs exporting to EU", "Exporters", "MENA",
  dict(pain=5,freq=5,wtp=5,market=5,white=4,reach=4,tech=6,reg=6,timing=6,defe=4), "", "Weak evidence."),
 (26, "Exchange-bureau digital compliance (post circular 3/2025)", "Bureaux de change", "Morocco",
  dict(pain=5,freq=8,wtp=4,market=3,white=4,reach=5,tech=6,reg=5,timing=7,defe=3), "", "NAPS/Attijari Payment already moving."),
 (27, "Tokenized receivables for MENA (on-chain factoring)", "Funds, SMEs", "MENA",
  dict(pain=6,freq=6,wtp=5,market=6,white=5,reach=3,tech=4,reg=1,timing=4,defe=5), "Regulatory: DeFi excluded, bill pending", "Fatal today."),
 (28, "AP automation for Moroccan mid-market (OCR + approval)", "DAF", "Morocco",
  dict(pain=6,freq=9,wtp=5,market=6,white=5,reach=5,tech=6,reg=8,timing=6,defe=3), "", "Generic; better as part of #1."),
 (29, "Chargeback/dispute automation for EM merchants", "E-commerce merchants", "MENA",
  dict(pain=5,freq=7,wtp=5,market=5,white=5,reach=4,tech=6,reg=7,timing=4,defe=3), "", "Low card chargeback culture in Morocco [H]."),
 (30, "Regulatory-change monitoring for Maghreb finance teams", "DAF, compliance", "Maghreb",
  dict(pain=4,freq=6,wtp=3,market=4,white=5,reach=5,tech=7,reg=8,timing=5,defe=3), "No proven WTP", "Info product; low WTP."),
]

def score(s): return round(sum(s[k]*W[k] for k in COLS)/10, 1)
rows = sorted(((score(s),) + o for o in O for s in [o[4]]), key=lambda r: -r[0])

here = os.path.dirname(os.path.abspath(__file__))
md = ["# Fintech Opportunity Ranking (30 opportunities)", "",
      "Weights: pain 15 · frequency 10 · WTP 15 · market 10 · whitespace 15 · reach 10 · tech 10 · regulatory 5 · timing 5 · defensibility 5. Score /100.",
      "Scores are analyst judgements from the evidence files, not measurements. **Fatal flags override scores.**", "",
      "| Rank | Score | # | Opportunity | Customer | Region | " + " | ".join(COLS) + " | Fatal flag | Rationale |",
      "|" + "---|" * (8 + len(COLS))]
for i, (sc, id_, name, cust, reg, s, fatal, why) in enumerate(rows, 1):
    md.append(f"| {i} | {sc} | {id_} | {name} | {cust} | {reg} | " + " | ".join(str(s[k]) for k in COLS) + f" | {fatal or '—'} | {why} |")
open(os.path.join(here, "FINTECH_OPPORTUNITY_RANKING.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")

try:
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Ranking"
    ws.append(["Rank", "Score", "#", "Opportunity", "Customer", "Region"] + COLS + ["Fatal flag", "Rationale"])
    ws.append(["", "weights", "", "", "", ""] + [W[k] for k in COLS] + ["", ""])
    for i, (sc, id_, name, cust, reg, s, fatal, why) in enumerate(rows, 1):
        r = ws.max_row + 1
        ws.append([i, None, id_, name, cust, reg] + [s[k] for k in COLS] + [fatal, why])
        # live formula so users can re-weight in Excel
        ws.cell(row=r, column=2).value = f"=SUMPRODUCT(G{r}:P{r},$G$2:$P$2)/10"
    wb.save(os.path.join(here, "FINTECH_OPPORTUNITY_RANKING.xlsx")); print("xlsx ok")
except ImportError:
    print("openpyxl missing: xlsx skipped")
for r in rows[:12]: print(r[0], r[1], r[2])
