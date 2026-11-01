# AVENEL Expert Register (Moroccan Accounting & Tax)

Per Rule A.1:
> *"Never invent a domain rule. Read from `/jurisdiction/ma/*.yaml`. If missing, mark `status: needs_expert` with `TODO(EXPERT)` and disable."*

This register catalogs all domain items in AVENEL currently flagged `status: needs_expert` requiring formal validation by a qualified Moroccan Chartered Accountant (Expert-Comptable inscrit à l'Ordre des Experts-Comptables du Maroc).

---

## Catalog of Needs-Expert Rules

| Identifier / Domain Item | Jurisdiction Rule Key | Current Restrictive Choice / Default | OEC / Legal Reference Context | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Withholding Receivable Account** | `accounting.withholding.receivable_account` | `3457` (default suggestion in mapping UI) | CGNC (1989) does not explicitly code `3457`. Candidates in Class 3: `3452` (IS récupérable), `3453` (Acomptes), `3458` (Autres débiteurs). Mandatory mapping approval by firm accountant. | `needs_expert` (`TODO(EXPERT)`) |
| **Default Suspense Account** | `accounting.suspense.default_account` | `4711` ("Créditeurs divers - Comptes d'attente") | CGNC standard uses 4711 for operations to be regularized. Missing mapping requires manual resolution; cannot post automatically without accountant mapping. | `needs_expert` (`TODO(EXPERT)`) |
| **Default Bank Fee Account** | `accounting.bank_fees.default_account` | `6147` ("Services bancaires") | CGNC standard subgroup 6147. VAT deductible on banking commissions (10%) requires approved mapping direction `bank_fee`. | `needs_expert` (`TODO(EXPERT)`) |
| **Foreign Exchange Rounding Accounts** | `accounting.rounding.gain_account` / `loss_account` | `7331` (Gains de change) / `6331` (Pertes de change) vs `6588` | CGNC distinguishes exchange differences from commercial rounding differences. Requires confirmation of standard Moroccan practice. | `needs_expert` (`TODO(EXPERT)`) |
| **Bank Codes in Moroccan RIB** | `identifiers.rib.bank_codes` | List of 22 Moroccan banks / institutions | Known conflicts: 013 is BMCI (not BP), 022 is Société Générale Maroc (not CAM). Warning only; awaiting Bank Al-Maghrib official clearing directory. | `needs_expert` (`TODO(EXPERT)`) |
| **ICE Check-Digit Algorithm** | `identifiers.ice.check_digit` | Regex validation only (`^[0-9]{15}$`) | Official check digit formula not published in statutory texts. Check digit mismatches trigger a warning, never a rejection. | `needs_expert` (`TODO(EXPERT)`) |
| **Cash Payment Limits Base** | `vat.deduction.cash_limit` | TTC basis applied (conservative) | CGI Art. 106-II statutory wording does not explicitly clarify HT vs TTC basis for the 5,000 MAD / 50,000 MAD threshold. | `needs_expert` (`TODO(EXPERT)`) |

---

## Maintenance & Resolution Protocol
1. Any code attempting to automate these values without explicit tenant/client mapping MUST block or warn, never silently default.
2. When an Expert-Comptable or official DGI / Bank Al-Maghrib circular clarifies an entry, record the gazette or official circular reference in `/jurisdiction/ma/*.yaml`, set `status: verified`, and update this register.

