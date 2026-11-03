# AVENEL — Rapport de Phase : Pilot-2 (Documentation & Gouvernance Pilote)

**Identifiant du rapport :** `pilot-2`  
**Date :** 3 novembre 2026  
**Branche Git :** `main`  
**Commit de référence Phase 5 :** `3cde3d3`  
**Commit Phase 5b (Clôture) :** `573b2b6`  
**Commit Pilot-1 :** `e9928b7`  
**Commit Pilot-2 (Documentation) :** `be1176f`  
**Statut du système :** Mode Support Pilote Actif (Docs only, aucune modification de code, Phase 6 strictement bloquée)

---

## 1. Synthèse Exécutive et Conformité aux Directives Pilot-2

Conformément aux instructions strictes de **Pilot-2 (docs only, no code changes)** :

1. **Qualification Formelle des Capacités Hébergeurs Souverains :**
   - Toutes les mentions et déclarations relatives aux fonctionnalités d'infrastructure cloud au Maroc (notamment N+ONE Datacenters et Inwi Business Cloud) — incluant la compatibilité avec l'API AWS S3 Object Lock en mode `COMPLIANCE`, les services de gestion de clés KMS matériels (HSM FIPS 140-2 L3) et les découpages régionaux — ont été formellement annotées avec la mention obligatoire :
     ```text
     unverified — confirm with provider
     ```
   - Tous les identifiants de régions hypothétiques ou non officiellement publiés (tels que `ma-casablanca-1`) ont été supprimés de la documentation et remplacés par la balise normalisée `<REGION_TBD>`.
   - Les documents mis à jour comprennent : `docs/architecture/storage.md`, `docs/ARCHITECTURE-notes.md`, `docs/security/asvs.md`, `docs/reports/pilot-1-report.md`, et `docs/adr/ADR-001-frontend-vite-spa.md`.

2. **Divulgation Transparente de la Simulation de Réplication Off-Host :**
   - Il est désormais expressément et clairement stipulé dans `docs/reports/pilot-1-report.md` ainsi que dans le manuel opératoire `docs/runbooks/restore.md` que la réplication documentaire chiffrée off-host est **actuellement simulée dans le banc de test d'intégration continue (CI)** et **n'est pas encore configurée en environnement de production**.
   - La mise en service effective d'une seconde cible de stockage géographique dans la même région de souveraineté (`<REGION_TBD>`) a été érigée en condition préalable bloquante dans la checklist de go-live.

3. **Checklist Bloquante de Mise en Production Pilote (`docs/pilot/go-live-checklist.md`) :**
   - Rédaction intégrale du document de gouvernance `docs/pilot/go-live-checklist.md`.
   - Définition des 9 jalons préalables obligatoires devant être individuellement vérifiés et contresignés (nom, rôle, date, référence de preuve) avant le moindre téléversement de document client réel dans le système :
     1. Hébergeur souverain retenu ; région (`<REGION_TBD>`), stockage d'objets, versioning, chiffrement SSE-S3 AES-256 et support Object Lock confirmés par écrit par le fournisseur.
     2. Cible réelle de sauvegarde off-host configurée dans la même région de souveraineté ; première synchronisation nocturne réussie.
     3. Drill de restauration déterministe (`scripts/test_backup_restore.py`) exécuté avec succès sur l'infrastructure de production réelle ; vérification SHA-256 validée sur l'échantillon documentaire.
     4. Séquestre de la clé maîtresse `AVENEL_KMS_KEY` : copie chiffrée hors-ligne entreposée dans deux lieux sécurisés distincts, deux gardiens nommés, test de récupération à froid validé.
     5. Déclaration CNDP (Loi 09-08) déposée et numéro de récépissé consigné dans `tenants.cndp_declaration_ref`.
     6. Accord de sous-traitance des données (DPA) dûment paraphé et signé avec la fiduciaire partenaire.
     7. Grille d'experts fiscaux (`docs/pilot/expert-sign-off-sheet.md`) passée en revue : seules les règles attestées par un expert nommé avec source légale sont activées (`status: verified`), les autres demeurent désactivées (`status: needs_expert`).
     8. Sécurité réseau, terminaison TLS 1.3, MFA obligatoire pour l'ensemble des comptes du cabinet, accès opérateur désactivé par défaut.
     9. Aller-retour logiciel (Sage 100 / Odoo) enregistré avec succès (`result = 'ok'`) sur le logiciel effectif de la fiduciaire.
   - Protocole de clôture formalisé par un engagement sur l'honneur du Directeur de Projet autorisant le Go-Live.

4. **Invariance du Code Source :**
   - Aucune ligne de code applicatif (`avenel/`, `apps/`, `scripts/`, `docker-compose.prod.yml`, dépendances) n'a été modifiée au cours de cette phase.

---

## 2. Confirmation d'Intégrité des Migrations Gelées (K.24)

