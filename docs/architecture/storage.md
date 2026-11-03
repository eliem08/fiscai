# AVENEL — Architecture de Stockage d'Objets S3 et Résidence des Données

**Référence :** ARCHITECTURE.md (C.4, Part K, Phase 5b, Pilot-1)  
**Date :** 3 novembre 2026  
**Statut :** Approuvé pour Pilote

---

## 1. Contexte et Objectifs

Dans le respect de la règle d'isolation et d'intégrité de la plateforme AVENEL, les documents comptables et pièces justificatives (factures d'achat, de vente, relevés bancaires, packs de preuves) ne doivent **jamais** résider sur un volume local de conteneur en production.

L'architecture de stockage répond aux exigences suivantes :
1. **Stockage d'objets compatible S3 souverain :** Les documents sont stockés sur une infrastructure compatible S3 hébergée dans la zone de souveraineté géographique du tenant (`DATA_RESIDENCY_POLICY` : Maroc `MA_ONLY` ou Union Européenne `EU_ALLOWED`).
2. **Chiffrement au repos (SSE) :** Chiffrement systématique au repos avec AES-256 (`ServerSideEncryption = "AES256"`).
3. **Gestion des versions (Versioning) :** Compartiment S3 avec historisation native des versions.
4. **URLs éphémères signées :** Téléversement et consultation via URLs pré-signées de 15 minutes (HMAC-SHA256).
5. **Sauvegarde et réplication chiffrée quotidienne :** Réplication chiffrée quotidienne vers un second site souverain distant dans la même région.

---

## 2. Configuration Applicative

L'adaptateur S3 (`avenel.infrastructure.storage.S3StorageBackend`) est configuré via variables d'environnement injectées de façon sécurisée :

| Variable d'Environnement | Valeur par Défaut | Description |
| :--- | :--- | :--- |
| `STORAGE_BACKEND` | `s3` | Type d'adaptateur (`s3` en production, `filesystem` en tests unitaires) |
| `S3_ENDPOINT_URL` | `http://minio:9000` | Point de terminaison S3 souverain ou passerelle locale |
| `S3_REGION` | `ma-casablanca-1` | Région de souveraineté géographique |
| `S3_BUCKET_NAME` | `avenel-documents` | Nom du compartiment de stockage des documents |
| `S3_ACCESS_KEY_ID` | `avenel_s3_admin` | Clé d'accès S3 |
| `S3_SECRET_ACCESS_KEY` | *(Secret KMS)* | Clé secrète S3 |
| `S3_SERVER_SIDE_ENCRYPTION`| `AES256` | Algorithme de chiffrement côté serveur |
| `S3_ENABLE_OBJECT_LOCK` | `false` | Activation de l'immutabilité WORM S3 Object Lock |

---

## 3. Analyse de l'Écart : Verrouillage d'Objets (Object Lock Gap) sur Hébergeurs Marocains

### 3.1 Constat Technique
Les opérateurs d'hébergement souverain opérant au Maroc (notamment N+ONE Datacenters et Inwi Business Cloud) fournissent des solutions de stockage objet compatibles avec le protocole S3 standard. Toutefois, à la date de démarrage du pilote :
- L'extension **AWS S3 Object Lock** (mode `COMPLIANCE` avec rétention WORM matérielle garantie par API `ObjectLockMode` / `ObjectLockRetainUntilDate`) n'est pas exposée nativement sur les offres d'objets managées souveraines.

### 3.2 Stratégie Palliative et Atténuation des Risques pour le Pilote
Pour satisfaire aux exigences strictes de conservation de la DGI (10 ans selon le CGI art. 145) sans exposer le pilote :
1. **MinIO compatible S3 avec versioning activé :** Le déploiement s'appuie sur une instance compatible S3 (MinIO durcie) avec compartiment configuré en versioning strict.
2. **Immuabilité applicative et base de données :** Des déclencheurs PostgreSQL (`prevent_immutable_update_or_delete`) interdisent toute modification ou suppression sur les tables `document_versions`, `documents`, `evidence_records`, `approvals` et `audit_events`.
3. **Réplication quotidienne chiffrée off-host :** Chaque nuit, une archive chiffrée AES-256 de l'ensemble des objets est synchronisée vers un second centre de données physiquement distinct situé sur le territoire marocain.
4. **Vérification cryptographique continue :** Le script de drill de restauration (`scripts/test_backup_restore.py`) restaure un échantillon de documents et valide l'empreinte SHA-256 par rapport à la table `document_versions`.
5. **Formalisation ASVS :** L'écart est acté en risque accepté de phase pilote dans `docs/security/asvs.md` (Réf. `PILOT-RISK-OBJ-LOCK-01`).

### 3.3 Trajectoire de Remédiation (Phase 7 / GA)
Dès l'ouverture d'un service d'archivage WORM certifié ou l'intégration d'appliances matérielles certifiées au Maroc, le basculement se fera par configuration sans réécriture de code via `S3_ENABLE_OBJECT_LOCK = true`.
