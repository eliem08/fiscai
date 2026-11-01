# Phase 5 Plan — Validation et Exportation (Approval and Export)

## 1. Objectif
Mettre en œuvre la **Phase 5** conformément à `ARCHITECTURE.md` (Version 2.0, 30 octobre 2026, Partie G) et aux règles obligatoires de la Partie A, après avoir finalisé tous les prérequis validés de la Phase 4.

La Phase 5 constitue le point de convergence de l'ensemble du cycle comptable d'AVENEL :
1. **Contrôles qualité et cycle des anomalies (Quality Check & Issue Workflow)** : vérification qu'aucune anomalie bloquante (`blocking`) ne subsiste avant soumission pour validation.
2. **Demandes clients dans le portail (Client Requests)** : demandes d'explication ou de justificatifs rattachées aux anomalies ou lignes bancaires/factures, résolues par le client ou l'expert.
3. **Validation formelle avec empreinte numérique (`subject_hash`) et séparation des tâches (Segregation of Duties)** :
   - Calcul de l'empreinte canonique SHA-256 (`compute_proposal_set_hash`) de l'ensemble des propositions du dossier mensuel.
   - Contrôle strict de la séparation des fonctions : le préparateur ne peut pas valider son propre dossier, sauf si la politique `single_person_policy` est activement configurée pour le cabinet.
   - Exigence légale marocaine : l'approbateur doit disposer d'un numéro d'inscription à l'Ordre (`professional_registration_number`).
