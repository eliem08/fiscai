# AVENEL — Checklist Bloquante de Mise en Production Pilote (Go-Live)

**Référence :** ARCHITECTURE.md (Part A, C.4, E.8, Pilot-2)  
**Date d'établissement :** 3 novembre 2026  
**Statut d'application :** STRICTEMENT BLOQUANT  
**Règle d'or :** Aucun document client réel ni aucune donnée personnelle ne doit être téléversé dans le système tant que l'intégralité des 9 jalons ci-dessous n'a pas été formellement validée, vérifiée et signée (nom, rôle, date).

---

## Registre des 9 Jalons Pré-Requis Obligatoires

### Jalon 1 : Sélection et Confirmation Écrite de l'Hébergeur Souverain
- **Exigence :** L'hébergeur souverain de production est officiellement sélectionné. La région exacte d'hébergement (`<REGION_TBD>`), la compatibilité du stockage d'objets S3, le versioning de compartiment, le chiffrement au repos (SSE-S3 AES-256) et les capacités effectives de verrouillage WORM (Object Lock en mode COMPLIANCE) doivent faire l'objet d'une **confirmation écrite formelle** émise par l'hébergeur.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Attestation contractuelle ou technique signée de l'hébergeur.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Responsable Infrastructure / CTO
  - **Date de validation :** ____ / ____ / 2026
  - **Signature / Réf. Preuve :** ____________________________________

---

### Jalon 2 : Configuration de la Cible Réelle de Sauvegarde Off-Host
- **Exigence :** Une cible réelle de sauvegarde et de réplication hors-site (off-host) est configurée dans la même région de souveraineté géographique (`<REGION_TBD>`). La première synchronisation nocturne chiffrée AES-256-GCM du stockage documentaire et des bases de données a été exécutée avec succès sans aucune erreur.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant — réplication actuellement simulée en CI)
- **Preuve requise :** Journal d'exécution de la première réplication et empreintes des archives distantes.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Ingénieur DevOps / SRE
  - **Date de validation :** ____ / ____ / 2026
  - **Signature / Réf. Preuve :** ____________________________________

---

### Jalon 3 : Drill de Restauration sur Infrastructure de Production Réelle
- **Exigence :** Le test automatisé de restauration déterministe (`scripts/test_backup_restore.py`) a été exécuté sur l'infrastructure réelle de production à partir d'une vraie sauvegarde off-host. Les contrôles d'intégrité des migrations (16/16), d'isolation PostgreSQL RLS (31/31 tables), de continuité de la chaîne d'audit SHA-256, et la vérification SHA-256 pièce par pièce sur l'échantillon documentaire restauré ont été validés à 100%.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Rapport de sortie d'exécution du drill de production attestant le code de retour 0.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Responsable Sécurité des SI (RSSI)
  - **Date de validation :** ____ / ____ / 2026
  - **Signature / Réf. Preuve :** ____________________________________

---

### Jalon 4 : Séquestre de la Clé Maîtresse KMS (`AVENEL_KMS_KEY`)
- **Exigence :** La clé maîtresse de chiffrement d'enveloppe (`AVENEL_KMS_KEY`) est mise sous séquestre : une copie hors-ligne chiffrée est conservée dans **deux emplacements physiques distincts et sécurisés** (coffres ignifugés), sous la garde de **deux dépositaires nommés et habilités**. Une procédure de récupération d'urgence à froid a été simulée et validée au moins une fois avec succès.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Procès-verbal de scellement des coffres et test de récupération.
- **Dépositaires désignés :**
  - **Dépositaire 1 (Nom, Rôle, Date) :** ____________________________________
  - **Dépositaire 2 (Nom, Rôle, Date) :** ____________________________________
  - **Signature conjointe :** ____________________________________

---

### Jalon 5 : Déclaration CNDP (Loi 09-08) & Récépissé Légal
- **Exigence :** Le dossier de déclaration de traitement de données à caractère personnel a été formellement déposé auprès de la CNDP (Commission Nationale de contrôle de la protection des Données à caractère Personnel). Le numéro de récépissé officiel a été saisi et persisté dans la colonne `tenants.cndp_declaration_ref`.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Récépissé officiel de dépôt ou d'autorisation délivré par la CNDP.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Délégué à la Protection des Données (DPO) / Conseiller Juridique
  - **Date de validation :** ____ / ____ / 2026
  - **Numéro récépissé CNDP :** ____________________________________

