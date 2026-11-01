# AVENEL — Manuel Opératoire : Sauvegarde Continue (PITR) et Restauration

**Référence :** ARCHITECTURE.md (C.4, E.8, Phase 5b)  
**Objectifs de service :**
- **RTO (Recovery Time Objective) :** $< 60$ minutes
- **RPO (Recovery Point Objective) :** $< 15$ minutes
- **Région de résidence :** Maroc (MA_ONLY) ou Union Européenne (EU_ALLOWED)

---

## 1. Architecture de Sauvegarde Continue (PITR)

La stratégie repose sur deux composantes complémentaires :
1. **Sauvegardes de base quotidiennes (Base Backups) :**
   - Générées chaque nuit à 02h00 UTC via `pg_basebackup` (chiffrées AES-256 au repos).
   - Rétention : 30 jours calendaires glissants.
2. **Archivage continu des journaux de transactions (WAL Archiving) :**
   - Mode PostgreSQL : `wal_level = replica`, `archive_mode = on`.
   - Commande d'archivage : Expédition immédiate des segments WAL de 16 Mo vers le volume de stockage persistant chiffré (`wal_archive/`).
   - Permet de restaurer l'état exact de la base à la seconde près jusqu'à l'incident.

---

## 2. Procédure de Restauration Déterministe

### Étape 1 : Isolation et Préparation de l'Instance Cible
1. Ne **jamais** écraser l'instance corrompue en place. Créer une nouvelle base ou instance isolée :
   ```bash
   createdb -h localhost -p 5432 -U postgres avenel_restored
   psql -h localhost -p 5432 -U postgres -d avenel_restored -f docker/postgres/init-roles.sql
   ```
2. Vérifier que la variable `DATA_RESIDENCY_POLICY` respecte la localisation requise.

### Étape 2 : Restauration de la Sauvegarde de Base
```bash
# Extraction de la sauvegarde de base la plus récente
tar -xzvf /opt/avenel/backups/base_backup_latest.tar.gz -C /var/lib/postgresql/data_restored/
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
Le rétablissement en production exige le passage avec succès de 4 jalons :
1. **Contrôle d'intégrité des migrations :**
   ```bash
   python scripts/check_migration_hashes.py
   ```
   *Doit valider que les 14 fichiers de migration 001 à 007 sont conformes aux empreintes gelées.*
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