Vérification du diff-stat des migrations de base de données depuis le commit d'approbation de la Phase 5 (`3cde3d3`) :
```bash
$ git diff --stat 3cde3d3..HEAD -- db/migrations/
 db/migrations/009_review_metrics_and_rate_limits.down.sql |  4 +++
 db/migrations/009_review_metrics_and_rate_limits.up.sql   | 34 ++++++++++++++++++++++
 2 files changed, 38 insertions(+)
```
**Attestation d'intégrité absolue :** Les migrations gelées 001 à 008 n'ont subi aucune modification. Seule la migration `009` (créée en Phase 5b pour les métriques de révision et rate-limiting) est présente.

---

## 3. Liens d'Exécution GitHub Actions CI

| Événement | Commit | Lien GitHub Actions (ubuntu-latest) | Statut & Durée |
| :--- | :---: | :--- | :---: |
| **Phase 5b Clôture** | `573b2b6` | [Run 41710087134](https://github.com/eliem08/fiscai/actions/runs/41710087134) | ✅ Succeeded (2m56s, 26 étapes) |
| **Pilot-1 Fix-Round** | `e9928b7` | [Run 41716866418](https://github.com/eliem08/fiscai/actions/runs/41716866418) | ✅ Succeeded (4m15s, 26 étapes) |
| **Pilot-2 Documentation** | `be1176f` | [Run 41719139626](https://github.com/eliem08/fiscai/actions/runs/41719139626) | ✅ Succeeded (2m59s, 26 étapes) |

---

## 4. Détail des Vérifications Documentaires

### 4.1 Annotation des Hypothèses Fournisseurs Cloud
Dans `docs/architecture/storage.md` (Section 3.1) et `docs/ARCHITECTURE-notes.md` (Section 12.2) :
```markdown
> [!WARNING]
> **Statut des déclarations de capacités hébergeurs (`unverified — confirm with provider`) :**
> Toutes les déclarations concernant les capacités techniques d'opérateurs infonuagiques souverains au Maroc (notamment N+ONE Datacenters et Inwi Business Cloud) — y compris le support de l'extension AWS S3 Object Lock en mode COMPLIANCE, les services KMS managés avec HSM, et les dénominations officielles de régions cloud — sont formellement classées comme **unverified — confirm with provider** (non vérifié — à confirmer par écrit auprès du fournisseur).
```
Dans `docs/security/asvs.md` (Lignes V6.4.1 et PILOT-RISK-OBJ-LOCK-01) :
```markdown
| **PILOT-RISK-OBJ-LOCK-01** | **Verrouillage d'objets WORM (S3 Object Lock en mode COMPLIANCE)** | Accepted Risk | *(unverified — confirm with provider)* Les déclarations relatives aux capacités des hébergeurs souverains au Maroc (notamment N+ONE et Inwi) concernant Object Lock, KMS et régions sont non vérifiées et doivent être confirmées par écrit auprès du fournisseur. Hypothèse : ces opérateurs n'exposent pas nativement l'API AWS S3 Object Lock en mode COMPLIANCE... |
```

### 4.2 Divulgation de l'État de la Réplication Off-Host
Dans `docs/runbooks/restore.md` (Section 1, point 3) et `docs/reports/pilot-1-report.md` (Section 1, point 3) :
```markdown
> [!WARNING]
> **État d'avancement opérationnel :** La réplication off-host est actuellement **simulée en intégration continue (CI)** et **n'est pas encore configurée en production**. La configuration d'une cible réelle de sauvegarde off-host dans la même région de souveraineté (`<REGION_TBD>`) est un prérequis bloquant avant le premier téléversement de documents clients réels (voir `docs/pilot/go-live-checklist.md`).
```

### 4.3 Structure de la Checklist de Go-Live (`docs/pilot/go-live-checklist.md`)
Les 9 jalons ont été découpés en fiches d'audit individuelles comportant :
- L'exigence opérationnelle précise et la référence d'architecture.
- L'indicateur de statut bloquant : `[ ] NON EFFECTUÉ (Bloquant)`.
- La nature exacte de la pièce probante requise (attestation, rapport, contrat, récépissé, capture).
- L'identité nominative, le rôle et la signature du signataire responsable.

---

## 5. Maintien du Mode Support Pilote

Le système demeure strictement en **Mode Support Pilote** :
- **Phase 6 (SIMPL-TVA / Télédéclaration) :** Strictement bloquée dans l'attente de la mise à disposition du schéma XSD officiel de la DGI (`TODO(EXPERT)`).
- **Interdiction de nouveaux développements ou refactorisations.**
- **Périmètre d'action exclusif :**
  1. Résolution de bogues identifiés lors des essais terrains de la fiduciaire.
  2. Intégration des règles fiscales validées avec attestation nominative d'expert (`status: verified`).
  3. Ajustements mineurs des profils d'export suite aux allers-retours réels Sage/Odoo.
  4. Évaluation continue sur jeu de données réelles dès disponibilité de `labels.jsonl`.
