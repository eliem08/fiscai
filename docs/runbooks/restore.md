# AVENEL — Manuel Opératoire : Sauvegarde Continue (PITR) et Restauration

**Référence :** ARCHITECTURE.md (C.4, E.8, Phase 5b)  
**Objectifs de service :**
- **RTO (Recovery Time Objective) :** $< 60$ minutes
- **RPO (Recovery Point Objective) :** $< 15$ minutes
- **Région de résidence :** Maroc (MA_ONLY) ou Union Européenne (EU_ALLOWED)

---

## 1. Architecture de Sauvegarde Continue (PITR) et Réplication Documentaire

La stratégie repose sur trois composantes complémentaires :
1. **Sauvegardes de base quotidiennes (Base Backups) :**
   - Générées chaque nuit à 02h00 UTC via `pg_basebackup` (chiffrées AES-256 au repos).
   - Rétention : 30 jours calendaires glissants.
2. **Archivage continu des journaux de transactions (WAL Archiving) :**
   - Mode PostgreSQL : `wal_level = replica`, `archive_mode = on`.
   - Commande d'archivage : Expédition immédiate des segments WAL de 16 Mo vers le volume de stockage persistant chiffré (`wal_archive/`).
   - Permet de restaurer l'état exact de la base à la seconde près jusqu'à l'incident.
3. **Réplication chiffrée quotidienne du stockage d'objets (Document Storage Replication) :**
   - Synchronisation nocturne chiffrée AES-256-GCM de l'ensemble des pièces originales et packs de preuves (`documents/`) vers un second site d'hébergement souverain situé dans la même région de résidence (`ma-casablanca-1` ou `eu-west-1`).
   - Rétention : Conforme à la période légale de conservation (10 ans selon le CGI art. 145 / pack fiscal).

---

## 2. Procédure de Restauration Déterministe

### Étape 1 : Isolation et Préparation de l'Instance Cible
1. Ne **jamais** écraser l'instance corrompue en place. Créer une nouvelle base ou instance isolée :
   ```bash
   createdb -h localhost -p 5432 -U postgres avenel_restored
   psql -h localhost -p 5432 -U postgres -d avenel_restored -f docker/postgres/init-roles.sql
   ```
2. Vérifier que la variable `DATA_RESIDENCY_POLICY` respecte la localisation requise.

### Étape 2 : Restauration de la Sauvegarde de Base et des Documents
```bash
# Extraction de la sauvegarde de base la plus récente
tar -xzvf /opt/avenel/backups/base_backup_latest.tar.gz -C /var/lib/postgresql/data_restored/

# Restauration et déchiffrement des pièces d'archives documentaires (AES-256-GCM)
python -c "from scripts.test_backup_restore import restore_document_storage; from pathlib import Path; restore_document_storage(Path('/opt/avenel/backups/doc_replication_latest.enc.tar.gz'), Path('/var/lib/avenel/documents_restored'), enc_key)"
```

### Étape 3 : Configuration de la Récupération Temporelle (Point-In-Time)
Dans le fichier `postgresql.conf` (ou `recovery.signal` sur PostgreSQL 16) :
```ini
restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'
recovery_target_time = '2026-11-01 14:30:00 UTC'
recovery_target_action = 'promote'
```

### Étape 4 : Exécution du Script de Test Automatisé
Le dépôt fournit le script d'audit automatisé de restauration :
```bash
python scripts/test_backup_restore.py
```

### Étape 5 : Liste des Contrôles Post-Restauration Obligatoires
Le rétablissement en production exige le passage avec succès de 5 jalons :
1. **Contrôle d'intégrité des migrations :**
   ```bash
   python scripts/check_migration_hashes.py
   ```
   *Doit valider que les 16 fichiers de migration 001 à 008 sont conformes aux empreintes gelées.*
2. **Contrôle d'isolation PostgreSQL RLS (30/30 tables) :**
   ```bash
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/avenel_restored python scripts/rls_check.py
   ```
   *Doit attester que les 30 tables locatives possèdent RLS activée, forcée, et une politique active.*
3. **Contrôle de continuité de la chaîne d'audit :**
   ```bash
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/avenel_restored python scripts/verify_audit_chain.py
   ```
   *Vérifie que la séquence cryptographique SHA-256 de chaque tenant est linéaire et exempte de rupture.*
4. **Contrôle de déchiffrement des RIB :**
   *Vérification avec la clé KMS d'environnement (`AVENEL_KMS_KEY`) que les données bancaires chiffrées sont récupérables.*
5. **Contrôle d'intégrité cryptographique des documents restaurés :**
   *Extraction d'un échantillon de pièces depuis le stockage restauré, recalcul déterministe de leur empreinte SHA-256 et comparaison stricte avec la colonne `document_versions.sha256`.*