---

### Jalon 6 : Signature de l'Accord de Sous-Traitance (DPA)
- **Exigence :** L'accord contractuel de traitement des données à caractère personnel (*Data Processing Agreement*) conforme à la Loi 09-08 a été dûment paraphé et signé entre l'opérateur AVENEL et les représentants légaux de la fiduciaire pilote.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Contrat DPA contresigné archivé sous `docs/pilot/contracts/`.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Directeur Général / Représentant Légal AVENEL
  - **Date de validation :** ____ / ____ / 2026
  - **Signature / Réf. Contrat :** ____________________________________

---

### Jalon 7 : Revue de la Grille d'Experts Fiscaux & Règles Activées
- **Exigence :** La grille de validation légale (`docs/pilot/expert-sign-off-sheet.md`) a été formellement passée en revue. Seules les règles comptables et fiscales ayant recueilli une signature d'expert fiscaliste ou expert-comptable avec nom, date et citation textuelle de source légale sont activées (`status: verified`). Toutes les règles non attestées demeurent formellement désactivées avec le statut `status: needs_expert`.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Feuille de signature d'experts signée par l'expert-comptable référent.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Expert-Comptable Référent (Inscrit à l'OEC)
  - **Date de validation :** ____ / ____ / 2026
  - **Signature / N° Inscription OEC :** ____________________________________

---

### Jalon 8 : Sécurisation Réseau, TLS 1.3, MFA & Rôles Opérateurs
- **Exigence :** Le chiffrement TLS 1.3 avec en-têtes de sécurité stricts (HSTS, CSP, Permissions-Policy) est actif en production. L'authentification multi-facteurs (MFA RFC 9470) est formellement activée et obligatoire pour l'ensemble des comptes utilisateurs de la fiduciaire. L'accès d'assistance technique opérateur (`role: operator`) est **désactivé par défaut** et ne peut être ouvert que sur demande explicite consignée en audit.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Rapport de scan de conformité TLS (Qualys SSL Labs A+) et export de configuration Keycloak.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Lead Architecte Sécurité
  - **Date de validation :** ____ / ____ / 2026
  - **Signature / Réf. Audit :** ____________________________________

---

### Jalon 9 : Validation des Allers-Retours Logiciels (Sage 100 / Odoo)
- **Exigence :** Un test aller-retour complet a été exécuté avec le logiciel comptable effectif de la fiduciaire (Sage 100 ou Odoo). Le résultat `ok` a été formellement consigné via `POST /v1/export-profiles/{id}:record-round-trip` avec pièce justificative (capture d'écran d'intégration réussie sans anomalie de balance), débloquant l'affichage de l'export sur la console.
- **Statut :** `[ ] NON EFFECTUÉ` (Bloquant)
- **Preuve requise :** Enregistrement dans `export_round_trips` avec `result = 'ok'`.
- **Signataire désigné :**
  - **Nom du signataire :** ____________________________________
  - **Rôle / Titre :** Expert-Comptable / Associé de la Fiduciaire Pilote
  - **Date de validation :** ____ / ____ / 2026
  - **Logiciel & Version testée :** ____________________________________
  - **Signature / Réf. Aller-Retour :** ____________________________________

---

## 3. Autorisation Finale de Téléversement des Pièces Réelles

> **DÉCLARATION FORMELLE DE MISE EN SERVICE (GO-LIVE) :**  
> Je soussigné(e), ____________________________________, agissant en qualité de Directeur de Projet / Associé Gérant, atteste sur l'honneur que l'ensemble des 9 jalons ci-dessus ont été contrôlés, vérifiés et dûment contresignés.  
> 
> L'autorisation de téléversement de documents réels et d'activation du service pilote est accordée le : ____ / ____ / 2026 à Casablanca.  
> 
> **Signature finale de Go-Live :** ____________________________________
