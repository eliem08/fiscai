# AVENEL — Rapport de Phase : Pilot-1 (Pre-Data Blocker)

**Identifiant du rapport :** `pilot-1`  
**Date :** 3 novembre 2026  
**Branche Git :** `main`  
**Commit de référence Phase 5 :** `3cde3d3`  
**Commit Phase 5b (Clôture) :** `573b2b6`  
**Commit Pilot-1 :** `e9928b7`  
**Statut du système :** Mode Support Pilote Actif (Aucune nouvelle phase, Phase 6 strictement bloquée)

---

## 1. Synthèse Exécutive et Conformité aux Directives Pilot-1

Conformément aux instructions `Pilot-1 (pre-data blocker)` :
1. **Élimination stricte des volumes locaux de conteneurs pour les documents :**
   - Le montage `docdata:/app/data/documents` a été formellement retiré des conteneurs `api` et `worker` dans `docker-compose.prod.yml`.
   - Tous les documents sont désormais hébergés sur un stockage d'objets compatible S3 dans la région de souveraineté géographique du tenant (`DATA_RESIDENCY_POLICY` : `MA_ONLY` dans la région `<REGION_TBD>` ou `EU_ALLOWED`).
   - L'adaptateur S3 (`avenel.infrastructure.storage.S3StorageBackend`) prend en charge nativement le chiffrement côté serveur SSE-S3 (`AES256`), le versioning des compartiments, et le verrouillage WORM Object Lock (`COMPLIANCE` mode avec date de rétention `retain_until`).
2. **Documentation des Capacités Hébergeurs (`unverified — confirm with provider`) :**
   - Toutes les déclarations concernant les capacités des hébergeurs souverains au Maroc (notamment N+ONE Datacenters et Inwi Business Cloud) quant au support d'Object Lock, des régions et de KMS sont formellement classées comme **unverified — confirm with provider** (non vérifié — à confirmer par écrit auprès du fournisseur).
   - L'écart préliminaire d'Object Lock a été consigné dans `docs/architecture/storage.md` et `docs/ARCHITECTURE-notes.md`.
   - Le risque est formellement enregistré dans la grille OWASP ASVS L2 (`docs/security/asvs.md`) sous la référence `PILOT-RISK-OBJ-LOCK-01` avec les mesures palliatives actives (versioning MinIO, déclencheurs PostgreSQL immuables append-only, réplication quotidienne chiffrée off-host et drill hebdomadaire).
3. **Extension de la Sauvegarde et Drill de Restauration Documentaire :**
   > [!IMPORTANT]
   > **Avertissement d'état opérationnel :** La réplication off-host du stockage de documents est actuellement **simulée en intégration continue (CI)** et **n'est pas encore configurée en production**. La configuration d'une cible réelle de sauvegarde off-host dans la même région de souveraineté (`<REGION_TBD>`) est un prérequis bloquant obligatoire avant tout téléversement de documents clients réels (voir `docs/pilot/go-live-checklist.md`).
   - Mise en place d'une réplication quotidienne chiffrée AES-256-GCM du stockage documentaire vers un second emplacement souverain distinct.
   - Extension de `scripts/test_backup_restore.py`, de la documentation `docs/runbooks/restore.md` et du workflow CI hebdomadaire `.github/workflows/restore-drill.yml`.
   - Vérification déterministe post-restauration de chaque pièce restaurée par recalcul SHA-256 et comparaison stricte avec la colonne immuable `document_versions.sha256`.

---

## 2. Confirmation d'Intégrité des Migrations Gelées (K.24)

Diff-stat exact depuis le commit d'approbation de la Phase 5 (`3cde3d3`) :
```bash
$ git diff --stat 3cde3d3..HEAD -- db/migrations/
 db/migrations/009_review_metrics_and_rate_limits.down.sql |  4 +++
 db/migrations/009_review_metrics_and_rate_limits.up.sql   | 34 ++++++++++++++++++++++
 2 files changed, 38 insertions(+)
```
**Attestation d'invariance :** Aucune ligne des migrations gelées 001 à 008 n'a été modifiée. Seule la migration `009` (ajoutée en Phase 5b) est présente.

---

## 3. Liens d'Exécution GitHub Actions CI

