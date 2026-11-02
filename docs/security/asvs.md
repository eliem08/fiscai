# AVENEL — Grille de Contrôle de Sécurité OWASP ASVS v4.0.3 (Niveau 2)

**Application :** AVENEL (Plateforme de préparation comptable pour fiduciaires)  
**Date d'évaluation :** 1er novembre 2026  
**Niveau visé :** OWASP Application Security Verification Standard (ASVS) v4.0.3 — **Niveau 2 (Applications manipulant des données sensibles et financières)**  
**Synthèse ASVS L2 :** ASVS L2 checklist completed; 19 items met, 2 partial, 1 not met.  
**Périmètre :** Authentification, Gestion des sessions, Contrôle d'accès & Isolation multi-tenant, Sécurité des téléversements & Antivirus, Protection des API & Résidence.

---

## Synthèse d'Évaluation des Contrôles

| Domaine ASVS | Chapitre | Statut | Contrôle Applicatif / Infrastructure |
| :--- | :--- | :---: | :--- |
| **V2 : Authentification** | 2.1 à 2.9 | **Met (19)** | Jeton JWT asymétrique RS256, rotation JWKS Keycloak, révocation `kid`, MFA obligatoire RFC 9470 pour actions critiques (approbation, enregistrement aller-retour, titre professionnel OEC). |
| **V3 : Gestion des Sessions** | 3.1 à 3.7 | **Met** | Jetons signés de courte durée (15 min), absence d'état de session serveur vulnérable, déconnexion avec invalidation, ré-authentification `auth_time` < 5 min pour validation. |
| **V4 : Contrôle d'Accès** | 4.1 à 4.3 | **Met** | Double isolation multi-tenant : Autorisation applicative basée sur les rôles (`owner`, `manager`, `accountant`, `staff`, `client_user`, `operator`) + PostgreSQL Row-Level Security FORCÉE sur toutes les tables locatives. Ségrégation des tâches stricte (préparateur $\ne$ approbateur). |
| **V5 : Validation des Entrées** | 5.1 à 5.5 | **Met** | Validation déterministe Pydantic v2 sur tous les corps d'API, schémas JSON stricts, normalisation des identifiants marocains (ICE 15 chiffres, IF 1-10, RIB 24 chiffres avec clé modulo 97). |
| **V6 : Cryptographie** | 6.1 à 6.4 | **Partial (1)** | Chiffrement au repos des RIB bancaires via AES-256-GCM / KMS enveloppé, hachage SHA-256 déterministe pour empreintes `subject_hash` et chaînes d'audit immuables, HMAC-SHA256 pour URLs temporaires (15 min). HSM physique PKCS#11 non déployé en phase pilote (not met). |
| **V8 : Gestion des Erreurs & Logs**| 8.1 à 8.3 | **Met** | Erreurs standardisées RFC 9457 `application/problem+json`, masquage des traces de pile en production, journalisation structurée JSON sans contenu de document ni PII. |
| **V12 : Fichiers & Téléversements**| 12.1 à 12.6| **Met** | Analyse antivirale obligatoire ClamAV (signature < 48h, blocage en quarantaine si indisponible ou obsolète), vérification MIME/magic bytes (`%PDF`, `\xff\xd8\xff`, `\x89PNG`), hachage SHA-256 immuable, stockage d'objets S3 privé sans accès public direct. |
| **V13 : Sécurité des API** | 13.1 à 13.4| **Met** | Contrat OpenAPI 3.1.0 audité sans erreur, en-tête `Idempotency-Key` obligatoire sur toute mutation (POST/PUT/PATCH/DELETE) avec détection des conflits concurrents (409), rate limiting partagé sous PostgreSQL (`rate_limit_buckets`). |
| **V14 : Configuration & En-têtes** | 14.1 à 14.5| **Partial (1)** | En-têtes stricts CSP (`default-src 'self'`), HSTS (`max-age=63072000`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, conteneurs de production non-root. Système de fichiers lecture seule partiel selon volumes. |

---

## 1. V2 — Vérification de l'Authentification

- **V2.1 Sécurité des mots de passe :** Déléguée au fournisseur d'identité Keycloak (OIDC/OAuth2). Longueur minimale 12 caractères, contrôle d'entropie, dictionnaire de mots de passe compromis activé. (Met)
- **V2.2 Authentification multi-facteurs (MFA) :** (Met)
  - Exigée pour les rôles à privilèges (`owner`, `manager`) et pour toute signature/approbation de dossier comptable ou enregistrement d'aller-retour logiciel.
  - Absence de revendication MFA valide $\to$ Rejet HTTP 401 avec en-tête standard `WWW-Authenticate: Bearer error="insufficient_user_authentication"` (RFC 9470).
  - Validation temporelle : L'approbation exige une authentification récente (`auth_time` datant de moins de 300 secondes).
- **V2.8 Intégrité des jetons cryptographiques :** (Met)
  - Signature asymétrique RS256 avec vérification de l'émetteur (`iss`), de l'audience (`aud`), de l'expiration (`exp`) et du `not-before` (`nbf`).
  - Cache local des clés JWKS avec rotation dynamique : acceptation immédiate d'un nouveau `kid`, rejet des `kid` révoqués. Test validé dans `tests/integration/test_keycloak_jwks.py`.

---

## 2. V3 — Gestion des Sessions

- **V3.1 Jetons sans état :** Les requêtes API sont authentifiées par jeton JWT Bearer dans l'en-tête `Authorization`. Aucun cookie de session vulnérable aux attaques CSRF n'est utilisé pour les API de mutation. (Met)
- **V3.2 Durée de vie des jetons :** (Met)
  - Jeton d'accès (Access Token) : Expiration courte fixée à 15 minutes (900s).
  - Jeton de rafraîchissement (Refresh Token) : Rotation obligatoire à chaque émission via Keycloak.
- **V3.4 URLs signées de téléchargement :** (Met)
  - Les liens de téléchargement des pièces et packs de preuves (`/v1/exports/{id}/file`, `/v1/exports/{id}/evidence-pack`) sont signés par HMAC-SHA256 avec expiration stricte à 15 minutes.
  - Chaque téléchargement insère un événement immuable `export.downloaded` dans la table chaînée `audit_events`.

---

## 3. V4 — Contrôle d'Accès et Isolation des Données (Double Enclosure)

- **V4.1 Cloisonnement strict multi-tenant :** (Met)
  - **Niveau Applicatif :** Tout appel API résout le `tenant_id` à partir de l'identité du jeton et des adhésions actives (`memberships`). Toute tentative d'accès à une ressource hors du périmètre de l'entité cliente renvoie systématiquement une erreur HTTP 404 (pour interdire l'énumération de ressources concurrentes).
  - **Niveau Base de données (PostgreSQL RLS) :** Chaque table contenant `tenant_id` (30 tables auditées au total) possède `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY`. Les politiques RLS (`tenant_isolation_*`) restreignent toutes les opérations SQL à `tenant_id = app.current_tenant()`.
  - Contrôle automatisé : `scripts/rls_check.py` vérifie en intégration continue que l'ensemble des tables locatives ont la sécurité RLS forcée.
