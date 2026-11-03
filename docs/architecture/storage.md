# AVENEL — Architecture de Stockage d'Objets S3 et Résidence des Données

**Référence :** ARCHITECTURE.md (C.4, Part K, Phase 5b, Pilot-1, Pilot-2)  
**Date :** 3 novembre 2026  
**Statut :** Approuvé pour Pilote

---

## 1. Contexte et Objectifs

Dans le respect de la règle d'isolation et d'intégrité de la plateforme AVENEL, les documents comptables et pièces justificatives (factures d'achat, de vente, relevés bancaires, packs de preuves) ne doivent **jamais** résider sur un volume local de conteneur en production.

L'architecture de stockage répond aux exigences suivantes :
1. **Stockage d'objets compatible S3 souverain :** Les documents sont stockés sur une infrastructure compatible S3 hébergée dans la zone de souveraineté géographique du tenant (`DATA_RESIDENCY_POLICY` : Maroc `MA_ONLY` dans la région `<REGION_TBD>` ou Union Européenne `EU_ALLOWED`).
2. **Chiffrement au repos (SSE) :** Chiffrement systématique au repos avec AES-256 (`ServerSideEncryption = "AES256"`).
3. **Gestion des versions (Versioning) :** Compartiment S3 avec historisation native des versions.
4. **URLs éphémères signées :** Téléversement et consultation via URLs pré-signées de 15 minutes (HMAC-SHA256).
5. **Sauvegarde et réplication chiffrée quotidienne :** Réplication chiffrée quotidienne vers un second site souverain distant dans la même région `<REGION_TBD>` *(Note opérationnelle : la réplication off-host est actuellement simulée en intégration continue et n'est pas encore configurée en production)*.

---

## 2. Configuration Applicative

L'adaptateur S3 (`avenel.infrastructure.storage.S3StorageBackend`) est configuré via variables d'environnement injectées de façon sécurisée :

| Variable d'Environnement | Valeur par Défaut | Description |
| :--- | :--- | :--- |
| `STORAGE_BACKEND` | `s3` | Type d'adaptateur (`s3` en production, `filesystem` en tests unitaires) |
| `S3_ENDPOINT_URL` | `http://minio:9000` | Point de terminaison S3 souverain ou passerelle locale |
| `S3_REGION` | `<REGION_TBD>` | Région de souveraineté géographique (ex. `<REGION_TBD>`, à confirmer avec l'hébergeur) |
| `S3_BUCKET_NAME` | `avenel-documents` | Nom du compartiment de stockage des documents |
| `S3_ACCESS_KEY_ID` | `avenel_s3_admin` | Clé d'accès S3 |
| `S3_SECRET_ACCESS_KEY` | *(Secret KMS)* | Clé secrète S3 |
| `S3_SERVER_SIDE_ENCRYPTION`| `AES256` | Algorithme de chiffrement côté serveur |
| `S3_ENABLE_OBJECT_LOCK` | `false` | Activation de l'immutabilité WORM S3 Object Lock (si confirmée par l'hébergeur) |

---

## 3. Analyse des Capacités Hébergeurs et Verrouillage d'Objets (Object Lock)

### 3.1 Statut des Capacités Hébergeurs Souverains : `unverified — confirm with provider`
> [!WARNING]
> **Avertissement de non-vérification (unverified — confirm with provider) :**  
> Toutes les déclarations concernant les capacités techniques d'opérateurs infonuagiques souverains au Maroc (notamment N+ONE Datacenters et Inwi Business Cloud) — y compris le support de l'extension AWS S3 Object Lock en mode COMPLIANCE, les services KMS managés avec HSM, et les dénominations officielles de régions cloud — sont formellement classées comme **unverified — confirm with provider** (non vérifié — à confirmer par écrit auprès du fournisseur).  
> 
> L'hypothèse technique retenue pour le pilote est que ces opérateurs fournissent des interfaces de stockage objet compatibles S3 standard, mais n'exposent pas l'extension propriétaire AWS S3 Object Lock en mode conformité matérielle WORM (`ObjectLockMode = COMPLIANCE` avec rétention légale `retain_until`). Ces capacités, ainsi que le nommage exact de la région (`<REGION_TBD>`), doivent être confirmées par écrit par l'hébergeur retenu avant le go-live (voir `docs/pilot/go-live-checklist.md`).

### 3.2 Stratégie Palliative et Atténuation des Risques pour le Pilote
Pour satisfaire aux exigences strictes de conservation de la DGI (10 ans selon le CGI art. 145) sans dépendre de fonctionnalités non vérifiées :
1. **MinIO compatible S3 avec versioning activé :** Le déploiement s'appuie sur une instance compatible S3 (MinIO durcie) avec compartiment configuré en versioning strict.
2. **Immuabilité applicative et base de données :** Des déclencheurs PostgreSQL (`prevent_immutable_update_or_delete`) interdisent toute modification ou suppression sur les tables `document_versions`, `documents`, `evidence_records`, `approvals` et `audit_events`.
3. **Réplication quotidienne chiffrée off-host (Simulée en CI, à configurer en production) :** Chaque nuit, une archive chiffrée AES-256-GCM est synchronisée vers un second centre de données physiquement distinct situé dans la même région de souveraineté `<REGION_TBD>`. *(Note : cette réplication est démontrée et testée dans le drill CI ; sa cible de production doit être configurée avant le premier téléversement réel).*
4. **Vérification cryptographique continue :** Le script de drill de restauration (`scripts/test_backup_restore.py`) restaure un échantillon de documents et valide l'empreinte SHA-256 par rapport à la table `document_versions`.
5. **Formalisation ASVS :** L'écart est acté en risque accepté de phase pilote dans `docs/security/asvs.md` (Réf. `PILOT-RISK-OBJ-LOCK-01`).

### 3.3 Trajectoire de Remédiation (Phase 7 / GA)
Dès confirmation écrite ou mise en service d'un stockage WORM certifié chez l'hébergeur souverain retenu, l'activation se fera directement par variable d'environnement sans modification de code via `S3_ENABLE_OBJECT_LOCK = true`.
