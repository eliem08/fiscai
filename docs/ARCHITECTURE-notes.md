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


