# AVENEL — Protocole de Demande d'Échantillons Documentaires Réels

**Destinataire :** Cabinet d'expertise comptable partenaire du pilote  
**Référence :** ARCHITECTURE.md (Part H, Phase 5b)  
**Objet :** Constitution du corpus d'évaluation et de calage terrain sur pièces comptables marocaines réelles.

---

## 1. Cadre Juridique et Confidentialité (Loi 09-08 & CNDP)

La transmission des pièces s'effectue sous le strict respect du Règlement Général sur la Protection des Données et de la Loi marocaine n° 09-08 :
1. **Accord de Traitement des Données (DPA) :** Signature préalable du DPA disponible sur l'API (`GET /v1/compliance/dpa`).
2. **Déclaration préalable CNDP :** Enregistrement sous le récépissé de conformité CNDP (`GET /v1/compliance/cndp`).
3. **Chiffrement de bout en bout :** Les pièces sont téléversées via canal sécurisé TLS 1.3 et stockées avec chiffrement au repos AES-256 (`tests/fixtures/real/`, exclu de tout dépôt git public).
4. **Engagement d'immuabilité :** Aucune donnée client n'est utilisée pour l'entraînement de modèles tiers publics.

---

## 2. Typologie des Pièces Requises (100 à 150 documents)

Pour garantir une représentativité fidèle des flux mensuels d'une PME marocaine, le cabinet est invité à fournir les échantillons suivants :

### 2.1 Factures Fournisseurs & Achats (60 à 80 pièces)
- **Régimes de TVA variés :**
  - Taux standard 20% (prestations de services, biens de consommation).
  - Taux intermédiaire 14% (transport, électricité, travaux immobiliers).
  - Taux réduits 10% (restauration, hôtellerie, opérations bancaires) et 7% (eau, fournitures scolaires, produits de base).
  - Factures multi-taux (ex. facture de télécommunication avec 20% sur abonnement et 10% sur terminaux).
  - Factures exonérées sans droit à déduction ou avec mention auto-entrepreneur (Art. 91 CGI).
- **Variété typographique et linguistique :**
  - Factures bilingues Français / Arabe ou monolingues Arabe.
  - Factures imprimées par ERP (Sage, Odoo, SAP) et factures scannées (factures manuscrites exclues pour le pilote automatique, réservées à la saisie assistée).
  - Pièces numérisées par smartphone (légère inclinaison, éclairage non uniforme, JPEG compressé).

### 2.2 Factures Clients & Ventes (20 à 30 pièces)
- Factures émises avec numérotation séquentielle continue.
- Factures avec retenue à la source appliquée par le client (RAS TVA ou RAS IS de 5% pour travaux ou prestations).
- Avoirs et notes de crédit.

### 2.3 Relevés Bancaires (2 à 3 mois par banque partenaire)
Fournir des relevés sous format PDF numérique natif ou scanné propre pour les principales banques marocaines :
- **Attijariwafa Bank** (Code RIB `007`)
- **Banque Centrale Populaire / Banques Populaires Régionales** (Plage `1xx`, ex. `101`, `181`)
- **Bank of Africa — BMCE Group** (Code RIB `011`)
- **BMCI** (Code RIB `013`)
- **CIH Bank** (Code RIB `230`)
- **Société Générale Maroc — SGMB** (Code RIB `022`)

---

## 3. Modalités Pratiques de Téléversement

1. Accéder au portail fiduciaire sécurisé : `https://pilot.avenel.ma` (ou instance locale du cabinet).
2. Se connecter avec le compte `manager` ou `owner` habilité (authentification multifacteur activée).
3. Déposer les pièces par lot dans le dossier d'évaluation du client pilote.
