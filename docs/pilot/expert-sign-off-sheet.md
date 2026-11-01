# AVENEL — Fiche de Visa et d'Arbitrage des Règles Réglementaires (`needs_expert`)

**Cabinet partenaire :** Cabinet d'Expertise Comptable Pilote  
**Expert-comptable responsable :** ............................................................  
**N° d'inscription à l'Ordre (OEC) :** ......................................................  
**Date d'arbitrage :** ...... / ...... / 2026  
**Référence :** Règle Obligatoire Part A.1 (« Ne jamais inventer une règle de droit ») & Phase 5b.

---

## 1. Inventaire Exhaustif des Clés Réglementaires en Statut `needs_expert`

Pour chaque point ci-dessous, la plateforme applique un comportement de précaution (avertissement ou absence d'affectation automatique). L'expert est invité à viser l'interprétation retenue pour le cabinet.

| Réf | Domaine | Fichier Source & Clé | Question Réglementaire Ouverte | Proposition Technique par Défaut | Arbitrage Cabinet | Visa Expert |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **EXP-01** | **Bancaire** | `jurisdiction/ma/identifiers.yaml`<br>`identifiers.rib.bank_codes` | Nomenclature exhaustive des codes guichets et banques BAM (notamment codes BMCI `013`, SGMB `022`, et déclinaisons régionales BCP `1xx`). | Avertissement non bloquant (`needs_expert_warning`) si code banque non certifié par circulaire BAM officielle. | [ ] Approuvé<br>[ ] Corrigé | ________ |
| **EXP-02** | **Fiscalité** | `jurisdiction/ma/vat_withholding.yaml`<br>`withholding.accounts.receivable` | Compte CGNC pour enregistrer la créance de retenue à la source (TVA et IS) subie par l'entreprise : arbitrage entre compte `3457` (Créances sur l'État - Retenues à la source), `3453` ou sous-compte dédié `3458`. | Imputation sur compte `3457` (avec paramétrage modifiable par entité via `client_tax_mappings`). | [ ] Compte 3457<br>[ ] Compte 3453<br>[ ] Autre : ______ | ________ |
| **EXP-03** | **Comptabilité** | `jurisdiction/ma/cgnc_seed.yaml`<br>`accounts.suspense_default` | Compte d'attente à mouvementer provisoirement lors de l'ingestion d'une ligne de relevé bancaire non encore rapprochée : compte `4711` ou compte général `471`. | Utilisation temporaire du compte `4711` (Compte d'attente - Opérations bancaires non affectées). | [ ] Compte 4711<br>[ ] Compte 471<br>[ ] Autre : ______ | ________ |
| **EXP-04** | **Comptabilité** | `jurisdiction/ma/cgnc_seed.yaml`<br>`accounts.bank_fees_default` | Compte de charges par défaut pour les commissions et frais bancaires prélevés sur relevé : `6147` (Services bancaires) ou `61472` (Frais sur titres et valeurs). | Imputation sur `6147` avec extraction de la TVA déductible à 10% (compte `34552`). | [ ] Compte 6147<br>[ ] Autre : ______ | ________ |
| **EXP-05** | **Change** | `jurisdiction/ma/cgnc_seed.yaml`<br>`accounts.fx_rounding` | Compte de régularisation des centimes d'écart de conversion de change (FX rounding) : imputation en perte (`6331` Perte de change vs `6588` Charges diverses) ou en gain (`7331` Gain de change vs `7588` Produits divers). | Direction `rounding_loss` vers compte `6331` ; direction `rounding_gain` vers compte `7331`. | [ ] 6331 / 7331<br>[ ] 6588 / 7588<br>[ ] Autre : ______ | ________ |
| **EXP-06** | **TVA** | `jurisdiction/ma/vat_rules.yaml`<br>`vat.exemption.auto_entrepreneur` | Citation légale applicable pour la non-soumission à la TVA du régime de l'auto-entrepreneur : Article 91 ou Article 89 du Code Général des Impôts (CGI). | Citation CGNC / CGI : Article 91 (Régime d'exonération de la taxe sur la valeur ajoutée). | [ ] Article 91<br>[ ] Article 89<br>[ ] Autre : ______ | ________ |
| **EXP-07** | **Retenue IS** | `jurisdiction/ma/vat_withholding.yaml`<br>`withholding.is_rate` | Base de calcul de la retenue à la source IS 5% (prestations rendues par des personnes morales soumises à l'IS) : Confirmation formelle de l'assiette Hors Taxes (HT) par opposition au TTC. | Assiette HT stricte : $\text{Retenue} = 5\% \times \text{Montant HT}$. | [ ] Assiette HT<br>[ ] Autre : ______ | ________ |

---

## 2. Déclaration Formelle de l'Expert-Comptable Signataire

Je soussigné(e), ...................................................................................., agissant en qualité d'expert-comptable associé / commissaire aux comptes inscrit au tableau de l'Ordre des Experts-Comptables du Maroc sous le numéro ................................... :

1. Confirme avoir pris connaissance de l'ensemble des règles de comptabilisation et de détermination fiscale automatisées par la plateforme AVENEL.
2. Déclare validés les arbitrages cochés ci-dessus pour le paramétrage du cabinet et de ses dossiers clients pilotes.
3. Autorise le passage en statut certifié (`status: verified`) des clés visées dès intégration dans les fichiers de juridiction correspondants.

**Fait à :** .......................................................  
**Le :** ...... / ...... / 2026  

**Signature et cachet professionnel :**  
<br><br><br>
_____________________________________________________