| Événement | Commit | Lien GitHub Actions (ubuntu-latest) | Statut & Durée |
| :--- | :---: | :--- | :---: |
| **Phase 5b Clôture** | `573b2b6` | [Run 41710087134](https://github.com/eliem08/fiscai/actions/runs/41710087134) | ✅ Succeeded (2m56s, 26 étapes) |
| **Pilot-1 Fix-Round** | `e9928b7` | [Run 41716866418](https://github.com/eliem08/fiscai/actions/runs/41716866418) | ✅ Succeeded (4m15s, 26 étapes) |

---

## 4. Détail des Réalisations Techniques

### 4.1 Stockage d'Objets Compatible S3 et Élimination des Volumes Locaux

1. **Suppression des volumes locaux Docker :**
   Dans `docker-compose.prod.yml`, les entrées `volumes: - docdata:/app/data/documents` ont été supprimées des services `api` et `worker`. Le volume `docdata` a été remplacé par un service de stockage compatible S3 (`minio`) avec volume persistant `miniodata`.
2. **Implémentation de l'adaptateur `S3StorageBackend` :**
   Créé dans `avenel/infrastructure/storage.py` :
   - `put_object` et `put_original` : Chiffrement SSE-S3 (`ServerSideEncryption='AES256'`) systématique, support de la rétention légale `retain_until` via `ObjectLockMode='COMPLIANCE'` et `ObjectLockRetainUntilDate`.
   - `get_object` : Récupération du flux binaire et levée de `FileNotFoundError` en cas d'absence.
   - `generate_presigned_get_url` et `generate_presigned_put_url` : URLs temporaires signées à 15 minutes.
   - Rejeu sans échec en cas d'absence de configuration Object Lock sur l'infrastructure hôte (repli sécurisé avec journalisation d'audit).
3. **Documentation de l'architecture et statut non vérifié :**
   - Document dédié rédigé : `docs/architecture/storage.md`.
   - Section 12 ajoutée à `docs/ARCHITECTURE-notes.md`.
   - Risque accepté consigné dans `docs/security/asvs.md` (Réf. `PILOT-RISK-OBJ-LOCK-01`).

### 4.2 Sauvegarde Documentaire Chiffrée et Drill de Restauration

1. **Réplication chiffrée quotidienne off-host (simulée en CI, cible prod à configurer) :**
   - Fonction `backup_document_storage` : empaquetage `tar.gz` et chiffrement AES-256-GCM via la clé KMS maîtresse (`AVENEL_KMS_KEY`).
   - Simule l'expédition nocturne vers un second centre de données souverain dans la région `<REGION_TBD>`.
2. **Restauration et vérification déterministe (`scripts/test_backup_restore.py`) :**
   - Restaure la base logique dans `avenel_restored_verification`.
   - Déchiffre et extrait les pièces documentaires dans un répertoire de stockage isolé.
   - Étape de contrôle 5d : Interroge `SELECT object_key, sha256, byte_size FROM document_versions` sur la base restaurée, lit chaque document depuis le stockage restauré, recalcule déterministement son empreinte SHA-256 et atteste l'égalité stricte.
3. **Manuel opératoire mis à jour :**
   - `docs/runbooks/restore.md` intègre l'architecture à trois volets (Base Backups + WAL Archiving + Document Storage Replication) et le 5e jalon de vérification SHA-256.

---

## 5. Synthèse des Résultats des Jalons de Qualité

Tous les contrôles automatisés s'exécutent avec succès tant localement qu'en intégration continue :

```
[make] Running lint...
All checks passed!
[LINT PASSED] No forbidden numeric tax literals, hardcoded identifier regexes, or account seeds found in application code.
SUCCESS: All 16 frozen migrations (001–008) verified intact.
[TEST COUNT CHECK] Collected: 214 | Required Baseline: 214
[TEST COUNT CHECK PASSED] Test count maintained or increased.
PASS: docs/pilot/expert-sign-off-sheet.md is up to date with 28 needs_expert rules.

[make] Running typecheck...
Success: no issues found in 88 source files

[make] Running openapi-lint...
No results with a severity of 'error' found!

[make] Running rls-check...
[RLS-CHECK PASSED] All 31 tables with tenant_id have forced RLS and tenant policy.

[make] Running audit-verify...
[AUDIT-VERIFY PASSED] All 5 audit events across 1 tenant(s) verified linear and intact.

[make] Running test...
======================= 214 passed in 126.10s =======================

[make] Running backup-restore drill...
========================================================
SUCCESS: Backup and restore verification completed successfully.
Restored database 'avenel_restored_verification' and document storage passed all security invariants.
========================================================
```

---

## 6. Maintien du Mode Support Pilote

Le système demeure strictement en **Mode Support Pilote** :
- **Phase 6 :** Formellement bloquée (en attente du schéma officiel XSD SIMPL-TVA de la DGI).
- **Aucune nouvelle fonctionnalité ni refactorisation.**
- **Périmètre exclusif d'intervention :**
  1. Corrections de bogues remontés par les fiduciaires du pilote.
  2. Ajustements du pack fiscal `/jurisdiction/ma/*.yaml` accompagnés des signatures d'experts (nom, date, source légale).
  3. Ajustements des profils d'export logiciel (Sage 100, Odoo) issus des tests aller-retour réels.
  4. Évaluation sur documents réels dès livraison du fichier `labels.jsonl`.
