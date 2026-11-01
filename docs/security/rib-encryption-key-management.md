# Gestion des clés de chiffrement des RIB bancaires (ARCHITECTURE.md Part D)

## 1. Contexte réglementaire et sécurité
Le Relevé d'Identité Bancaire (RIB) à 24 chiffres constitue une donnée financière sensible soumise à la loi 09-08 (CNDP) et aux directives de Bank Al-Maghrib (BAM).
Dans AVENEL :
- La colonne `rib_encrypted` stocke le RIB chiffré réversiblement en AES-256-GCM (dérivé via PBKDF2-HMAC-SHA256, 100 000 itérations).
- La colonne `rib_sha256` stocke l'empreinte non réversible pour l'unicité et les contrôles anti-collision.
- La colonne `rib_last4` et la fonction `mask_rib()` fournissent l'affichage sécurisé (ex. `007 ***************** 1234`).
- **Règle absolue** : La valeur brute du RIB ou `rib_encrypted` ne doit jamais apparaître dans les logs applicatifs, les traces d'audit, ni les réponses de l'API.

## 2. Emplacement des clés selon les environnements

### 2.1 Environnement de développement et CI locale (`dev`)
- **Emplacement** : La clé doit résider dans un fichier physique **strictement en dehors de l'arborescence du dépôt git**.
- **Variable d'environnement** : `AVENEL_RIB_KEY_FILE`
- **Exemple de configuration** :
  ```bash
  # Clé générée dans le répertoire utilisateur hors projet
  echo -n "avenel-dev-rib-encryption-key-entropy-64chars" > ~/.avenel/rib_dev.key
  chmod 600 ~/.avenel/rib_dev.key

  export AVENEL_RIB_KEY_FILE="$HOME/.avenel/rib_dev.key"
  ```
- **Interdiction** : Aucun fichier de clé ne doit être commité dans le dépôt (`.gitignore` actif).

### 2.2 Environnement de production (`prod`)
- **Emplacement** : Service de gestion de clés managé (KMS) :
  - AWS KMS / GCP Cloud KMS / HashiCorp Vault.
- **Variable d'environnement** : `AVENEL_KMS_KEY`
- La clé est injectée dans le conteneur applicatif au runtime depuis le KMS sécurisé, sans persistance sur disque.

## 3. Comportement au démarrage de l'application
Au démarrage de l'API FastAPI (`apps/api/main.py`), la fonction `get_rib_encryption_raw_key()` est invoquée :
- Si ni `AVENEL_RIB_KEY_FILE` (fichier existant et non vide) ni `AVENEL_KMS_KEY` ne sont configurés, l'application lève une exception fatale `RibKeyMissingError` et refuse de démarrer.
- Aucun secret par défaut en dur n'est autorisé.

