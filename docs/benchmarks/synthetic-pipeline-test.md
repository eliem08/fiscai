# Rapport de test du pipeline synthétique (Phase 2)

**Date du test** : 2026-10-31
**Nombre de documents synthétiques évalués** : 30
**Moteur OCR** : RapidOCR / PaddleOCR ONNX PP-OCRv4 v1.4.4
**Perturbations appliquées** : skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70

> [!NOTE]
> Ce test évalue la robustesse de la chaîne d'extraction sur des images raster générées et bruitées.
> Conformément à ARCHITECTURE.md Part H, les portails de validation du pilote sont mesurés
> exclusivement sur le jeu de données réelles (≥ 300 pièces). Ce test synthétique valide le pipeline
> mais ne constitue pas la validation finale du pilote.

## 1. Taux d'exactitude stricte par champ (Exact-Match)

| Champ fiscal | Total évalué | Exact-Match | Échecs | Taux d'exactitude |
|---|---|---|---|---|
| `supplier_ice` (ICE Fournisseur) | 30 | 28 | 2 | 93.33% |
| `invoice_number` (Numéro facture) | 30 | 29 | 1 | 96.67% |
| `invoice_date` (Date de facture) | 30 | 30 | 0 | 100.00% |
| `supplier_if` (IF Fournisseur) | 30 | 26 | 4 | 86.67% |
| `total_ht` (Total Hors Taxe) | 30 | 30 | 0 | 100.00% |
| `total_vat` (Total TVA) | 30 | 30 | 0 | 100.00% |
| `total_ttc` (Total TTC) | 30 | 29 | 1 | 96.67% |

## 2. Comparaison indicative avec les seuils cibles Part H

| Portail Part H | Seuil cible Part H | Résultat synthétique obtenu | Statut indicatif |
|---|---|---|---|
| ICE, invoice number, date exact match | ≥ 97,0% | 90.00% | Non atteint |
| HT, TVA par taux, TTC exact match | ≥ 98,0% | 96.67% | Non atteint |

## 3. Analyse des échecs d'extraction sous bruit OCR

Exemples d'écarts observés lors du test sur images perturbées :

- **Pièce `fr_inv_001`** (french_corporate) :
  - `supplier_if` : attendu `23456789`, extrait `None`
- **Pièce `fr_inv_008`** (french_corporate) :
  - `supplier_ice` : attendu `009012345678901`, extrait `None`
- **Pièce `fr_inv_015`** (french_corporate) :
  - `supplier_if` : attendu `67890123`, extrait `None`
- **Pièce `fr_inv_016`** (french_corporate) :
  - `total_ttc` : attendu `2282.87`, extrait `228287.0`
- **Pièce `fr_inv_022`** (french_corporate) :
  - `invoice_number` : attendu `FAC-2026-1022`, extrait `N`