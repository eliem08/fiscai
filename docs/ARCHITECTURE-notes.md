# Architecture Notes — Role Authorization & Resource Scoping

## 1. Scope-First Authorization Rule (Part A & Part G Invariant)

To guarantee strict tenant isolation and zero information leakage across tenant and client boundaries:

### The Scope-First Invariant
1. **Out-of-Scope Resources return `404 Not Found`**:
   - Any attempt to access, list, read, or mutate a resource that belongs to another tenant returns `404 Not Found` (never `403 Forbidden` or `200 OK`).
   - For `client_user` members, any attempt to access a client entity or child resource (periods, chart of accounts, documents) outside their assigned `client_scope_ids` returns `404 Not Found`.
   - The API never reveals whether an out-of-scope resource ID exists.

2. **In-Scope Role Inabilities return `403 Forbidden`**:
   - When a resource is confirmed to exist and is within the caller's authorized scope, but the caller's role is not permitted to execute that specific action, the API returns `403 Forbidden`.
   - `operator` access is strictly read-only for support purposes. Any mutating endpoint invoked by an operator returns `403 Forbidden`.
   - `staff` members cannot modify client entities, archive companies, open/close accounting periods, or seed/import chart of accounts (`403 Forbidden`).
   - `client_user` members cannot mutate client master data, archive companies, manage accounting periods, or alter the chart of accounts even for their in-scope company (`403 Forbidden`).
   - `accountant` members cannot archive client entities (`403 Forbidden`), as archiving is reserved for firm owners and managers (`owner`, `manager`).

---

## 2. Role × Action Permission Matrix (Phase 1 Mutating Endpoints)

