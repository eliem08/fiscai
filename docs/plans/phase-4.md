# Phase 4 Plan — Bank and Reconciliation

## 1. Goal
Implement Phase 4 according to `ARCHITECTURE.md` (Version 2.0, 30 October 2026, Part G) and Part A mandatory rules, following completion of all four review items.

---

## 2. Pre-Phase-4 Review Items

### Item 1: FX Rounding (`rounding_loss` and `rounding_gain`)
- **Migration 005 (`005_rounding_directions`)**:
  - Update `client_tax_mappings.direction` check constraint to include `'rounding_loss'` and `'rounding_gain'`.
  - Provide complete down migration for rollback.
- **Jurisdiction Pack Defaults**:
  - `accounting.fx_rounding.loss_account`: "6331", marked `status: needs_expert`, `TODO(EXPERT)`.
  - `accounting.fx_rounding.gain_account`: "7331", marked `status: needs_expert`, `TODO(EXPERT)`.
- **Conversion Logic**:
  - Positive residual ($\sum \text{debits} < \sum \text{credits}$) $\to$ debit `rounding_loss` account.
  - Negative residual ($\sum \text{debits} > \sum \text{credits}$) $\to$ credit `rounding_gain` account.
- **Golden Test**:
  - Facture en devise étrangère où le résidu est négatif, crédité au compte de gain de change.

### Item 2: Multi-rate Invoice Date Check & 14% Transitional Rate
- **Jurisdiction Pack**:
  - `vat.rate.reduced_14`: `effective_from: "2024-01-01"`, `effective_to: "2025-12-31"`.
- **Date-Aware Validation**:
  - Facture avec taux de TVA à 14% datée du `2025-12-31` $\to$ acceptée.
  - Facture avec taux de TVA à 14% datée du `2026-01-01` $\to$ anomalie bloquante `VAT_RATE_UNKNOWN`.
- **Golden Tests**:
  - Préciser la date de facture sur le test multi-taux.
  - Ajouter les tests spécifiques sur la frontière 2025/2026.

### Item 3: Suppression des citations légales typées dans le code et les tests
- Supprimer les mentions codées en dur (ex. « CGI art. 106-I », « CGI art. 89 ») dans les commentaires et tests.
- Utiliser exclusivement les clés de règles du pack juridique (`vat.deduction.exclusions_by_nature`, `vat.deduction.cash_limit.daily`, `invoice.auto_entrepreneur.vat_forbidden`).
- Source auto-entrepreneur : marquer `status: needs_expert` avec `TODO(EXPERT)` (« art. 91 vs 89 à confirmer »).

### Item 4: Account Suggester (LLM, Résidence, Runs & Faible Confiance)
- Documenter formellement l'utilisation du LLM (heuristique déterministe + historique de contrepartie par défaut).
- Si appel LLM : obligation de transiter par le routeur de résidence et de consigner une entrée dans `agent_runs`.
- Si la confiance est inférieure au seuil du pack (`accounting.suggestion.confidence_threshold: 0.75`) $\to$ lever `ACCOUNT_LOW_CONFIDENCE` (`review`).
- Test avec politique `MA_ONLY` sans modèle local disponible $\to$ repli exclusif sur l'historique des tiers.

---

## 3. Phase 4 Implementation Details

### 3.1 Validation du RIB Marocain (`avenel/bank/rib.py`)
- RIB marocain sur 24 chiffres :
  - 3 chiffres code banque
  - 3 chiffres code localité / guichet
  - 16 chiffres numéro de compte
  - 2 chiffres clé de contrôle (modulus 97)
- Chiffrement symétrique du RIB (`rib_encrypted`), hash SHA-256 (`rib_sha256`) et 4 derniers chiffres masqués (`rib_last4`).

### 3.2 Analyse des relevés bancaires (`avenel/bank/parser.py`, `avenel/bank/service.py`)
- Formats pris en charge : PDF, CSV, XLSX.
- Invariant fondamental de contrôle de solde :
  $$\text{Solde initial} + \sum \text{Mouvements} = \text{Solde final}$$
- Si l'écart est non nul $\to$ `balance_check = 'break'` et anomalie bloquante `BANK_BALANCE_BREAK`.

### 3.3 Moteur de rapprochement bancaire (`avenel/reconciliation/matcher.py`, `avenel/reconciliation/service.py`)
- Génération déterministe des candidats : montant, fenêtre de dates, tokens du tiers, références.
- Rapprochement avec retenue à la source de TVA (`vat_withheld`) :
  - Encaissement inférieur au TTC d'un montant égal à 75% ou 100% de la TVA de la facture.
  - `difference_kind = 'vat_withheld'`.
  - Écriture d'imputation au compte de créance de retenue (`client_tax_mappings` direction `'withholding'`).
  - Absence de mappage $\to$ `ACCOUNT_UNMAPPED` (bloquant).
- Types d'écarts gérés : `vat_withheld`, `bank_fee`, `fx`, `rounding`, `unexplained`.
- Rapprochements scindés (split) et groupés (grouped) via `reconciliation_match_items`.
- **Règle absolue d'exclusion** : Aucune ligne bancaire ne peut appartenir à deux rapprochements acceptés.
- Lignes bancaires non rapprochées $\to$ `BANK_LINE_UNMATCHED` (`review`).

### 3.4 Interface de rapprochement (`src/components/domain/ReconciliationScreen.tsx`)
- Disposition deux colonnes respectant Part E :
  - Colonne gauche : lignes bancaires.
  - Colonne droite : propositions / pièces candidates.
  - Colonne d'écart affichant la qualification de la différence.

---

## 4. Exit Criteria Phase 4
- **Balance-break fixtures detected** (`BANK_BALANCE_BREAK`).
- **Withheld-VAT fixtures matched with correct difference kind** (`vat_withheld`).
- **No bank line in two accepted matches**.
- **Tous les contrôles qualité au vert** (`make lint test typecheck openapi-lint rls-check audit-verify`).