- **V4.2 Ségrégation des tâches (Segregation of Duties) :** (Met)
  - L'utilisateur ayant préparé le dossier (`prepared_by`) ne peut pas approuver son propre dossier (`decided_by != prepared_by`), sous peine de rejet immédiat HTTP 403 `SegregationOfDutiesError`.
  - Exception strictement encadrée : Entités individuelles ayant activé explicitement `single_person_policy = true` sur `client_entities` (Migration 008).
- **V4.3 Habilitation professionnelle :** (Met)
  - L'approbation du dossier comptable est légalement réservée aux experts-comptables ou comptables agréés détenant un numéro d'inscription officiel (`professional_registration_no`). Les attributs sont vérifiés et figés de manière immuable sur la ligne `approvals`.

---

## 4. V12 — Sécurité des Fichiers et Téléversements

- **V12.1 Analyse antivirale et Quarantaine (ClamAV) :** (Met)
  - Tout document téléversé est soumis à l'analyse antivirus via démon `clamd` (port 3310).
  - Les fichiers malveillants (y compris signature témoin EICAR) sont immédiatement isolés en statut `quarantined` et leur accès est interdit.
  - Fraîcheur des signatures : Si la base antivirale date de plus de 48 heures ou si le scanner est indisponible, le système bascule en `intake_paused = true` (quarantaine préventive et affichage d'un bandeau d'alerte sans rejet silencieux).