| Endpoint | Action | `owner` | `manager` | `accountant` | `staff` | `client_user` (in-scope) | `client_user` (out-of-scope) | `operator` |
|---|---|---|---|---|---|---|---|---|
| `POST /v1/client-entities` | Create client | ✅ 201 | ✅ 201 | ✅ 201 | ❌ 403 | ❌ 403 | N/A | ❌ 403 |
| `PUT /v1/client-entities/{id}` | Update client | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `PATCH /v1/client-entities/{id}` | Patch client | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/archive` | Archive client | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/periods` | Open period | ✅ 201 | ✅ 201 | ✅ 201 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/periods/{pid}/close` | Close period | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/chart-accounts/seed-cgnc` | Seed CGNC | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/chart-accounts/import` | Import chart | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |

---

## 3. Jurisdiction Pack Catalog (`/jurisdiction/ma/`)

All tax, accounting, and legal rules are read strictly from `/jurisdiction/ma/*.yaml` per Part A Rule 1 and Rule 2:

| Fichier | Objet et finalité | Citation légale source | Statut |
|---|---|---|---|
| `manifest.yaml` | Manifeste du pack fiscal marocain (version, dates, registre des fichiers) | Architecture AVENEL | verified |
| `pack.schema.json` | Schéma JSON Schema Draft 2020-12 validant chaque règle du pack | Architecture AVENEL | verified |
| `vat_rates.yaml` | Taux de TVA (20%, 14%, 10%, 7%, 0%) et transition LF 2024-2026 | CGI art. 89, 98, 99 | verified |
| `vat_deduction.yaml` | Conditions d'exercice du droit à déduction et prorata de déduction | CGI art. 101, 102, 104 | verified |
| `vat_filing.yaml` | Modalités et calendriers de déclaration mensuelle et trimestrielle | CGI art. 110, 111 | needs_expert |
| `vat_withholding.yaml` | Retenue à la source sur la TVA (fournisseurs de biens d'équipement et prestataires de services) | CGI art. 117-IV (LF 2024–2026) | verified |
| `invoice_mentions.yaml` | Mentions obligatoires sur factures d'achat et vente, tolérance arithmétique (0,01 MAD), interdiction TVA auto-entrepreneur | CGI art. 145-III, art. 89 / Loi 114-13 | verified |
| `identifiers.yaml` | Formats d'identifiants fiscaux marocains (ICE 15 chiffres, IF 1-8 chiffres, RC, CNSS, TP, RIB 24 chiffres) | DGI / OMPIC / CNSS | verified |
| `cgnc_seed.yaml` | Plan comptable général marocain standard (Classes 1 à 7) | CGNC (CNC 1989) référencé par Loi 9-88 | verified |
| `simpl_tva.yaml` | Structure XML SIMPL-TVA et nomenclature des modes de paiement | DGI Maroc (Télédéclaration SIMPL) | needs_expert |
| `compliance.yaml` | Conformité CNDP protection des données personnelles et DPA fiduciaire | Loi n° 09-08 / CNDP | verified |
| `oec_position.yaml` | Règles de déontologie OEC, secret professionnel et conservation décennale | Dahir 1-92-139 / Loi 9-88 art. 22 | verified |
| `einvoicing.yaml` | Calendrier et exigences de facturation électronique (mise en réserve) | DGI (en attente des décrets d'application) | needs_expert |
| `issues.yaml` | Catalogue exhaustif des codes d'anomalies, niveaux de sévérité et résolutions | Architecture AVENEL Part D.2 | verified |
| `corporate_tax.yaml` | Barème progressif de l'Impôt sur les Sociétés (IS) — Hors périmètre Phase 1-5 | CGI art. 19 | out_of_scope |
| `penalties.yaml` | Pénalités et majorations fiscales de retard — Hors périmètre Phase 1-5 | CGI art. 208 | out_of_scope |
| `social_charges.yaml` | Taux de cotisations sociales CNSS / AMO — Hors périmètre Phase 1-5 | Dahir 1-72-184 / CNSS | out_of_scope |

---

## 4. Gestion des Doublons Stricts (Exact Duplicates)

Conformément à la règle Phase 2 révisée :
- L'importation d'une pièce ayant une empreinte SHA-256 identique pour la même entreprise cliente ne renvoie pas d'erreur `409 Conflict`.
- Le point d'accès `POST /v1/work-requests/{id}/uploads` renvoie un code **`200 OK`** avec l'identifiant du document existant (`document_id`) et le statut `resubmitted`.
- Un événement d'audit immuable **`document.resubmitted`** est consigné dans la chaîne cryptographique `audit_events`.

---

## 5. Spécification des Erreurs HTTP et Bounding Boxes

- **Erreurs HTTP** : L'ensemble des réponses d'erreur respecte strictement la norme **RFC 9457** (*Problem Details for HTTP APIs*, remplaçant RFC 7807) sous le type MIME `application/problem+json`.
- **Boîtes englobantes (Bounding Boxes)** : Le format universel adopté à tous les niveaux du système (OCR, extraction, stockage, API et viewer UI) est **`[x0, y0, x1, y1]`** normalisé dans l'intervalle $[0.0, 1.0]$ :
  - `x0` : bord gauche normalisé ($0.0 \le x_0 \le 1.0$)
  - `y0` : bord supérieur normalisé ($0.0 \le y_0 \le 1.0$)
  - `x1` : bord droit normalisé ($x_0 \le x_1 \le 1.0$)
  - `y1` : bord inférieur normalisé ($y_0 \le y_1 \le 1.0$)

---

## 6. Résolution des Comptes de Taxe et Nomenclature des Règles TVA

### A. Résolution stricte par `client_tax_mappings`
- Les comptes de TVA ne sont jamais imputés directement par défaut sans approbation.
- Chaque imputation de TVA doit obligatoirement être résolue par la table `client_tax_mappings` pour l'entreprise cliente (`tenant_id`, `client_entity_id`, `tax_code`, `direction`) avec la condition impérative `approved_by IS NOT NULL`.
- Si aucun mapping approuvé n'existe pour un code de taxe et une direction donnés :
  - **Aucune ligne d'écriture n'est générée.**
  - Une anomalie bloquante de sévérité `blocking` est levée : **`ACCOUNT_UNMAPPED`**.
- Le pack fiscal peut fournir des suggestions de comptes par défaut dans l'interface utilisateur pour assister l'expert comptable (`get_suggested_tax_account_default`), mais celles-ci ne sont jamais appliquées automatiquement en base sans validation explicite.

### B. Correspondance des fichiers de règles TVA (`vat_rules.yaml`)
- Certaines références conceptuelles mentionnent `vat_rules.yaml`. Dans la structure effective du pack `/jurisdiction/ma/`, ces règles sont structurées en deux fichiers conformément à `ARCHITECTURE.md` :
  - `vat_rates.yaml` : Taux légaux (normal 20%, réduit 10%, historique 7%/14%) et calendrier de transition LF 2024–2026.
  - `vat_deduction.yaml` : Conditions d'exercice du droit à déduction, exclusions par nature (CGI art. 106-I), plafonds de règlement en espèces (CGI art. 106-II : 5 000 MAD/jour/fournisseur) et prorata de déduction (CGI art. 104).

---

## 7. Traçabilité des Références de Preuve (`evidence_refs` vs `rule_refs`)

Pour garantir une séparation stricte entre les pièces justificatives et les fondements réglementaires :
- **`journal_lines.evidence_refs`** : Doit contenir **exclusivement** des références à des régions de documents physiques (`document_version_id` ou `document_id`, `page`, `bbox`) ou des lignes de relevé bancaire (`bank_statement_line_id` ou `bank_transaction_id`).
  - Toute ligne d'écriture ne contenant que des références de règles sans repère physique est formellement **rejetée**.
- **`journal_proposals.rule_refs`** : Les fondements réglementaires et légaux (ex. `vat.rate.standard`, `cgnc.seed.accounts`, `vat.deduction.cash_limit.daily`, `vat.deduction.prorata`) sont stockés au niveau de l'entête de la proposition d'écriture dans le tableau typé `rule_refs text[]`.

---

## 8. Conversion de Devises et Gestion des Écarts d'Arrondi (Centimes)

- Les taux de conversion de devises sont stockés au niveau du tenant dans la table `fx_rates` (migration 004) avec `rate_date`, `currency`, `rate`, `source` (ex. fixing Bank Al-Maghrib).
- Tout document en devise étrangère dont le taux n'est pas saisi ou importé lève immédiatement l'anomalie bloquante **`FX_RATE_MISSING`** (aucun appel réseau en test ou production).
- Lors de la conversion en dirhams marocains (MAD) :
  - La ligne du tiers (fournisseur ou client) est **strictement égale au montant TTC de la facture converti au taux officiel**.
  - Tout écart résiduel arithmétique de centimes résultant des arrondis ligne par ligne est imputé sur une **ligne explicite d'arrondi**, jamais imputé sur le compte de tiers.
  - Le compte d'arrondi est résolu via `client_tax_mappings` (direction `'rounding'`) ou à défaut sur le compte CGNC par défaut du pack marqué `status: needs_expert` (`6588`).

---

## 9. Détection des Doublons Probables (`DUPLICATE_PROBABLE`)

- La règle de détection des doublons probables exige :
  $$\text{Même tiers} \land (\text{Même numéro de facture} \lor (\text{Même montant TTC} \land |\Delta_{\text{dates}}| \le \text{fenêtre du pack}))$$
- La fenêtre temporelle est lue dynamiquement depuis le pack : `invoice.duplicate_window_days` (20 jours).
- Code d'anomalie : **`DUPLICATE_PROBABLE`** (sévérité `review`).
- Deux fournisseurs différents ayant le même montant ne sont jamais signalés en doublon.
- Une facture récurrente (ex. loyer mensuel) avec des numéros différents espacés de 30 jours n'est pas signalée en doublon (dépassement de la fenêtre de 20 jours).

---

## 10. Approbation Exclusive au Niveau du Dossier Mensuel (Phase 5)

- Il n'existe **aucun point d'accès d'approbation unitaire par écriture** (`POST /v1/proposals/{id}:approve` est supprimé).
- L'approbation comptable intervient exclusivement au niveau global du dossier mensuel de révision (*Monthly File Review*, Phase 5 per Part G).
- Dans l'interface utilisateur de révision des propositions (`ProposalReview`), la touche `Entrée` permet uniquement de **confirmer la ligne focalisée** (toast : *« Ligne confirmée »*). Aucun chemin clavier ne permet de valider ou approuver une écriture.
- Les vérifications de rôles sont renommées pour cibler la permission **`edit_proposals`** (`owner`, `manager`, `accountant`).

---

## 11. Empreinte Numérique Déterministe (`subject_hash`) et Intégrité Cryptographique (D.4)

L'empreinte numérique du dossier mensuel (`subject_hash`) garantit l'intégrité absolue et l'immuabilité des écritures et rapprochements validés (Invariant #7).

### 11.1 Champs inclus dans le calcul du hachage
Le hachage est calculé via SHA-256 sur la sérialisation canonique JSON (clés triées, sans espace, montants décimaux formatés avec 2 décimales) des structures suivantes :

1. **Propositions comptables actives (`journal_proposals`)** (triées par `id`) :
   - `id` : identifiant UUID canonique de la proposition
   - `journal_code` : code journal comptable (`ACH`, `VTE`, `BQ`, `OD`)
   - `entry_date` : date comptable au format ISO-8601 (`YYYY-MM-DD`)
   - `label` : libellé de l'écriture
   - `source_document_id` : identifiant du document source ou `null`
   - `source_bank_transaction_id` : identifiant de la ligne bancaire source ou `null`
   - `rule_refs` : liste triée des références réglementaires appliquées
   - `lines` : lignes d'écriture ordonnées par `line_no` croissant :
     - `line_no` : numéro de ligne (entier $\ge 1$)
     - `account_code` : code du compte général CGNC (ex. `6111000`)
     - `label` : libellé de la ligne
     - `currency` : devise de transaction (`MAD`, `EUR`, `USD`)
     - `debit_mad` : montant débit en MAD avec 2 décimales
     - `credit_mad` : montant crédit en MAD avec 2 décimales
     - `counterparty_id` : identifiant du compte tiers auxiliaire ou `null`

2. **Rapprochements bancaires acceptés (`reconciliation_matches`)** (triés par `id`) :
   - `id` : identifiant UUID du rapprochement accepté
   - `difference_kind` : typologie de l'écart (`none`, `vat_withheld`, `bank_fee`, `fx`, `rounding`)
   - `difference_mad` : montant de l'écart avec 2 décimales
   - `items` : items constitutifs du match ordonnés par `(bank_transaction_id, journal_proposal_id)` :
     - `bank_transaction_id` : identifiant de la transaction bancaire ou `null`
     - `journal_proposal_id` : identifiant de la proposition liée ou `null`
     - `amount_mad` : montant rapproché en MAD avec 2 décimales

### 11.2 Champs volatils formellement exclus du hachage
Pour assurer que la transition d'état au moment de l'approbation n'altère pas l'empreinte :
- **`status`** : exclu (la proposition passe de `proposed` à `approved` sans modifier le `subject_hash`)
- **Horodatages** : `created_at`, `updated_at`, `decided_at`
- **Acteurs** : `decided_by`, `last_edited_by`
- **Compteurs de révision** : `revision`

### 11.3 Règle de décision et détection de fraîcheur
- Le corps de la requête `POST /v1/approvals/{id}:decide` exige obligatoirement le champ `subject_hash`.
- Si l'empreinte soumise ne correspond pas à l'empreinte recalculée en direct sur les propositions et rapprochements actifs, l'API renvoie une erreur `409 Conflict` (`ApprovalStaleError`).
- Toute modification ultérieure d'un rapprochement accepté ou d'une écriture entraîne le refus immédiat de l'export (`ExportHashMismatchError`, Invariant #7).

