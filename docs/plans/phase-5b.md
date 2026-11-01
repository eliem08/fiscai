# Plan Phase 5b — Préparation au Pilote Fiduciaire (Pilot Readiness)

**Date :** 1er novembre 2026  
**Auteur :** Antigravity (Assistant IA d'Ingénierie)  
**Référence :** ARCHITECTURE.md (v2.0, Phase 5b)  
**Objectif :** Préparer le déploiement pilote auprès des cabinets d'expertise comptable partenaires : validation de bout en bout d'un dossier mensuel complet, accessibilité (axe-core), conteneurisation de production avec respect de la résidence des données, stratégie de sauvegarde et test de restauration chiffrée, durcissement de sécurité (OWASP ASVS L2, CSP, rate limiting) et kit pilote documentaire.

---

## 1. Périmètre et Objectifs Détaillés

### Module 1 : Test End-to-End Playwright (Cycle Mensuel Intégral)
- **Objectif :** Tester la chaîne complète d'un dossier mensuel réaliste via l'interface web et l'API :
  1. Connexion et création d'une entité cliente SARL.
  2. Import du plan comptable CGNC.
  3. Ouverture de la période comptable (ex. `2026-10`).
  4. Téléversement de pièces justificatives (factures d'achat, de vente) et d'un relevé bancaire (Attijariwafa Bank).
  5. Revue et correction d'un champ par l'opérateur dans le DocumentViewer avec mise en évidence de boîte englobante.
  6. Résolution/acquittement des anomalies (contrôle qualité zéro bloquant, justification d'anomalie de revue).
  7. Rapprochement bancaire : acceptation des propositions de matching avec écriture de contrepartie.
  8. Demande de validation initiée par un collaborateur comptable (`staff`).
  9. Approbation formelle par l'expert-comptable associé (`owner` avec MFA récente, titre OEC et numéro d'inscription).
  10. Exportation des écritures Sage 100 CSV et téléchargement du pack de preuves zippé avec lien signé temporaire.
- **Exécution :** Exécutable en local et en CI contre l'environnement conteneurisé docker-compose.

### Module 2 : Audits d'Accessibilité Automatisés (axe-core)
- **Objectif :** Zéro violation sérieuse ou critique sur les 6 écrans clés du produit :
  1. File d'attente des dossiers (`Queue` / `WorkRequestsQueue`).
  2. Écran de revue et DocumentViewer (`Review` / `ProposalReview`).
  3. Écran de réconciliation bancaire (`Reconciliation` / `ReconciliationScreen`).
  4. Écran d'approbation expert (`Approval` / `ApprovalScreen`).
  5. Écran d'exportation comptable (`Export` / `ExportScreen`).
  6. Espace demandes justificatifs client (`Portal` / `PortalRequests`).
- **Outil :** `@axe-core/playwright` / injection `axe-core` dans la suite Playwright.

### Module 3 : Déploiement et Résidence des Données
- **Conteneurisation de production :**
  - `docker/Dockerfile.api` : Multi-stage build Python 3.12, utilisateur non-root `appuser`, pas de compilateur dans l'image finale, health check actif.
  - `docker/Dockerfile.web` : Multi-stage build Vite + Nginx Alpine non-root avec en-têtes de sécurité (CSP, HSTS, X-Content-Type-Options, etc.).
- **Orchestration et infrastructure :**
  - Configuration `docker-compose.prod.yml` et manifestes Terraform pour VM hébergée au Maroc (N+ONE, Inwi Cloud) ou UE selon `data_residency_policy`.
  - Terminaison TLS automatisée, variables d'environnement hors dépôt, intégration KMS pour clé maître de chiffrement.
  - Journalisation structurée JSON (`avenel/infrastructure/structured_logging.py`) bannissant formellement l'affichage des contenus textuels bruts de documents ou de données personnelles (PII).

### Module 4 : Sauvegardes et Test de Restauration Déterministe
- **Configuration PITR :** Archivage continu des WAL PostgreSQL et sauvegardes de base quotidiennes chiffrées.
- **Script de test de restauration (`scripts/test_backup_restore.py`) :**
  - Procède à un dump/backup d'une base témoin.
  - Restaure le dump dans une base PostgreSQL isolée (`avenel_restore_verification`).
  - Exécute `scripts/check_migration_hashes.py` sur la base restaurée.
  - Exécute `scripts/rls_check.py` pour vérifier que les 30 tables conservent la sécurité RLS forcée.
  - Exécute `scripts/verify_audit_chain.py` pour prouver que la chaîne d'audit SHA-256 est intègre et inaltérée.
- **Runbook :** Documentation d'exploitation pas-à-pas dans `docs/runbooks/restore.md`.

### Module 5 : Durcissement Sécurité (OWASP ASVS L2)
- **Audit des dépendances :** Zéro vulnérabilité non corrigée (`pip-audit`, `npm audit`).
- **Grille de contrôle :** `docs/security/asvs.md` documentant la conformité aux exigences ASVS Niveau 2 (Authentification, Sessions, Contrôle d'accès, Upload sécurisé, Chiffrement).
- **Limitation de débit (Rate Limiting) :** Middleware FastAPI sur `/v1/auth/*` (10 req/min par IP/sujet) et sur `/v1/documents` (30 uploads/min par tenant).
- **Politique de sécurité de contenu (CSP) :** Configuration Nginx et middleware HTTP interdisant les scripts inline non autorisés et restreignant les origines.

### Module 6 : Kit Pilote Documentaire (`docs/pilot/`)
- `docs/pilot/real-document-request.md` : Protocole de collecte d'échantillons réels (factures représentatives, relevés bancaires des 6 principales banques marocaines).
- `docs/pilot/labelling-guide.md` : Guide d'annotation pour `labels.jsonl` (format normalisé 0-1, types de champs, taux de TVA, numéros ICE/IF).
- `docs/pilot/round-trip-test-procedure.md` : Guide opératoire pour tester et consigner un aller-retour logiciel sur Sage 100 et Odoo Enterprise.
- `docs/pilot/expert-sign-off-sheet.md` : Fiche de visa expert recensant exhaustivement chaque règle ou compte en statut `needs_expert`.

---

## 2. Ordre d'Exécution et Jalons de Validation

1. **Jalon 1 (Plan) :** Enregistrement de `docs/plans/phase-5b.md`.
2. **Jalon 2 (Sécurité & Rate Limiting) :** Middleware rate-limiting, CSP, audit des dépendances, rédaction de `docs/security/asvs.md`.
3. **Jalon 3 (Déploiement & Résidence) :** Dockerfiles de production, compose de production, journalisation structurée sans PII, configuration de santé.
4. **Jalon 4 (Sauvegardes & Restauration) :** Script `scripts/test_backup_restore.py` et runbook `docs/runbooks/restore.md`.
5. **Jalon 5 (Kit Pilote) :** Rédaction des 4 guides du dossier `docs/pilot/`.
6. **Jalon 6 (E2E & Accessibilité Playwright) :** Scénario mensuel complet + tests axe-core sur les 6 écrans.
7. **Jalon 7 (Revue finale de conformité) :** Exécution `make lint test typecheck openapi-lint rls-check`, vérification des 0 vulnérabilités et arrêt pour revue humaine.