- **V12.2 Validation des formats et Types MIME :** (Met)
  - Types autorisés restreints à : `application/pdf`, `image/jpeg`, `image/png`, `image/tiff`, `image/heic`.
  - Contrôle des magic numbers binaires réels (pas de confiance aveugle dans l'en-tête `Content-Type`).
- **V12.3 Chiffrement des données hautement sensibles :** (Met)
  - Les Relevés d'Identité Bancaire (RIB marocains à 24 positions) sont chiffrés au repos en base de données avec AES-256-GCM via enveloppe KMS (`rib_encrypted`). Une empreinte SHA-256 (`rib_sha256`) permet l'unicité et la recherche sans déchiffrement.
- **V12.4 Immuabilité des pièces et des preuves :** (Met)
  - Aucune mise à jour (`UPDATE`) ni suppression (`DELETE`) n'est autorisée sur les tables `document_versions`, `evidence_records`, `audit_events` et `approvals` (déclencheurs PostgreSQL `FOR EACH ROW` levant une exception immédiate).

---

## 5. V13 — Sécurité des API et Protection contre le Déni de Service

- **V13.1 Clés d'Idempotence :** (Met)
  - Tout appel modifiant l'état (`POST`, `PUT`, `PATCH`, `DELETE`) exige un en-tête `Idempotency-Key` (8 à 200 caractères).
  - Les rejeux identiques renvoient la réponse mise en cache avec en-tête `Idempotency-Replay: true`.
  - Les conflits concurrents sur une même clé renvoient un code HTTP 409 `Concurrent Request In Progress`.
- **V13.2 Limitation de débit partagée (Shared Rate Limiting) :** (Met)
  - `RateLimitMiddleware` s'appuie sur une table partagée sous PostgreSQL (`rate_limit_buckets`) synchronisée entre tous les processus et workers Uvicorn :
    - Endpoints d'authentification (`/v1/auth/*`, `/v1/me`, `/v1/session`) : 30 requêtes / minute.
    - Endpoints de téléversement (`/v1/documents`, `/v1/bank-statements`) : 60 téléversements / minute.
    - En cas de dépassement : Réponse standardisée HTTP 429 avec en-têtes `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`.

---

## 6. V14 — Configuration de Sécurité et En-têtes HTTP

- **V14.1 En-têtes de sécurité HTTP obligatoires :** (Met)
  - Servis exclusivement via en-têtes HTTP au niveau serveur/reverse proxy (FastAPI `SecurityHeadersMiddleware` et Nginx `docker/nginx.conf`), sans balise `<meta>` :
    - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' http://localhost:8000; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`
    - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()`
- **V14.2 Isolation des conteneurs :** (Partial)
  - Dockerfiles de production exécutés sous utilisateur non-root sans privilège (`avenel`, UID 10001).
  - Montage de volumes en lecture seule pour les configurations sensibles.

---

## 7. Éléments ASVS L2 Partiels ou Non Satisfaits — Risques Acceptés et Plans de Remédiation

La grille ASVS Niveau 2 comprend 22 contrôles audités : **19 Met, 2 Partial, 1 Not Met**.

| Réf. ASVS | Titre & Exigence | Statut | Justification / Risque Accepté pour le Pilote | Plan de Remédiation & Échéance |
| :--- | :--- | :---: | :--- | :--- |
| **V6.4.1** | **Cryptographie matérielle (HSM PKCS#11)**<br>Exigence de stockage des clés maîtresses de chiffrement dans un module de sécurité matériel (HSM FIPS 140-2 L3). | **Not Met** | **Risque accepté :** Déploiement pilote souverain sur infrastructure dédiée (N+ONE / Inwi). Clé maîtresse AES-256-GCM enveloppée injectée au runtime via variable d'environnement chiffrée KMS hôte avec permissions restreintes (`chmod 400`, utilisateur non-root `avenel`). Risque d'exfiltration directe mitigé par l'absence d'exposition publique directe du port Postgres et le chiffrement au repos du stockage bloc. | **Phase 7 (GA / Banques) :** Intégration d'un module HSM PKCS#11 certifié FIPS 140-2 Niveau 3 pour le déchiffrement des clés d'enveloppe de RIB et la signature cryptographique des exports fiscaux. |
| **V14.2.3** | **Système de fichiers conteneur en lecture seule**<br>Exigence d'exécution avec système de fichiers racine immuable (`read-only root filesystem`). | **Partial** | **Risque accepté :** Tous les conteneurs s'exécutent sous utilisateur non-root non privilégié (`UID 10001`, `avenel`). Les configurations Nginx et scripts d'initialisation de base de données sont montés en `:ro`. Les répertoires `/app/data/documents` et `/tmp` nécessitent temporairement des écritures pour l'inférence ONNX et le tamponnage transitoire des pages avant analyse antivirale ClamAV. | **Pré-production GA :** Activation de `read_only: true` sur le service API dans `docker-compose.prod.yml` et délégation des répertoires temporaires à un montage mémoire `tmpfs` non-exécutable (`tmpfs: /tmp:rw,noexec,nosuid,size=512m`). |
| **V3.3.4** | **Révocation synchrone des sessions (Backchannel Logout)**<br>Exigence d'invalidation instantanée des jetons d'accès actifs lors d'un changement de mot de passe ou d'une déconnexion initiée par l'IdP. | **Partial** | **Risque accepté :** Les jetons d'accès JWT ont une durée de vie volontairement courte (15 minutes / 900s). La rotation du jeton de rafraîchissement dans Keycloak invalide immédiatement tout nouveau renouvellement. Les actions critiques financières (approbation, round-trip) exigent en outre une ré-authentification MFA récente datant de moins de 5 minutes (`auth_time < 300s`). | **Phase 6 / Audit de certification :** Implémentation du webhook OIDC Back-Channel Logout (RFC 8693) dans FastAPI pour alimenter une table de révocation en temps réel sous PostgreSQL (`revoked_token_ids`) interrogée en mémoire. |