4. **Exportateurs comptables certifiés** :
   - Sage 100 CSV (encodage Windows-1252 / CP1252, délimiteur point-virgule, colonnes Sage standard).
   - Sage 100 PNM (format d'import natif Sage 100).
   - Odoo CSV (format d'import standard des pièces comptables `account.move` et `account.move.line`).
5. **Dossier de preuves numérique (Evidence Pack)** :
   - Synthèse récapitulative (bordereau d'export / rapport de contrôle).
   - Manifeste JSON complet avec références documentaires, horodatages, règles appliquées et chaînes de hachage.
   - Empreintes SHA-256 de chaque pièce justificative incluse dans l'export.
6. **Invariant C4 n° 7** : Refus absolu de tout export si le hachage des écritures a été altéré depuis la validation (`ExportHashMismatchError`).
7. **Comptabilisation des usages (`usage_records`)** : enregistrement immuable d'un événement de facturation (`unit = 'monthly_file'`, `quantity = 1`, `billable = true`) lors de l'export validé.
8. **Enregistrement de la vérification aller-retour** : mise à jour de `export_profiles.verified_round_trip_at` pour acter le test sur logiciel comptable pilote.

---

## 2. Synthèse des 4 Prérequis de Phase 4 (Complétés et Testés)

1. **Codes bancaires RIB marocains (`identifiers.rib.bank_codes`)** :
   - L'ensemble de la liste est marqué `status: needs_expert` (`TODO(EXPERT)`).
   - Conflits corrigés : `013` est BMCI (et non BP), `101` est Banque Populaire, `022` est Société Générale Maroc.
   - `bp_stub.json` corrigé avec le RIB BP `101780000123456789012345`.
   - La validation de code banque émet un avertissement non bloquant (`warning`) tant que la liste est en attente de vérification Bank Al-Maghrib.
2. **Assiette HT pour la retenue à la source IS 5% (LF 2026) et retenues combinées** :
   - Assiette IS 5% assise rigoureusement sur le montant HT : $\text{Net} = \text{TTC} - \text{Taux}_{\text{IS}} \times \text{HT}$.
   - Retenues combinées (TVA 75%/100% sur TVA + IS 5% sur HT) : $\text{Net} = \text{TTC} - \text{Taux}_{\text{TVA}} \times \text{TVA} - \text{Taux}_{\text{IS}} \times \text{HT}$.
   - Taux et assiettes issus exclusivement de `vat_withholding.yaml`. Tests golden et matcher validés.
3. **Invariant BQ : Une seule proposition active par ligne bancaire** :
   - Migration 007 (`007_active_bq_proposal_unique.up.sql`) avec index partiel unique :
     ```sql
     CREATE UNIQUE INDEX one_active_bq_proposal_per_bank_transaction
     ON journal_proposals (tenant_id, source_bank_transaction_id)
     WHERE source_bank_transaction_id IS NOT NULL AND status IN ('proposed', 'edited', 'approved');
     ```
   - Cycle complet : ligne non rapprochée $\to$ proposition d'attente (rev 1) ; rapprochement accepté $\to$ attente remplacée par tiers (rev 2) ; rapprochement rejeté $\to$ proposition d'attente restaurée (rev 3).
   - Test d'intégration complet `test_bq_proposal_lifecycle.py` validé.
4. **Questions ouvertes et Registre des Experts** :
   - `docs/open-questions.md` complété (sections 6, 7, 8).
   - `docs/expert-register.md` rédigé, répertoriant les comptes d'attente (4711), de retenue (3457 vs 3452/3453/3458), et de frais bancaires (6147).

---

## 3. Architecture et Composants de la Phase 5

### 3.1 Service de Contrôle Qualité et Résolution d'Anomalies (`avenel/quality/service.py`)
- Vérifie l'état de préparation du dossier mensuel (`work_request_id`) :
  - Recherche d'anomalies de sévérité `blocking` à l'état `open`.
  - Vérification de l'équilibre de toutes les écritures proposées ($\sum \text{Débits} = \sum \text{Crédits}$).
  - Vérification qu'aucune ligne bancaire du relevé n'est orpheline sans proposition active.
  - Vérification que tous les comptes comptables sont résolus et mappés (aucun `ACCOUNT_UNMAPPED`).
- Si des anomalies bloquantes subsistent : levée de `QualityGateViolationError` listant les anomalies non résolues.

### 3.2 Service de Validation et Séparation des Fonctions (`avenel/approvals/service.py`)
- **Calcul de l'empreinte canonique (`compute_proposal_set_hash`)** :
  - Récupère toutes les propositions du dossier mensuel avec le statut `proposed` ou `edited`.
  - Trie déterministement les propositions par `journal_code`, `entry_date`, `id`.
  - Pour chaque proposition, trie ses lignes par `line_no`.
  - Sérialise en JSON canonique UTF-8 sans espacement inutile (`{"sort_keys": true, "separators": (',', ':')}`).
  - Calcule le condensat SHA-256 hexadécimal `subject_hash`.
- **Création de la demande d'approbation (`create_work_request_approval`)** :
  - Statut initial : `pending`.
  - Enregistre `subject_hash`, `prepared_by`.
- **Décision d'approbation (`decide_work_request_approval`)** :
  - **Règle de séparation des fonctions** : si `decided_by == prepared_by`, rejeter sauf si `tenants.settings.single_person_policy == true`.
  - **Numéro d'inscription professionnelle** : l'utilisateur approbateur doit posséder un `professional_registration_number` renseigné dans `users`.
  - Re-vérification du `subject_hash` en temps réel au moment de la signature : si les écritures ont changé entre la soumission et la décision, rejet immédiat avec `ApprovalStaleError`.
  - Transition atomique des propositions du dossier de `proposed`/`edited` vers `approved`.

### 3.3 Moteur d'Exportation Multi-Formats (`avenel/exports/`)
- **Vérification de l'Invariant C4 n° 7** :
  - Avant de générer les fichiers d'export, recalculer le `subject_hash` des propositions approuvées.
  - Si `current_hash != approval.subject_hash`, lever `ExportHashMismatchError("Le dossier a changé depuis la validation. Demandez une nouvelle validation.")`.
- **Exportateur Sage 100 CSV (`avenel/exports/sage_csv.py`)** :
  - Format texte standardisé, encodage CP1252 (avec translitération ou remplacement strict des caractères non supportés), séparateur `;`.
  - Colonnes : Code journal, Date écriture (JJMMYY ou JJMMAAAA selon profil), Numéro de pièce, Référence pièce, Numéro de compte général, Numéro de compte tiers, Libellé écriture, Montant débit, Montant crédit.
- **Exportateur Sage 100 PNM (`avenel/exports/sage_pnm.py`)** :
  - Format natif propriétaire Sage 100 d'import de pièces.
- **Exportateur Odoo CSV (`avenel/exports/odoo_csv.py`)** :
  - Colonnes d'import `account.move` et `account.move.line` : `move_id`, `journal_id`, `date`, `ref`, `account_id/code`, `partner_id/name`, `name`, `debit`, `credit`.
  - Encodage UTF-8 avec BOM optionnel.
- **Dossier de preuves numérique (Evidence Pack - `avenel/exports/evidence_pack.py`)** :
  - `manifest.json` : métadonnées complètes, horodatages, identifiants des pièces, règles juridiques appliquées, hash SHA-256 des documents sources et des propositions.
  - `summary.pdf` : récapitulatif synthétique certifié (généré via WeasyPrint ou ReportLab).
  - Archive ZIP contenant : `manifest.json`, `summary.pdf`, et le fichier d'export comptable.
- **Enregistrement d'usage (`avenel/exports/metering.py`)** :
  - Insertion dans la table `usage_records` : `tenant_id`, `work_request_id`, `unit = 'monthly_file'`, `quantity = 1`, `billable = true`.
  - Mise à jour de `export_profiles.verified_round_trip_at`.

### 3.4 Interface Utilisateur (Partie E)
- Écran de validation (`src/components/domain/ApprovalScreen.tsx`) :
  - Récapitulatif du dossier : totaux débits/crédits, pièces traitées, anomalies résolues.
  - Avertissement visuel de séparation des tâches.
  - Bouton d'action « Valider le dossier » (réservé à l'approbation du dossier mensuel, E.8).
- Écran d'export (`src/components/domain/ExportScreen.tsx`) :
  - Sélection du profil d'export (Sage 100 CSV, Sage 100 PNM, Odoo).
  - Téléchargement du fichier comptable et du dossier de preuves.
  - Mention explicite de l'empreinte de validation SHA-256.

---

## 4. Stratégie de Test et Critères de Sortie
1. **Invariant n° 7** : `test_invariant_7_export_refused_on_hash_mismatch` dé-skippé et implémenté avec assertion stricte de refus si le hash change.
2. **Séparation des fonctions** : tests d'approbation avec préparateur = approbateur (rejet sans `single_person_policy`, acceptation avec `single_person_policy`), et vérification du numéro d'inscription professionnelle.
3. **Fichiers d'export golden byte-identiques** : tests golden comparant octet par octet les exports Sage 100 CSV, Sage 100 PNM, et Odoo CSV.
4. **Vérification de l'Evidence Pack** : contrôle de la présence et de la validité du `manifest.json` et des SHA-256 des documents.
5. **Vérification de la facturation** : contrôle de l'insertion dans `usage_records`.
6. **Passage de l'ensemble de la suite CI** :
   - `make lint test typecheck openapi-lint rls-check`
   - Zero numeric tax literals outside `/jurisdiction/`.
   - Zéro mention du mot interdit dans tous les rapports et sorties.

