# AVENEL — Procédure de Test d'Aller-Retour Logiciel (Sage 100 & Odoo)

**Référence :** ARCHITECTURE.md (E.8, Phase 5, Phase 5b)  
**Objet :** Procédure opératoire pour tester et consigner la validation d'un format d'exportation sur le progiciel comptable du cabinet.

---

## 1. Contexte et Règle d'Immuabilité

Conformément à la règle de sécurité et à l'exigence #1 de la Phase 5 :
> *L'exportation comptable ne valide jamais automatiquement un profil d'export. La vérification de compatibilité logicielle (`verified_round_trip_at`) doit faire l'objet d'un enregistrement formel par un associé ou gestionnaire (`owner` ou `manager`), sous authentification MFA, documenté dans la table `export_round_trips`.*

Tant qu'aucun aller-retour réussi (`ok`) n'est consigné, l'interface affiche l'avertissement :  
**« Format non vérifié sur votre logiciel »**.

---

## 2. Procédure Sage 100 Comptabilité (Formats CSV & PNM)

### Étape 2.1 : Génération de l'export test dans AVENEL
1. Accéder au dossier validé du client pilote.
2. Ouvrir l'écran d'exportation (`ExportScreen`).
3. Sélectionner la cible **Sage 100 CSV** (ou **Sage 100 PNM**).
4. Cliquer sur **« Exporter les écritures »** et télécharger le fichier généré (`ecritures_sage100.csv` / `.pnm`).

### Étape 2.2 : Importation dans Sage 100 Comptabilité
1. Lancer **Sage 100 Comptabilité** (version 100c v8.0+ ou v10.0+).
2. Ouvrir le dossier de la société correspondante.
3. Aller dans : **Fichier > Importer > Format paramétrable...** (ou format standard Sage pour le fichier `.pnm`).
4. Sélectionner le fichier téléchargé.
5. Vérifier les options d'importation :
   - Encodage : Windows ANSI (`Windows-1252`).
   - Séparateur de champs : Point-virgule (`;`).
   - Séparateur décimal : Virgule (`,`).
6. Valider l'intégration des écritures dans le journal approprié (`ACH`, `VTE`, `BQ`, `OD`).

### Étape 2.3 : Contrôles de validation dans Sage 100
- **Équilibre des journaux :** Total Débit = Total Crédit.
- **Codes comptes généraux :** Comptes CGNC paddés sur 8 positions (ex. `61110000` ou `44110000`).
- **Comptes tiers auxiliaires :** Rattachement correct aux fiches tiers fournisseurs/clients.
- **Dates d'écritures :** Dates au format `JJMMAAAA` sans anomalie de période.

---

## 3. Procédure Odoo Enterprise (Format CSV)

### Étape 3.1 : Génération de l'export Odoo
1. Dans AVENEL, sélectionner le profil **Odoo CSV**.
2. Télécharger le fichier généré (`ecritures_odoo.csv`).

### Étape 3.2 : Importation dans Odoo
1. Ouvrir Odoo Comptabilité (v16.0+, v17.0+ ou v18.0+).
2. Naviguer vers : **Comptabilité > Écritures comptables**.
3. Cliquer sur le menu déroulant **Favoris > Importer des enregistrements**.
4. Téléverser le fichier `ecritures_odoo.csv`.
5. Cliquer sur **« Tester l'importation »** : Odoo doit afficher le bandeau vert *« Tout semble correct »*.
6. Cliquer sur **« Importer »**.

---

## 4. Enregistrement Formel de l'Aller-Retour dans AVENEL

Dès l'importation effectuée, consigner immédiatement le test dans AVENEL :

### Option A : Via l'Interface Utilisateur
1. Sur l'écran d'exportation ([`ExportScreen.tsx`](file:///c:/Users/21263/Downloads/fiscai/src/components/domain/ExportScreen.tsx)), cliquer sur **« Enregistrer un aller-retour logiciel »**.
2. Renseigner le progiciel (`Sage 100c`, `Odoo Enterprise`), la version exacte (ex. `10.03`), et le résultat (`ok` ou `failed`).
3. Ajouter une note explicative (ex. *"Importation de 128 écritures sans rejet"*).
4. Joindre une capture d'écran de l'import réussi.
5. Valider avec authentification MFA.

### Option B : Via l'API
```bash
curl -X POST "https://api.avenel.ma/v1/export-profiles/{profile_id}:record-round-trip" \
  -H "Authorization: Bearer $OEC_MFA_TOKEN" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "software": "Sage 100c Comptabilité",
    "version": "10.02",
    "imported_at": "2026-11-01T14:30:00Z",
    "result": "ok",
    "notes": "Validation réussie sur dossier pilote SARL avec 45 pièces équilibrées."
  }'
```

