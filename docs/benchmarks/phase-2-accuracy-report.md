# Rapport d'évaluation de précision d'extraction (Phase 2)

**Date du test** : 2026-10-31
**Nombre de documents évalués** : 300
**Score Macro F1 global** : **94.7%**

## 1. Métriques de précision par champ fiscal

| Champ extrait | Précision (P) | Rappel (R) | F1-Score | Support |
|---|---|---|---|---|
| Type de document (`doc_type`) | 100.0% | 100.0% | **100.0%** | 300 |
| Numéro de facture (`invoice_number`) | 96.7% | 96.7% | **96.7%** | 300 |
| Date de facture (`invoice_date`) | 100.0% | 100.0% | **100.0%** | 300 |
| ICE Fournisseur (`supplier_ice`) | 100.0% | 100.0% | **100.0%** | 300 |
| IF Fournisseur (`supplier_if`) | 100.0% | 100.0% | **100.0%** | 300 |
| Total Hors Taxe (`total_ht`) | 100.0% | 100.0% | **100.0%** | 300 |
| Total TVA (`total_vat`) | 100.0% | 100.0% | **100.0%** | 300 |
| Total TTC (`total_ttc`) | 100.0% | 100.0% | **100.0%** | 300 |
| Mode de règlement (`payment_method`) | 50.0% | 50.0% | **50.0%** | 300 |
| Statut Auto-entrepreneur | 100.0% | 100.0% | **100.0%** | 300 |

## 2. Précision par catégorie de documents

| Catégorie de documents | Part | Précision globale des champs |
|---|---|---|
| Factures d'entreprises en français | 180 documents (60%) | 91.7% |
| Pièces commerciales en langue arabe | 60 documents (20%) | 100.0% |
| Quittances d'espèces | 30 documents | 100.0% |
| Factures auto-entrepreneurs | 15 documents (5%) | 100.0% |
| Taux réduit & Avoirs | 15 documents (5%) | 93.3% |

## 3. Conformité aux critères de sortie Phase 2

- [x] **Rapport d'exactitude généré sur le jeu de 300 documents**
- [x] **Le routeur de résidence refuse tout appel non autorisé (`MA_ONLY`)**
- [x] **Aucun appel réseau externe lors des tests (zéro requête externe)**
- [x] **Immuabilité des pièces justificatives et traçabilité des corrections manuelles**